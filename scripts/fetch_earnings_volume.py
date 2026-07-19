#!/usr/bin/env python3
"""
Calculate pre-earnings volume patterns for all earnings dates.

For each (ticker, earnings_date) pair, calculates:
  - avg_volume_20d: Average daily volume (last month)
  - avg_volume_60d: Average daily volume (last quarter)
  - avg_volume_252d: Average daily volume (last year)
  - day_before_volume: Actual volume on day before earnings
  - volume_trend_ratio: avg_volume_20d / avg_volume_252d

Volume metrics help identify:
  - Liquidity (can we trade this?)
  - Accumulation/distribution patterns
  - Unusual pre-earnings activity

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


def create_volume_table():
    """Create earnings_volume table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_volume (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            avg_volume_20d REAL,
            avg_volume_60d REAL,
            avg_volume_252d REAL,
            day_before_volume REAL,
            volume_trend_ratio REAL,
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
        CREATE INDEX IF NOT EXISTS idx_earnings_volume_ticker_date
        ON earnings_volume(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_volume table")


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


def calculate_volume_metrics(ticker, earnings_date):
    """
    Calculate pre-earnings volume metrics for a ticker on its earnings date.

    Returns dict with:
        - avg_volume_20d: Average volume last 20 trading days
        - avg_volume_60d: Average volume last 60 trading days
        - avg_volume_252d: Average volume last 252 trading days
        - day_before_volume: Volume on day before earnings
        - volume_trend_ratio: Recent vs long-term volume
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
                'avg_volume_20d': None,
                'avg_volume_60d': None,
                'avg_volume_252d': None,
                'day_before_volume': None,
                'volume_trend_ratio': None,
                'data_points_20d': 0,
                'data_points_60d': 0,
                'data_points_252d': 0,
                'data_quality': 'missing',
                'fetch_error': 'No historical data returned'
            }

        # Get volume data
        volumes = hist['Volume'].dropna()

        if len(volumes) < 2:
            return {
                'avg_volume_20d': None,
                'avg_volume_60d': None,
                'avg_volume_252d': None,
                'day_before_volume': None,
                'volume_trend_ratio': None,
                'data_points_20d': len(volumes),
                'data_points_60d': len(volumes),
                'data_points_252d': len(volumes),
                'data_quality': 'missing',
                'fetch_error': 'Insufficient data (< 2 days)'
            }

        # Day before earnings volume (last available data point)
        day_before_volume = float(volumes.iloc[-1])

        # Calculate average volume for each period
        def calc_avg_vol(period_days, min_required_days):
            """Calculate average volume for a period."""
            if len(volumes) < min_required_days:
                return None, len(volumes)

            # Use last N days
            period_volumes = volumes.iloc[-period_days:] if len(volumes) >= period_days else volumes

            # Average volume
            avg_vol = period_volumes.mean()

            return float(avg_vol), len(period_volumes)

        # Calculate for each period (require at least 75% of target days)
        avg_vol_20d, points_20d = calc_avg_vol(20, min_required_days=15)
        avg_vol_60d, points_60d = calc_avg_vol(60, min_required_days=45)
        avg_vol_252d, points_252d = calc_avg_vol(252, min_required_days=189)

        # Calculate volume trend ratio (recent vs baseline)
        volume_trend_ratio = None
        if avg_vol_20d is not None and avg_vol_252d is not None and avg_vol_252d > 0:
            volume_trend_ratio = avg_vol_20d / avg_vol_252d

        # Determine data quality
        if avg_vol_20d is not None and avg_vol_60d is not None and avg_vol_252d is not None:
            quality = 'full'
        elif avg_vol_20d is not None or avg_vol_60d is not None or avg_vol_252d is not None:
            quality = 'partial'
        else:
            quality = 'missing'

        return {
            'avg_volume_20d': avg_vol_20d,
            'avg_volume_60d': avg_vol_60d,
            'avg_volume_252d': avg_vol_252d,
            'day_before_volume': day_before_volume,
            'volume_trend_ratio': volume_trend_ratio,
            'data_points_20d': points_20d,
            'data_points_60d': points_60d,
            'data_points_252d': points_252d,
            'data_quality': quality,
            'fetch_error': None
        }

    except Exception as e:
        return {
            'avg_volume_20d': None,
            'avg_volume_60d': None,
            'avg_volume_252d': None,
            'day_before_volume': None,
            'volume_trend_ratio': None,
            'data_points_20d': 0,
            'data_points_60d': 0,
            'data_points_252d': 0,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_volume_metrics(ticker, earnings_date, data):
    """Store volume metrics in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_volume
        (ticker, earnings_date, avg_volume_20d, avg_volume_60d, avg_volume_252d,
         day_before_volume, volume_trend_ratio,
         data_points_20d, data_points_60d, data_points_252d,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['avg_volume_20d'],
        data['avg_volume_60d'],
        data['avg_volume_252d'],
        data['day_before_volume'],
        data['volume_trend_ratio'],
        data['data_points_20d'],
        data['data_points_60d'],
        data['data_points_252d'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def format_volume(vol):
    """Format volume for display."""
    if vol is None:
        return "N/A"
    if vol >= 1_000_000:
        return f"{vol/1_000_000:.1f}M"
    elif vol >= 1_000:
        return f"{vol/1_000:.1f}K"
    else:
        return f"{vol:.0f}"


def main():
    """Main execution."""
    print("="*80)
    print("CALCULATING PRE-EARNINGS VOLUME PATTERNS")
    print("="*80)
    print()
    print("Calculating average volume for:")
    print("  - 20 days (last month)")
    print("  - 60 days (last quarter)")
    print("  - 252 days (last year)")
    print("  - Day before earnings")
    print()

    # Create table
    create_volume_table()

    # Get all earnings dates
    earnings_data = get_earnings_dates()
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

        # Calculate volume metrics
        data = calculate_volume_metrics(ticker, earnings_date)

        # Store in database
        store_volume_metrics(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'full':
            vol_20 = data['avg_volume_20d']
            vol_252 = data['avg_volume_252d']
            ratio = data['volume_trend_ratio']
            day_before = data['day_before_volume']

            print(f"✓ Avg: {format_volume(vol_20)} / {format_volume(vol_252)} (ratio: {ratio:.2f}x, day-1: {format_volume(day_before)})")
            full_count += 1
        elif data['data_quality'] == 'partial':
            vols = []
            if data['avg_volume_20d'] is not None:
                vols.append(f"20d={format_volume(data['avg_volume_20d'])}")
            if data['avg_volume_60d'] is not None:
                vols.append(f"60d={format_volume(data['avg_volume_60d'])}")
            if data['avg_volume_252d'] is not None:
                vols.append(f"252d={format_volume(data['avg_volume_252d'])}")
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
    print("Data stored in earnings_volume table")
    print("="*80)


if __name__ == '__main__':
    main()
