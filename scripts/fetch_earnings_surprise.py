#!/usr/bin/env python3
"""
Fetch earnings surprise data (Actual EPS vs Analyst Consensus) for all earnings dates.

For each (ticker, earnings_date) pair, fetches:
  - eps_actual: Actual reported EPS
  - eps_estimate: Analyst consensus estimate
  - eps_difference: Actual - Estimate
  - surprise_percent: (Actual - Estimate) / |Estimate| * 100

Uses yfinance ticker.earnings_history API.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd


def create_earnings_surprise_table():
    """Create earnings_surprise table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_surprise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            eps_actual REAL,
            eps_estimate REAL,
            eps_difference REAL,
            surprise_percent REAL,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_surprise_ticker_date
        ON earnings_surprise(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_surprise table")


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


def fetch_earnings_surprise(ticker, earnings_date):
    """
    Fetch earnings surprise data for a specific ticker and date.

    Returns dict with:
        - eps_actual
        - eps_estimate
        - eps_difference
        - surprise_percent
        - data_quality (found/missing/error)
        - fetch_error (if any)
    """
    try:
        # Parse earnings date
        target_date = datetime.strptime(earnings_date, '%Y-%m-%d')

        # Fetch ticker data
        stock = yf.Ticker(ticker)

        # Try earnings_history first (more recent data)
        earnings_hist = stock.earnings_history

        if earnings_hist is not None and not earnings_hist.empty:
            # earnings_history has quarters as index
            # Try to find matching quarter
            for quarter, row in earnings_hist.iterrows():
                # quarters are like '2025-03-31', compare to our earnings_date
                quarter_date = pd.to_datetime(quarter)

                # Check if within same quarter (allow ±45 days)
                if abs((quarter_date - target_date).days) <= 45:
                    return {
                        'eps_actual': float(row['epsActual']) if pd.notna(row['epsActual']) else None,
                        'eps_estimate': float(row['epsEstimate']) if pd.notna(row['epsEstimate']) else None,
                        'eps_difference': float(row['epsDifference']) if pd.notna(row['epsDifference']) else None,
                        'surprise_percent': float(row['surprisePercent']) * 100 if pd.notna(row['surprisePercent']) else None,  # Convert to percentage
                        'data_quality': 'found',
                        'fetch_error': None
                    }

        # Try earnings_dates (historical earnings with dates)
        earnings_dates = stock.earnings_dates

        if earnings_dates is not None and not earnings_dates.empty:
            # earnings_dates has actual earnings dates as index
            for date_idx, row in earnings_dates.iterrows():
                # date_idx is a Timestamp with timezone
                report_date = pd.to_datetime(date_idx).tz_localize(None)

                # Check if dates match (within 7 days to account for timezone/reporting differences)
                if abs((report_date.date() - target_date.date()).days) <= 7:
                    eps_actual = float(row['Reported EPS']) if pd.notna(row['Reported EPS']) else None
                    eps_estimate = float(row['EPS Estimate']) if pd.notna(row['EPS Estimate']) else None
                    surprise_pct = float(row['Surprise(%)']) if pd.notna(row['Surprise(%)']) else None

                    # Calculate difference if we have both values
                    eps_diff = None
                    if eps_actual is not None and eps_estimate is not None:
                        eps_diff = eps_actual - eps_estimate

                    return {
                        'eps_actual': eps_actual,
                        'eps_estimate': eps_estimate,
                        'eps_difference': eps_diff,
                        'surprise_percent': surprise_pct,
                        'data_quality': 'found',
                        'fetch_error': None
                    }

        # No matching earnings found
        return {
            'eps_actual': None,
            'eps_estimate': None,
            'eps_difference': None,
            'surprise_percent': None,
            'data_quality': 'missing',
            'fetch_error': 'No matching earnings data found'
        }

    except Exception as e:
        return {
            'eps_actual': None,
            'eps_estimate': None,
            'eps_difference': None,
            'surprise_percent': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_earnings_surprise(ticker, earnings_date, data):
    """Store earnings surprise data in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_surprise
        (ticker, earnings_date, eps_actual, eps_estimate, eps_difference,
         surprise_percent, data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['eps_actual'],
        data['eps_estimate'],
        data['eps_difference'],
        data['surprise_percent'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("="*80)
    print("FETCHING EARNINGS SURPRISE DATA (EPS ACTUAL VS ESTIMATE)")
    print("="*80)
    print()

    # Create table
    create_earnings_surprise_table()

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

        # Fetch earnings surprise data
        data = fetch_earnings_surprise(ticker, earnings_date)

        # Store in database
        store_earnings_surprise(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            actual = data['eps_actual']
            estimate = data['eps_estimate']
            surprise = data['surprise_percent']

            if surprise is not None:
                print(f"✓ EPS: {actual:.2f} vs {estimate:.2f} ({surprise:+.1f}%)")
            elif actual is not None and estimate is not None:
                print(f"✓ EPS: {actual:.2f} vs {estimate:.2f}")
            elif actual is not None:
                print(f"✓ EPS: {actual:.2f} (no estimate)")
            else:
                print(f"✓ Found (partial data)")
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
    print(f"  ✓ Found:   {found_count} ({found_count/total*100:.1f}%)")
    print(f"  ⚠ Missing: {missing_count} ({missing_count/total*100:.1f}%)")
    print(f"  ✗ Error:   {error_count} ({error_count/total*100:.1f}%)")
    print()
    print("Data stored in earnings_surprise table")
    print("="*80)


if __name__ == '__main__':
    main()
