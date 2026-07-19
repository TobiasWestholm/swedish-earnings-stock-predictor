#!/usr/bin/env python3
"""
Fetch 52-week position metrics for all earnings dates.

For each (ticker, earnings_date) pair, calculates where the stock price
is positioned relative to its 52-week high and low BEFORE the earnings announcement.

Calculates:
  - position_in_range: Where price is in 52-week range (0=at low, 1=at high)
  - distance_from_high_pct: How far below 52-week high (%)
  - distance_from_low_pct: How far above 52-week low (%)
  - weeks_since_high: Weeks since hitting 52-week high
  - weeks_since_low: Weeks since hitting 52-week low

Why this matters:
  - Stocks near 52-week highs have muted positive reactions (priced in)
  - Stocks near 52-week lows can have explosive moves (depressed expectations)
  - Research shows 52-week high stocks have ~30% lower earnings volatility
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd


def create_52week_position_table():
    """Create earnings_52week_position table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_52week_position (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            week_52_high REAL,
            week_52_low REAL,
            current_price REAL,
            position_in_range REAL,
            distance_from_high_pct REAL,
            distance_from_low_pct REAL,
            weeks_since_high REAL,
            weeks_since_low REAL,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_52week_position_ticker_date
        ON earnings_52week_position(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_52week_position table")


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


def fetch_52week_position(ticker, earnings_date):
    """
    Fetch 52-week position metrics for a ticker before earnings date.

    Uses historical data ending the day BEFORE earnings to avoid look-ahead bias.
    """
    try:
        stock = yf.Ticker(ticker)
        earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')

        # Fetch 1 year + 5 days of data ending DAY BEFORE earnings
        end_date = earnings_dt - timedelta(days=1)
        start_date = end_date - timedelta(days=370)  # ~1 year + buffer

        hist = stock.history(start=start_date, end=end_date, interval='1d')

        if hist.empty or len(hist) < 200:  # Need reasonable history
            return {
                'week_52_high': None,
                'week_52_low': None,
                'current_price': None,
                'position_in_range': None,
                'distance_from_high_pct': None,
                'distance_from_low_pct': None,
                'weeks_since_high': None,
                'weeks_since_low': None,
                'data_quality': 'insufficient_data',
                'fetch_error': f'Only {len(hist)} days of history available'
            }

        # Get 52-week high/low from the trailing 252 trading days (~1 year)
        prices = hist['Close'].tail(252)

        week_52_high = float(prices.max())
        week_52_low = float(prices.min())
        current_price = float(hist['Close'].iloc[-1])  # Day before earnings

        # Calculate position in range (0 = at low, 1 = at high)
        range_size = week_52_high - week_52_low
        if range_size > 0:
            position_in_range = (current_price - week_52_low) / range_size
        else:
            position_in_range = 0.5  # Flat line, neutral position

        # Distance from high/low in percentage
        distance_from_high_pct = ((week_52_high - current_price) / week_52_high) * 100
        distance_from_low_pct = ((current_price - week_52_low) / week_52_low) * 100

        # Find when 52-week high/low were hit
        high_dates = hist[hist['Close'] >= week_52_high * 0.9999].index  # Account for floating point
        low_dates = hist[hist['Close'] <= week_52_low * 1.0001].index

        weeks_since_high = None
        weeks_since_low = None

        if len(high_dates) > 0:
            days_since_high = (hist.index[-1] - high_dates[-1]).days
            weeks_since_high = days_since_high / 7.0

        if len(low_dates) > 0:
            days_since_low = (hist.index[-1] - low_dates[-1]).days
            weeks_since_low = days_since_low / 7.0

        return {
            'week_52_high': week_52_high,
            'week_52_low': week_52_low,
            'current_price': current_price,
            'position_in_range': position_in_range,
            'distance_from_high_pct': distance_from_high_pct,
            'distance_from_low_pct': distance_from_low_pct,
            'weeks_since_high': weeks_since_high,
            'weeks_since_low': weeks_since_low,
            'data_quality': 'found',
            'fetch_error': None
        }

    except Exception as e:
        return {
            'week_52_high': None,
            'week_52_low': None,
            'current_price': None,
            'position_in_range': None,
            'distance_from_high_pct': None,
            'distance_from_low_pct': None,
            'weeks_since_high': None,
            'weeks_since_low': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_52week_position(ticker, earnings_date, data):
    """Store 52-week position in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_52week_position
        (ticker, earnings_date, week_52_high, week_52_low, current_price,
         position_in_range, distance_from_high_pct, distance_from_low_pct,
         weeks_since_high, weeks_since_low, data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['week_52_high'],
        data['week_52_low'],
        data['current_price'],
        data['position_in_range'],
        data['distance_from_high_pct'],
        data['distance_from_low_pct'],
        data['weeks_since_high'],
        data['weeks_since_low'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Fetch 52-week position metrics')
    parser.add_argument('--date', type=str, help='Fetch only for this date (YYYY-MM-DD)')
    parser.add_argument('--tickers', type=str, help='Comma-separated tickers to fetch')
    args = parser.parse_args()

    print("=" * 80)
    print("FETCHING 52-WEEK POSITION METRICS")
    print("=" * 80)
    print()
    print("For each earnings date, calculating where stock price is positioned")
    print("relative to its 52-week high and low (day before earnings).")
    print()

    # Create table
    create_52week_position_table()

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
    insufficient_count = 0
    error_count = 0

    # Track distribution
    near_high_count = 0  # >90% of range
    near_low_count = 0   # <10% of range
    mid_range_count = 0  # 40-60% of range

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] {ticker} on {earnings_date}...", end=" ")

        # Fetch 52-week position
        data = fetch_52week_position(ticker, earnings_date)

        # Store in database
        store_52week_position(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            pos = data['position_in_range']
            dist_high = data['distance_from_high_pct']
            dist_low = data['distance_from_low_pct']

            position_label = ""
            if pos >= 0.9:
                position_label = "🔴 NEAR HIGH"
                near_high_count += 1
            elif pos <= 0.1:
                position_label = "🟢 NEAR LOW"
                near_low_count += 1
            elif 0.4 <= pos <= 0.6:
                position_label = "🟡 MID-RANGE"
                mid_range_count += 1
            else:
                position_label = "⚪ NEUTRAL"

            print(f"✓ Position: {pos:.1%} {position_label} (High: -{dist_high:.1f}%, Low: +{dist_low:.1f}%)")
            found_count += 1
        elif data['data_quality'] == 'insufficient_data':
            print(f"⚠ {data.get('fetch_error', 'Insufficient data')}")
            insufficient_count += 1
        else:
            print(f"✗ {data.get('fetch_error', 'Error')}")
            error_count += 1

        # Rate limiting
        if idx % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.2)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total processed: {total}")
    print(f"  ✓ Found data:         {found_count} ({found_count/total*100:.1f}%)")
    print(f"  ⚠ Insufficient data:  {insufficient_count} ({insufficient_count/total*100:.1f}%)")
    print(f"  ✗ Error:              {error_count} ({error_count/total*100:.1f}%)")
    print()

    if found_count > 0:
        print("POSITION DISTRIBUTION:")
        print(f"  🔴 Near 52-week high (>90%): {near_high_count} ({near_high_count/found_count*100:.1f}%)")
        print(f"  🟢 Near 52-week low (<10%):  {near_low_count} ({near_low_count/found_count*100:.1f}%)")
        print(f"  🟡 Mid-range (40-60%):       {mid_range_count} ({mid_range_count/found_count*100:.1f}%)")
        print()
        print("KEY INSIGHTS:")
        print("  - Stocks near 52-week highs tend to have muted positive reactions")
        print("  - Stocks near 52-week lows can have explosive moves")
        print("  - Consider filtering out stocks >95% of range (limited upside)")
        print()

    print("Data stored in earnings_52week_position table")
    print("=" * 80)


if __name__ == '__main__':
    main()
