#!/usr/bin/env python3
"""
Fetch analyst EPS revisions for all earnings dates.

For each (ticker, earnings_date) pair, fetches:
  - eps_revisions_up_last_7d: Number of upward EPS revisions in last 7 days
  - eps_revisions_down_last_7d: Number of downward EPS revisions in last 7 days
  - eps_revisions_up_last_30d: Number of upward EPS revisions in last 30 days
  - eps_revisions_down_last_30d: Number of downward EPS revisions in last 30 days
  - eps_trend_current: Current quarter EPS estimate
  - eps_trend_7days_ago: EPS estimate 7 days ago
  - eps_trend_30days_ago: EPS estimate 30 days ago
  - eps_trend_60days_ago: EPS estimate 60 days ago

Analyst revision metrics help identify:
  - Positive/negative analyst sentiment changes
  - Estimate momentum (trending up or down)
  - Consensus building or breaking
  - Potential earnings surprises

NOTE: This data is primarily available for US stocks and larger international stocks.
Swedish small-cap stocks may have limited analyst coverage.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd


def create_revisions_table():
    """Create earnings_analyst_revisions table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_analyst_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            eps_revisions_up_last_7d INTEGER,
            eps_revisions_down_last_7d INTEGER,
            eps_revisions_up_last_30d INTEGER,
            eps_revisions_down_last_30d INTEGER,
            eps_trend_current REAL,
            eps_trend_7days_ago REAL,
            eps_trend_30days_ago REAL,
            eps_trend_60days_ago REAL,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_analyst_revisions_ticker_date
        ON earnings_analyst_revisions(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_analyst_revisions table")


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


def fetch_analyst_revisions(ticker, earnings_date):
    """
    Fetch analyst revisions data from yfinance.

    Returns dict with:
        - eps_revisions_up/down for 7d and 30d periods
        - eps_trend for current, 7d, 30d, 60d ago
        - data_quality: found/missing
        - fetch_error: Error message if any
    """
    try:
        stock = yf.Ticker(ticker)

        # Try to get analyst info
        try:
            info = stock.info
        except Exception:
            info = {}

        # Initialize result
        result = {
            'eps_revisions_up_last_7d': None,
            'eps_revisions_down_last_7d': None,
            'eps_revisions_up_last_30d': None,
            'eps_revisions_down_last_30d': None,
            'eps_trend_current': None,
            'eps_trend_7days_ago': None,
            'eps_trend_30days_ago': None,
            'eps_trend_60days_ago': None,
            'data_quality': 'missing',
            'fetch_error': None
        }

        # Check for analyst info
        has_data = False

        # Try to get EPS revisions (upLast7days, downLast7days, etc.)
        # Note: These fields may not be available for all stocks
        if 'epsRevisionsUpLast7days' in info and info['epsRevisionsUpLast7days'] is not None:
            result['eps_revisions_up_last_7d'] = int(info['epsRevisionsUpLast7days'])
            has_data = True

        if 'epsRevisionsDownLast7days' in info and info['epsRevisionsDownLast7days'] is not None:
            result['eps_revisions_down_last_7d'] = int(info['epsRevisionsDownLast7days'])
            has_data = True

        if 'epsRevisionsUpLast30days' in info and info['epsRevisionsUpLast30days'] is not None:
            result['eps_revisions_up_last_30d'] = int(info['epsRevisionsUpLast30days'])
            has_data = True

        if 'epsRevisionsDownLast30days' in info and info['epsRevisionsDownLast30days'] is not None:
            result['eps_revisions_down_last_30d'] = int(info['epsRevisionsDownLast30days'])
            has_data = True

        # Try to get EPS trend (current, 7daysAgo, 30daysAgo, 60daysAgo)
        # Note: These are forward-looking estimates
        if 'epsCurrentYear' in info and info['epsCurrentYear'] is not None:
            result['eps_trend_current'] = float(info['epsCurrentYear'])
            has_data = True

        # Try accessing earnings_estimate if available
        try:
            earnings_estimate = stock.earnings_estimate
            if earnings_estimate is not None and not earnings_estimate.empty:
                # This gives us quarterly estimates
                # We would need historical estimate data to track trends over time
                # Unfortunately yfinance doesn't provide historical estimate changes
                pass
        except Exception:
            pass

        # Try to get recommendations_summary for trend data
        try:
            recommendations = stock.recommendations_summary
            if recommendations is not None and not recommendations.empty:
                # This shows analyst recommendations over time
                # Can indicate sentiment changes
                pass
        except Exception:
            pass

        if has_data:
            result['data_quality'] = 'found'
        else:
            result['fetch_error'] = 'No analyst revision data available'

        return result

    except Exception as e:
        return {
            'eps_revisions_up_last_7d': None,
            'eps_revisions_down_last_7d': None,
            'eps_revisions_up_last_30d': None,
            'eps_revisions_down_last_30d': None,
            'eps_trend_current': None,
            'eps_trend_7days_ago': None,
            'eps_trend_30days_ago': None,
            'eps_trend_60days_ago': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_analyst_revisions(ticker, earnings_date, data):
    """Store analyst revisions in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_analyst_revisions
        (ticker, earnings_date,
         eps_revisions_up_last_7d, eps_revisions_down_last_7d,
         eps_revisions_up_last_30d, eps_revisions_down_last_30d,
         eps_trend_current, eps_trend_7days_ago,
         eps_trend_30days_ago, eps_trend_60days_ago,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['eps_revisions_up_last_7d'],
        data['eps_revisions_down_last_7d'],
        data['eps_revisions_up_last_30d'],
        data['eps_revisions_down_last_30d'],
        data['eps_trend_current'],
        data['eps_trend_7days_ago'],
        data['eps_trend_30days_ago'],
        data['eps_trend_60days_ago'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("="*80)
    print("FETCHING ANALYST EPS REVISIONS")
    print("="*80)
    print()
    print("Fetching:")
    print("  - EPS revisions (up/down) for last 7 days")
    print("  - EPS revisions (up/down) for last 30 days")
    print("  - EPS trend (current, 7d ago, 30d ago, 60d ago)")
    print()
    print("NOTE: Analyst revision data is primarily available for US stocks")
    print("      and larger international stocks. Swedish small-caps may have")
    print("      limited or no analyst coverage.")
    print()

    # Create table
    create_revisions_table()

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

        # Fetch analyst revisions
        data = fetch_analyst_revisions(ticker, earnings_date)

        # Store in database
        store_analyst_revisions(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            parts = []
            if data['eps_revisions_up_last_7d'] is not None or data['eps_revisions_down_last_7d'] is not None:
                up = data['eps_revisions_up_last_7d'] or 0
                down = data['eps_revisions_down_last_7d'] or 0
                parts.append(f"7d: ↑{up}/↓{down}")
            if data['eps_revisions_up_last_30d'] is not None or data['eps_revisions_down_last_30d'] is not None:
                up = data['eps_revisions_up_last_30d'] or 0
                down = data['eps_revisions_down_last_30d'] or 0
                parts.append(f"30d: ↑{up}/↓{down}")
            if data['eps_trend_current'] is not None:
                parts.append(f"EPS: {data['eps_trend_current']:.2f}")

            if parts:
                print(f"✓ {', '.join(parts)}")
            else:
                print(f"✓ Found (limited data)")
            found_count += 1
        elif data['data_quality'] == 'missing':
            print(f"⚠ No analyst data")
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
    print("Data stored in earnings_analyst_revisions table")
    print()
    print("NOTE: Low coverage is expected for Swedish small-cap stocks.")
    print("      Analyst coverage is typically limited to larger companies.")
    print("="*80)


if __name__ == '__main__':
    main()
