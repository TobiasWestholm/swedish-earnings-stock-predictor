#!/usr/bin/env python3
"""
Fetch historical fundamental metrics for all tickers on their earnings dates.

For each (ticker, earnings_date) pair, calculates:
  - yesterday_close: Closing price on the trading day before earnings
  - return_1m: 1-month return percentage (30 days ago to yesterday)
  - return_3m: 3-month return percentage (90 days ago to yesterday)
  - return_1y: 1-year return percentage (252 days ago to yesterday)
  - sma_200: 200-day simple moving average as of yesterday

Uses yfinance to fetch historical data with appropriate lookback periods.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd


def create_fundamentals_table():
    """Create earnings_fundamentals table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_fundamentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            yesterday_close REAL,
            return_1m REAL,
            return_3m REAL,
            return_1y REAL,
            sma_200 REAL,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_fundamentals_ticker_date
        ON earnings_fundamentals(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_fundamentals table")


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


def calculate_metrics(ticker, earnings_date):
    """
    Calculate fundamental metrics for a ticker on its earnings date.

    Returns dict with:
        - yesterday_close
        - return_1m
        - return_3m
        - return_1y
        - sma_200
        - data_quality (full/partial/missing)
        - fetch_error (if any)
    """
    try:
        # Parse earnings date
        earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')

        # We need data up to the day before earnings
        # Fetch extra buffer to handle weekends/holidays
        lookback_days = 400  # ~1.5 years to ensure we get 252 trading days
        start_date = earnings_dt - timedelta(days=lookback_days)
        end_date = earnings_dt  # yfinance end is exclusive, so this gets us up to day before

        # Fetch historical data
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date, interval='1d')

        if hist.empty:
            return {
                'yesterday_close': None,
                'return_1m': None,
                'return_3m': None,
                'return_1y': None,
                'sma_200': None,
                'data_quality': 'missing',
                'fetch_error': 'No historical data returned'
            }

        # Get closing prices
        closes = hist['Close'].dropna()

        if len(closes) == 0:
            return {
                'yesterday_close': None,
                'return_1m': None,
                'return_3m': None,
                'return_1y': None,
                'sma_200': None,
                'data_quality': 'missing',
                'fetch_error': 'No closing prices available'
            }

        # Yesterday's close (last available price before earnings)
        yesterday_close = float(closes.iloc[-1])

        # Calculate returns
        def calculate_return(days_back):
            """Calculate return from N trading days ago to yesterday."""
            if len(closes) < days_back + 1:
                return None
            past_price = float(closes.iloc[-(days_back + 1)])
            return ((yesterday_close - past_price) / past_price) * 100

        return_1m = calculate_return(21)   # ~1 month (21 trading days)
        return_3m = calculate_return(63)   # ~3 months (63 trading days)
        return_1y = calculate_return(252)  # ~1 year (252 trading days)

        # Calculate 200-day SMA
        if len(closes) >= 200:
            sma_200 = float(closes.iloc[-200:].mean())
        else:
            sma_200 = None

        # Determine data quality
        if all(v is not None for v in [return_1m, return_3m, return_1y, sma_200]):
            quality = 'full'
        elif yesterday_close is not None:
            quality = 'partial'
        else:
            quality = 'missing'

        return {
            'yesterday_close': yesterday_close,
            'return_1m': return_1m,
            'return_3m': return_3m,
            'return_1y': return_1y,
            'sma_200': sma_200,
            'data_quality': quality,
            'fetch_error': None
        }

    except Exception as e:
        return {
            'yesterday_close': None,
            'return_1m': None,
            'return_3m': None,
            'return_1y': None,
            'sma_200': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_metrics(ticker, earnings_date, metrics):
    """Store calculated metrics in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_fundamentals
        (ticker, earnings_date, yesterday_close, return_1m, return_3m, return_1y,
         sma_200, data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        metrics['yesterday_close'],
        metrics['return_1m'],
        metrics['return_3m'],
        metrics['return_1y'],
        metrics['sma_200'],
        metrics['data_quality'],
        metrics['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("="*80)
    print("FETCHING HISTORICAL FUNDAMENTALS FOR EARNINGS TICKERS")
    print("="*80)
    print()

    # Create table
    create_fundamentals_table()

    # Get all earnings dates
    earnings_data = get_earnings_dates()
    total = len(earnings_data)

    print(f"Found {total} unique (ticker, earnings_date) combinations")
    print()

    # Process each ticker/date
    success_count = 0
    partial_count = 0
    error_count = 0

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] Processing {ticker} on {earnings_date}...", end=" ")

        # Calculate metrics
        metrics = calculate_metrics(ticker, earnings_date)

        # Store in database
        store_metrics(ticker, earnings_date, metrics)

        # Report status
        if metrics['data_quality'] == 'full':
            print(f"✓ Full data")
            success_count += 1
        elif metrics['data_quality'] == 'partial':
            print(f"⚠ Partial data")
            partial_count += 1
        else:
            print(f"✗ {metrics.get('fetch_error', 'Failed')}")
            error_count += 1

        # Rate limiting - be nice to yfinance
        if idx % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.1)

    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total processed: {total}")
    print(f"  ✓ Full data:    {success_count} ({success_count/total*100:.1f}%)")
    print(f"  ⚠ Partial data: {partial_count} ({partial_count/total*100:.1f}%)")
    print(f"  ✗ Failed:       {error_count} ({error_count/total*100:.1f}%)")
    print()
    print("Data stored in earnings_fundamentals table")
    print("="*80)


if __name__ == '__main__':
    main()
