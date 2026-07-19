#!/usr/bin/env python3
"""
Fetch market cap and liquidity metrics for all earnings dates.

For each (ticker, earnings_date) pair, fetches:
  - market_cap: Market capitalization in local currency
  - market_cap_usd: Market cap converted to USD (for comparison)
  - shares_outstanding: Total shares outstanding
  - float_shares: Shares available for trading (float)
  - float_percent: Float as percentage of outstanding
  - avg_volume_10d: Average 10-day trading volume (liquidity)
  - avg_volume_3m: Average 3-month trading volume
  - dollar_volume_daily: Average daily dollar volume (market_cap_usd × volume)
  - liquidity_score: Composite liquidity metric (0-100)

These metrics help:
  - Filter by company size (small/mid/large cap)
  - Assess trading liquidity (can you actually trade this?)
  - Identify size-based risk (small caps = higher volatility)
  - Dollar volume = realistic position sizing

IMPORTANT: Fetches data as of the earnings date to avoid look-ahead bias.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd
import numpy as np


def create_market_cap_table():
    """Create market_cap_liquidity table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_cap_liquidity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            market_cap REAL,
            market_cap_usd REAL,
            shares_outstanding REAL,
            float_shares REAL,
            float_percent REAL,
            avg_volume_10d REAL,
            avg_volume_3m REAL,
            dollar_volume_daily REAL,
            liquidity_score REAL,
            currency TEXT,
            exchange TEXT,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_market_cap_liquidity_ticker_date
        ON market_cap_liquidity(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified market_cap_liquidity table")


def get_earnings_dates():
    """Get all unique (ticker, earnings_date) combinations."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker, earnings_date
        FROM earnings_intraday_analysis
        ORDER BY earnings_date DESC, ticker
    """)

    results = cursor.fetchall()
    conn.close()

    return results


def fetch_market_cap_liquidity(ticker, earnings_date):
    """
    Fetch market cap and liquidity metrics from yfinance.

    Returns dict with market cap, liquidity metrics, and derived scores.
    """
    try:
        stock = yf.Ticker(ticker)

        # Parse earnings date
        earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')

        # Get info (current snapshot - note: yfinance doesn't provide historical market cap easily)
        try:
            info = stock.info
        except Exception:
            info = {}

        # Get historical prices for volume calculation
        # Fetch 3 months before earnings for average volume
        start_date = earnings_dt - timedelta(days=100)
        end_date = earnings_dt  # Exclusive, so we get up to day before

        try:
            hist = stock.history(start=start_date, end=end_date, interval='1d')
        except Exception:
            hist = pd.DataFrame()

        # Initialize result
        result = {
            'market_cap': None,
            'market_cap_usd': None,
            'shares_outstanding': None,
            'float_shares': None,
            'float_percent': None,
            'avg_volume_10d': None,
            'avg_volume_3m': None,
            'dollar_volume_daily': None,
            'liquidity_score': None,
            'currency': None,
            'exchange': None,
            'data_quality': 'missing',
            'fetch_error': None
        }

        has_data = False

        # Market Cap
        if 'marketCap' in info and info['marketCap'] is not None:
            result['market_cap'] = float(info['marketCap'])
            has_data = True

        # Currency
        if 'currency' in info and info['currency'] is not None:
            result['currency'] = str(info['currency'])

        # Exchange
        if 'exchange' in info and info['exchange'] is not None:
            result['exchange'] = str(info['exchange'])

        # Convert to USD (rough estimate using current rates)
        # For Swedish stocks (SEK), approximate conversion
        if result['market_cap'] is not None and result['currency'] == 'SEK':
            # Rough SEK to USD: 1 USD ≈ 10 SEK (varies over time)
            result['market_cap_usd'] = result['market_cap'] / 10.0
        elif result['market_cap'] is not None:
            # Assume already in USD or close enough
            result['market_cap_usd'] = result['market_cap']

        # Shares
        if 'sharesOutstanding' in info and info['sharesOutstanding'] is not None:
            result['shares_outstanding'] = float(info['sharesOutstanding'])
            has_data = True

        if 'floatShares' in info and info['floatShares'] is not None:
            result['float_shares'] = float(info['floatShares'])
            has_data = True

        # Float percentage
        if result['float_shares'] is not None and result['shares_outstanding'] is not None and result['shares_outstanding'] > 0:
            result['float_percent'] = (result['float_shares'] / result['shares_outstanding']) * 100

        # Volume metrics from historical data
        if not hist.empty and 'Volume' in hist.columns:
            volumes = hist['Volume'].dropna()

            if len(volumes) > 0:
                # Last 10 days average
                if len(volumes) >= 10:
                    result['avg_volume_10d'] = float(volumes.iloc[-10:].mean())
                    has_data = True

                # 3-month average
                result['avg_volume_3m'] = float(volumes.mean())
                has_data = True

                # Dollar volume (using last available price before earnings)
                if len(hist) > 0 and 'Close' in hist.columns:
                    last_price = hist['Close'].iloc[-1]
                    avg_vol = result['avg_volume_10d'] if result['avg_volume_10d'] is not None else result['avg_volume_3m']

                    if avg_vol is not None:
                        # Dollar volume in local currency
                        dollar_vol_local = last_price * avg_vol

                        # Convert to USD
                        if result['currency'] == 'SEK':
                            result['dollar_volume_daily'] = float(dollar_vol_local / 10.0)
                        else:
                            result['dollar_volume_daily'] = float(dollar_vol_local)

        # Calculate liquidity score (0-100)
        # Based on: market cap, average volume, dollar volume
        # Higher score = more liquid
        if result['market_cap_usd'] is not None and result['dollar_volume_daily'] is not None:
            # Normalize market cap (log scale)
            # Small cap: $10M, Mid cap: $1B, Large cap: $10B+
            market_cap_score = min(100, (np.log10(max(result['market_cap_usd'], 1e6)) - 7) * 20)  # 7 = $10M

            # Normalize dollar volume (log scale)
            # Low: $10K/day, Medium: $1M/day, High: $10M+/day
            volume_score = min(100, (np.log10(max(result['dollar_volume_daily'], 1e4)) - 4) * 25)  # 4 = $10K

            # Combined score (weighted average)
            result['liquidity_score'] = (market_cap_score * 0.6 + volume_score * 0.4)
            result['liquidity_score'] = max(0, min(100, result['liquidity_score']))

        if has_data:
            result['data_quality'] = 'found'
        else:
            result['fetch_error'] = 'No market cap or liquidity data available'

        return result

    except Exception as e:
        return {
            'market_cap': None,
            'market_cap_usd': None,
            'shares_outstanding': None,
            'float_shares': None,
            'float_percent': None,
            'avg_volume_10d': None,
            'avg_volume_3m': None,
            'dollar_volume_daily': None,
            'liquidity_score': None,
            'currency': None,
            'exchange': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_market_cap_liquidity(ticker, earnings_date, data):
    """Store market cap and liquidity data in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO market_cap_liquidity
        (ticker, earnings_date, market_cap, market_cap_usd,
         shares_outstanding, float_shares, float_percent,
         avg_volume_10d, avg_volume_3m, dollar_volume_daily,
         liquidity_score, currency, exchange,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['market_cap'],
        data['market_cap_usd'],
        data['shares_outstanding'],
        data['float_shares'],
        data['float_percent'],
        data['avg_volume_10d'],
        data['avg_volume_3m'],
        data['dollar_volume_daily'],
        data['liquidity_score'],
        data['currency'],
        data['exchange'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def format_market_cap(cap_usd):
    """Format market cap for display."""
    if cap_usd is None:
        return "N/A"
    if cap_usd >= 1_000_000_000:
        return f"${cap_usd/1_000_000_000:.2f}B"
    elif cap_usd >= 1_000_000:
        return f"${cap_usd/1_000_000:.1f}M"
    elif cap_usd >= 1_000:
        return f"${cap_usd/1_000:.1f}K"
    else:
        return f"${cap_usd:.0f}"


def format_dollar_volume(dvol):
    """Format dollar volume for display."""
    if dvol is None:
        return "N/A"
    if dvol >= 1_000_000:
        return f"${dvol/1_000_000:.2f}M"
    elif dvol >= 1_000:
        return f"${dvol/1_000:.1f}K"
    else:
        return f"${dvol:.0f}"


def main():
    """Main execution."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Fetch market cap and liquidity metrics')
    parser.add_argument('--date', type=str, help='Fetch only for this date (YYYY-MM-DD)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers to fetch')
    args = parser.parse_args()

    print("="*80)
    print("FETCHING MARKET CAP & LIQUIDITY METRICS")
    print("="*80)
    print()
    print("Fetching:")
    print("  - Market capitalization")
    print("  - Shares outstanding & float")
    print("  - Average trading volume (10d, 3m)")
    print("  - Dollar volume (liquidity)")
    print("  - Liquidity score (0-100)")
    print()

    # Create table
    create_market_cap_table()

    # Get all earnings dates
    earnings_data = get_earnings_dates()

    # Filter by date if specified
    if args.date:
        earnings_data = [(ticker, date) for ticker, date in earnings_data if date == args.date]
        print(f"Filtering for date: {args.date}")

    # Filter by tickers if specified
    if args.tickers:
        ticker_list = [t.strip().upper() for t in args.tickers.split(',')]
        earnings_data = [(ticker, date) for ticker, date in earnings_data if ticker in ticker_list]
        print(f"Filtering for tickers: {', '.join(ticker_list)}")

    total = len(earnings_data)

    print(f"Found {total} unique (ticker, earnings_date) combinations")
    print()

    # Process each ticker/date
    found_count = 0
    missing_count = 0
    error_count = 0

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] {ticker} on {earnings_date}...", end=" ")

        # Fetch market cap and liquidity
        data = fetch_market_cap_liquidity(ticker, earnings_date)

        # Store in database
        store_market_cap_liquidity(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            cap = format_market_cap(data['market_cap_usd'])
            dvol = format_dollar_volume(data['dollar_volume_daily'])
            liq_score = data['liquidity_score'] if data['liquidity_score'] is not None else 0

            parts = [f"Cap: {cap}"]
            if data['dollar_volume_daily'] is not None:
                parts.append(f"Vol: {dvol}/day")
            if data['liquidity_score'] is not None:
                parts.append(f"Liq: {liq_score:.0f}/100")

            print(f"✓ {', '.join(parts)}")
            found_count += 1
        elif data['data_quality'] == 'missing':
            print(f"⚠ No data")
            missing_count += 1
        else:
            print(f"✗ {data.get('fetch_error', 'Error')}")
            error_count += 1

        # Rate limiting - be nice to yfinance
        if idx % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.2)

    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total processed: {total}")
    print(f"  ✓ Found data:   {found_count} ({found_count/total*100:.1f}%)")
    print(f"  ⚠ Missing data: {missing_count} ({missing_count/total*100:.1f}%)")
    print(f"  ✗ Error:        {error_count} ({error_count/total*100:.1f}%)")
    print()
    print("Data stored in market_cap_liquidity table")
    print("="*80)


if __name__ == '__main__':
    main()
