#!/usr/bin/env python3
"""
Fetch analyst coverage and recommendations for all earnings dates.

For each (ticker, earnings_date) pair, fetches ACTUALLY AVAILABLE analyst data:
  - Number of analysts covering
  - Average analyst rating (Strong Buy to Strong Sell)
  - Current year EPS estimate
  - Forward EPS estimate
  - Analyst price targets (current, high, low, mean, median)
  - Recommendation counts (Strong Buy, Buy, Hold, Sell, Strong Sell)

This replaces the analyst revisions script which tried to fetch data
that yfinance doesn't provide for Swedish stocks.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime
import time


def create_analyst_coverage_table():
    """Create earnings_analyst_coverage table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_analyst_coverage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            num_analysts INTEGER,
            avg_rating REAL,
            rating_key TEXT,
            eps_current_year REAL,
            eps_forward REAL,
            target_price_current REAL,
            target_price_high REAL,
            target_price_low REAL,
            target_price_mean REAL,
            target_price_median REAL,
            upside_to_mean_target REAL,
            strong_buy_count INTEGER,
            buy_count INTEGER,
            hold_count INTEGER,
            sell_count INTEGER,
            strong_sell_count INTEGER,
            data_quality TEXT,
            fetch_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_analyst_coverage_ticker_date
        ON earnings_analyst_coverage(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified earnings_analyst_coverage table")


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


def fetch_analyst_coverage(ticker, earnings_date):
    """
    Fetch analyst coverage data that's actually available from yfinance.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Initialize result
        result = {
            'num_analysts': None,
            'avg_rating': None,
            'rating_key': None,
            'eps_current_year': None,
            'eps_forward': None,
            'target_price_current': None,
            'target_price_high': None,
            'target_price_low': None,
            'target_price_mean': None,
            'target_price_median': None,
            'upside_to_mean_target': None,
            'strong_buy_count': None,
            'buy_count': None,
            'hold_count': None,
            'sell_count': None,
            'strong_sell_count': None,
            'data_quality': 'missing',
            'fetch_error': None
        }

        has_data = False

        # Number of analysts
        if 'numberOfAnalystOpinions' in info and info['numberOfAnalystOpinions']:
            result['num_analysts'] = int(info['numberOfAnalystOpinions'])
            has_data = True

        # Average rating (0.0 = Strong Buy, 5.0 = Strong Sell)
        if 'recommendationMean' in info and info['recommendationMean'] is not None:
            result['avg_rating'] = float(info['recommendationMean'])
            has_data = True

        if 'recommendationKey' in info and info['recommendationKey']:
            result['rating_key'] = str(info['recommendationKey'])

        # EPS estimates
        if 'epsCurrentYear' in info and info['epsCurrentYear'] is not None:
            result['eps_current_year'] = float(info['epsCurrentYear'])
            has_data = True

        if 'epsForward' in info and info['epsForward'] is not None:
            result['eps_forward'] = float(info['epsForward'])
            has_data = True

        # Price targets
        try:
            targets = stock.analyst_price_targets
            if targets:
                result['target_price_current'] = float(targets.get('current', 0)) if targets.get('current') else None
                result['target_price_high'] = float(targets.get('high', 0)) if targets.get('high') else None
                result['target_price_low'] = float(targets.get('low', 0)) if targets.get('low') else None
                result['target_price_mean'] = float(targets.get('mean', 0)) if targets.get('mean') else None
                result['target_price_median'] = float(targets.get('median', 0)) if targets.get('median') else None

                # Calculate upside to mean target
                if result['target_price_mean'] and result['target_price_current']:
                    result['upside_to_mean_target'] = ((result['target_price_mean'] - result['target_price_current']) / result['target_price_current']) * 100

                has_data = True
        except:
            pass

        # Recommendation counts
        try:
            recs = stock.recommendations_summary
            if recs is not None and not recs.empty:
                # Get the most recent month (row 0)
                latest = recs.iloc[0]
                result['strong_buy_count'] = int(latest.get('strongBuy', 0)) if latest.get('strongBuy') is not None else 0
                result['buy_count'] = int(latest.get('buy', 0)) if latest.get('buy') is not None else 0
                result['hold_count'] = int(latest.get('hold', 0)) if latest.get('hold') is not None else 0
                result['sell_count'] = int(latest.get('sell', 0)) if latest.get('sell') is not None else 0
                result['strong_sell_count'] = int(latest.get('strongSell', 0)) if latest.get('strongSell') is not None else 0
                has_data = True
        except:
            pass

        if has_data:
            result['data_quality'] = 'found'
        else:
            result['fetch_error'] = 'No analyst coverage data available'

        return result

    except Exception as e:
        return {
            'num_analysts': None,
            'avg_rating': None,
            'rating_key': None,
            'eps_current_year': None,
            'eps_forward': None,
            'target_price_current': None,
            'target_price_high': None,
            'target_price_low': None,
            'target_price_mean': None,
            'target_price_median': None,
            'upside_to_mean_target': None,
            'strong_buy_count': None,
            'buy_count': None,
            'hold_count': None,
            'sell_count': None,
            'strong_sell_count': None,
            'data_quality': 'error',
            'fetch_error': str(e)
        }


def store_analyst_coverage(ticker, earnings_date, data):
    """Store analyst coverage in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_analyst_coverage
        (ticker, earnings_date, num_analysts, avg_rating, rating_key,
         eps_current_year, eps_forward,
         target_price_current, target_price_high, target_price_low,
         target_price_mean, target_price_median, upside_to_mean_target,
         strong_buy_count, buy_count, hold_count, sell_count, strong_sell_count,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['num_analysts'],
        data['avg_rating'],
        data['rating_key'],
        data['eps_current_year'],
        data['eps_forward'],
        data['target_price_current'],
        data['target_price_high'],
        data['target_price_low'],
        data['target_price_mean'],
        data['target_price_median'],
        data['upside_to_mean_target'],
        data['strong_buy_count'],
        data['buy_count'],
        data['hold_count'],
        data['sell_count'],
        data['strong_sell_count'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("=" * 80)
    print("FETCHING ANALYST COVERAGE DATA")
    print("=" * 80)
    print()
    print("Fetching ACTUALLY AVAILABLE analyst data:")
    print("  - Number of analysts covering")
    print("  - Average rating (Strong Buy to Strong Sell)")
    print("  - EPS estimates (current year, forward)")
    print("  - Price targets (high, low, mean, median)")
    print("  - Recommendation breakdown")
    print()

    # Create table
    create_analyst_coverage_table()

    # Get all earnings dates
    earnings_data = get_earnings_dates()
    total = len(earnings_data)

    print(f"Found {total} unique (ticker, earnings_date) combinations")
    print()

    # Process each ticker/date
    found_count = 0
    missing_count = 0
    error_count = 0

    # Track coverage levels
    coverage_counts = {
        '3+ analysts': 0,
        '1-2 analysts': 0,
        'No coverage': 0
    }

    for idx, (ticker, earnings_date) in enumerate(earnings_data, 1):
        print(f"[{idx}/{total}] {ticker} on {earnings_date}...", end=" ")

        # Fetch analyst coverage
        data = fetch_analyst_coverage(ticker, earnings_date)

        # Store in database
        store_analyst_coverage(ticker, earnings_date, data)

        # Report status
        if data['data_quality'] == 'found':
            num_analysts = data['num_analysts']
            rating = data['rating_key']
            eps_cy = data['eps_current_year']

            info_parts = []
            if num_analysts:
                info_parts.append(f"{num_analysts} analysts")
                if num_analysts >= 3:
                    coverage_counts['3+ analysts'] += 1
                elif num_analysts >= 1:
                    coverage_counts['1-2 analysts'] += 1
            else:
                coverage_counts['No coverage'] += 1

            if rating:
                info_parts.append(f"{rating}")
            if eps_cy is not None:
                info_parts.append(f"EPS: {eps_cy:.2f}")

            print(f"✓ {', '.join(info_parts) if info_parts else 'Partial data'}")
            found_count += 1
        elif data['data_quality'] == 'missing':
            print(f"⚠ No coverage")
            coverage_counts['No coverage'] += 1
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
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total processed: {total}")
    print(f"  ✓ Found data:    {found_count} ({found_count/total*100:.1f}%)")
    print(f"  ⚠ Missing data:  {missing_count} ({missing_count/total*100:.1f}%)")
    print(f"  ✗ Error:         {error_count} ({error_count/total*100:.1f}%)")
    print()

    if found_count > 0:
        print("ANALYST COVERAGE LEVELS:")
        for level, count in coverage_counts.items():
            pct = count / total * 100 if total > 0 else 0
            print(f"  {level:20s}: {count:3d} ({pct:5.1f}%)")
        print()

    print("KEY INSIGHTS:")
    print("  - Stocks with 3+ analysts tend to have more efficient pricing")
    print("  - Stocks with low/no coverage can have bigger earnings surprises")
    print("  - Analyst rating can indicate sentiment before earnings")
    print()
    print("Data stored in earnings_analyst_coverage table")
    print("=" * 80)


if __name__ == '__main__':
    main()
