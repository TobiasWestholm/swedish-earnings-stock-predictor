#!/usr/bin/env python3
"""
Calculate pre-earnings historical volatility for all earnings dates.

For each (ticker, earnings_date) pair, calculates:
  - volatility_20d: 20-day annualized volatility (last month)
  - volatility_60d: 60-day annualized volatility (last quarter)
  - volatility_252d: 252-day annualized volatility (last year)

Volatility = standard deviation of daily returns, annualized.
Formula: std(returns) * sqrt(252)

IMPORTANT: Uses only data BEFORE earnings_date to avoid look-ahead bias.
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


def create_volatility_table():
    """Create earnings_volatility table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_volatility (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            volatility_20d REAL,
            volatility_60d REAL,
            volatility_252d REAL,
            data_points_20d INTEGER,
            data_points_60d INTEGER,
            data_points_252d INTEGER,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_volatility_ticker_date
        ON earnings_volatility(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_volatility table")


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


def calculate_volatility(ticker, earnings_date):
    """
    Calculate pre-earnings volatility for a ticker on its earnings date.

    Returns dict with:
        - volatility_20d: 20-day annualized volatility
        - volatility_60d: 60-day annualized volatility
        - volatility_252d: 252-day annualized volatility
        - data_points_20d/60d/252d: Actual number of trading days used
        - data_quality: full/partial/missing
        - fetch_error: Error message if any
    """
    try:
        # Parse earnings date
        earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')

        # We need data UP TO (but NOT including) earnings_date
        # Fetch extra buffer to handle weekends/holidays
        lookback_days = 400  # ~1.5 years calendar days to ensure 252 trading days
        start_date = earnings_dt - timedelta(days=lookback_days)
        end_date = earnings_dt  # yfinance end is exclusive, so this gets us up to day before

        # Fetch historical data
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date, interval='1d')

        if hist.empty:
            return {
                'volatility_20d': None,
                'volatility_60d': None,
                'volatility_252d': None,
                'data_points_20d': 0,
                'data_points_60d': 0,
                'data_points_252d': 0,
                'data_quality': 'missing',
                'fetch_error': 'No historical data returned'
            }

        # Get closing prices
        closes = hist['Close'].dropna()

        if len(closes) < 2:
            return {
                'volatility_20d': None,
                'volatility_60d': None,
                'volatility_252d': None,
                'data_points_20d': len(closes),
                'data_points_60d': len(closes),
                'data_points_252d': len(closes),
                'data_quality': 'missing',
                'fetch_error': 'Insufficient data (< 2 days)'
            }

        # Calculate daily returns: (price[t] - price[t-1]) / price[t-1]
        returns = closes.pct_change().dropna()

        if len(returns) == 0:
            return {
                'volatility_20d': None,
                'volatility_60d': None,
                'volatility_252d': None,
                'data_points_20d': 0,
                'data_points_60d': 0,
                'data_points_252d': 0,
                'data_quality': 'missing',
                'fetch_error': 'Could not calculate returns'
            }

        # Calculate volatility for each period
        def calc_vol(period_days, min_required_days):
            """Calculate annualized volatility for a period."""
            if len(returns) < min_required_days:
                return None, len(returns)

            # Use last N returns
            period_returns = returns.iloc[-period_days:] if len(returns) >= period_days else returns

            # Standard deviation of returns
            std_dev = period_returns.std()

            # Annualize: multiply by sqrt(252 trading days)
            annualized_vol = std_dev * np.sqrt(252)

            return float(annualized_vol), len(period_returns)

        # Calculate for each period (require at least 75% of target days)
        vol_20d, points_20d = calc_vol(20, min_required_days=15)
        vol_60d, points_60d = calc_vol(60, min_required_days=45)
        vol_252d, points_252d = calc_vol(252, min_required_days=189)

        # Determine data quality
        if vol_20d is not None and vol_60d is not None and vol_252d is not None:
            quality = 'full'
        elif vol_20d is not None or vol_60d is not None or vol_252d is not None:
            quality = 'partial'
        else:
            quality = 'missing'

        return {
            'volatility_20d': vol_20d,
            'volatility_60d': vol_60d,
            'volatility_252d': vol_252d,
            'data_points_20d': points_20d,
            'data_points_60d': points_60d,
            'data_points_252d': points_252d,
            'data_quality': quality,
            'fetch_error': None
        }

    except Exception as e:
        return {
            'volatility_20d': None,
            'volatility_60d': None,
            'volatility_252d': None,
            'data_points_20d': 0,
            'data_points_60d': 0,
            'data_points_252d': 0,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_volatility(ticker, earnings_date, data):
    """Store volatility data in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_volatility
        (ticker, earnings_date, volatility_20d, volatility_60d, volatility_252d,
         data_points_20d, data_points_60d, data_points_252d,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['volatility_20d'],
        data['volatility_60d'],
        data['volatility_252d'],
        data['data_points_20d'],
        data['data_points_60d'],
        data['data_points_252d'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Calculate pre-earnings historical volatility')
    parser.add_argument('--date', type=str, help='Fetch only for this date (YYYY-MM-DD)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers to fetch')
    args = parser.parse_args()

    print("="*80)
    print("CALCULATING PRE-EARNINGS HISTORICAL VOLATILITY")
    print("="*80)
    print()
    print("Calculating annualized volatility for:")
    print("  - 20 days (last month)")
    print("  - 60 days (last quarter)")
    print("  - 252 days (last year)")
    print()

    # Create table
    create_volatility_table()

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
    full_count = 0
    partial_count = 0
    missing_count = 0
    error_count = 0

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] {ticker} on {earnings_date}...", end=" ")

        # Calculate volatility
        data = calculate_volatility(ticker, earnings_date)

        # Store in database
        store_volatility(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'full':
            vol_20 = data['volatility_20d']
            vol_60 = data['volatility_60d']
            vol_252 = data['volatility_252d']
            print(f"✓ Vol: {vol_20*100:.1f}% / {vol_60*100:.1f}% / {vol_252*100:.1f}%")
            full_count += 1
        elif data['data_quality'] == 'partial':
            vols = []
            if data['volatility_20d'] is not None:
                vols.append(f"20d={data['volatility_20d']*100:.1f}%")
            if data['volatility_60d'] is not None:
                vols.append(f"60d={data['volatility_60d']*100:.1f}%")
            if data['volatility_252d'] is not None:
                vols.append(f"252d={data['volatility_252d']*100:.1f}%")
            print(f"⚠ Partial: {', '.join(vols)}")
            partial_count += 1
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
    print(f"  ✓ Full data:    {full_count} ({full_count/total*100:.1f}%)")
    print(f"  ⚠ Partial data: {partial_count} ({partial_count/total*100:.1f}%)")
    print(f"  ⚠ Missing data: {missing_count} ({missing_count/total*100:.1f}%)")
    print(f"  ✗ Error:        {error_count} ({error_count/total*100:.1f}%)")
    print()
    print("Data stored in earnings_volatility table")
    print("="*80)


if __name__ == '__main__':
    main()
