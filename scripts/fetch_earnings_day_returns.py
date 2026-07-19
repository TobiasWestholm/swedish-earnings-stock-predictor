#!/usr/bin/env python3
"""
Fetch actual earnings day returns for all earnings dates.

For each (ticker, earnings_date) pair, fetches the actual price return
ON the earnings announcement day.

Calculates:
  - earnings_day_return: Percentage return from previous close to earnings day close
  - earnings_day_high: Highest percentage return during earnings day
  - earnings_day_low: Lowest percentage return during earnings day

This data is used to calculate historical earnings patterns.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd


def create_earnings_returns_table():
    """Create earnings_day_returns table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_day_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            prev_close REAL,
            earnings_close REAL,
            earnings_high REAL,
            earnings_low REAL,
            earnings_day_return REAL,
            earnings_day_high_pct REAL,
            earnings_day_low_pct REAL,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_day_returns_ticker_date
        ON earnings_day_returns(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_day_returns table")


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


def fetch_earnings_day_return(ticker, earnings_date):
    """
    Fetch earnings day return from yfinance.

    Returns the actual price movement on earnings day.
    """
    try:
        stock = yf.Ticker(ticker)
        earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')

        # Fetch 5 days around earnings to get prev close and earnings day data
        start_date = earnings_dt - timedelta(days=5)
        end_date = earnings_dt + timedelta(days=2)

        hist = stock.history(start=start_date, end=end_date, interval='1d')

        if hist.empty:
            return {
                'prev_close': None,
                'earnings_close': None,
                'earnings_high': None,
                'earnings_low': None,
                'earnings_day_return': None,
                'earnings_day_high_pct': None,
                'earnings_day_low_pct': None,
                'data_quality': 'missing',
                'fetch_error': 'No price data'
            }

        # Find the earnings day
        earnings_day_data = None
        prev_close = None

        for i, (date, row) in enumerate(hist.iterrows()):
            date_only = date.date()
            if date_only == earnings_dt.date():
                earnings_day_data = row
                # Get previous trading day close
                if i > 0:
                    prev_close = hist.iloc[i-1]['Close']
                break

        if earnings_day_data is None or prev_close is None:
            return {
                'prev_close': None,
                'earnings_close': None,
                'earnings_high': None,
                'earnings_low': None,
                'earnings_day_return': None,
                'earnings_day_high_pct': None,
                'earnings_day_low_pct': None,
                'data_quality': 'missing',
                'fetch_error': 'Earnings day not found in price data'
            }

        # Calculate returns
        earnings_close = float(earnings_day_data['Close'])
        earnings_high = float(earnings_day_data['High'])
        earnings_low = float(earnings_day_data['Low'])
        prev_close = float(prev_close)

        earnings_day_return = ((earnings_close - prev_close) / prev_close) * 100
        earnings_day_high_pct = ((earnings_high - prev_close) / prev_close) * 100
        earnings_day_low_pct = ((earnings_low - prev_close) / prev_close) * 100

        return {
            'prev_close': prev_close,
            'earnings_close': earnings_close,
            'earnings_high': earnings_high,
            'earnings_low': earnings_low,
            'earnings_day_return': earnings_day_return,
            'earnings_day_high_pct': earnings_day_high_pct,
            'earnings_day_low_pct': earnings_day_low_pct,
            'data_quality': 'found',
            'fetch_error': None
        }

    except Exception as e:
        return {
            'prev_close': None,
            'earnings_close': None,
            'earnings_high': None,
            'earnings_low': None,
            'earnings_day_return': None,
            'earnings_day_high_pct': None,
            'earnings_day_low_pct': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_earnings_day_return(ticker, earnings_date, data):
    """Store earnings day return in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_day_returns
        (ticker, earnings_date, prev_close, earnings_close,
         earnings_high, earnings_low, earnings_day_return,
         earnings_day_high_pct, earnings_day_low_pct,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['prev_close'],
        data['earnings_close'],
        data['earnings_high'],
        data['earnings_low'],
        data['earnings_day_return'],
        data['earnings_day_high_pct'],
        data['earnings_day_low_pct'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("="*80)
    print("FETCHING EARNINGS DAY RETURNS")
    print("="*80)
    print()
    print("Fetching actual price returns ON earnings announcement days")
    print()

    # Create table
    create_earnings_returns_table()

    # Get all earnings dates
    earnings_data = get_earnings_dates()
    total = len(earnings_data)

    print(f"Found {total} unique (ticker, earnings_date) combinations")
    print()

    # Process each ticker/date
    found_count = 0
    missing_count = 0
    error_count = 0

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] {ticker} on {earnings_date}...", end=" ")

        # Fetch earnings day return
        data = fetch_earnings_day_return(ticker, earnings_date)

        # Store in database
        store_earnings_day_return(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            ret = data['earnings_day_return']
            high = data['earnings_day_high_pct']
            low = data['earnings_day_low_pct']
            print(f"✓ Return: {ret:+.2f}% (Range: [{low:+.2f}%, {high:+.2f}%])")
            found_count += 1
        elif data['data_quality'] == 'missing':
            print(f"⚠ No data")
            missing_count += 1
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
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total processed: {total}")
    print(f"  ✓ Found data:   {found_count} ({found_count/total*100:.1f}%)")
    print(f"  ⚠ Missing data: {missing_count} ({missing_count/total*100:.1f}%)")
    print(f"  ✗ Error:        {error_count} ({error_count/total*100:.1f}%)")
    print()
    print("Data stored in earnings_day_returns table")
    print("="*80)


if __name__ == '__main__':
    main()
