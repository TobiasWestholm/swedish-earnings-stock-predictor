#!/usr/bin/env python3
"""
Calculate historical earnings day patterns for each ticker.

For each ticker, analyzes past earnings announcements to identify:
  - avg_abs_return: Average absolute return on earnings days (typical magnitude)
  - std_return: Standard deviation of earnings day returns (consistency)
  - max_positive_return: Largest positive earnings move
  - max_negative_return: Largest negative earnings move
  - positive_count: Number of positive earnings days
  - negative_count: Number of negative earnings days
  - win_rate: Percentage of positive earnings days
  - directional_consistency: Measure of consistent direction (0-1)
  - earnings_count: Total number of historical earnings events

These metrics identify "high-reaction" vs "low-reaction" stocks and
help predict future earnings day behavior based on historical patterns.

IMPORTANT: For each earnings date, only uses PRIOR earnings to avoid look-ahead.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import pandas as pd
import numpy as np


def create_patterns_table():
    """Create historical_earnings_patterns table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_earnings_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            avg_abs_return REAL,
            std_return REAL,
            max_positive_return REAL,
            max_negative_return REAL,
            positive_count INTEGER,
            negative_count INTEGER,
            win_rate REAL,
            directional_consistency REAL,
            earnings_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_historical_earnings_patterns_ticker_date
        ON historical_earnings_patterns(ticker, earnings_date)
    """)

    conn.commit()
    conn.close()
    print("✓ Created/verified historical_earnings_patterns table")


def get_all_earnings_data():
    """Get all earnings data ordered by ticker and date."""
    conn = get_connection()
    cursor = conn.cursor()

    # Get earnings day returns from the earnings_day_returns table
    cursor.execute("""
        SELECT
            ticker,
            earnings_date,
            earnings_day_return
        FROM earnings_day_returns
        WHERE earnings_day_return IS NOT NULL
        ORDER BY ticker, earnings_date
    """)

    results = cursor.fetchall()
    conn.close()

    return results


def calculate_historical_patterns(ticker, current_earnings_date, historical_returns):
    """
    Calculate historical earnings patterns for a ticker up to (but not including) current_earnings_date.

    Args:
        ticker: Stock ticker
        current_earnings_date: The earnings date we're analyzing
        historical_returns: List of (earnings_date, day_return) tuples for this ticker

    Returns:
        Dict with historical pattern metrics
    """
    if len(historical_returns) < 2:
        # Need at least 2 historical earnings to calculate patterns
        return {
            'avg_abs_return': None,
            'std_return': None,
            'max_positive_return': None,
            'max_negative_return': None,
            'positive_count': 0,
            'negative_count': 0,
            'win_rate': None,
            'directional_consistency': None,
            'earnings_count': len(historical_returns)
        }

    returns = np.array(historical_returns)

    # Average absolute return (typical magnitude)
    avg_abs_return = float(np.abs(returns).mean())

    # Standard deviation (consistency/volatility)
    std_return = float(returns.std())

    # Max positive and negative moves
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]

    max_positive = float(positive_returns.max()) if len(positive_returns) > 0 else 0.0
    max_negative = float(negative_returns.min()) if len(negative_returns) > 0 else 0.0

    # Count of positive vs negative
    positive_count = int((returns > 0).sum())
    negative_count = int((returns < 0).sum())

    # Win rate
    win_rate = float(positive_count / len(returns))

    # Directional consistency (0 = random, 1 = always same direction)
    # Measured as abs(win_rate - 0.5) * 2
    # 0% or 100% wins = 1.0 consistency
    # 50% wins = 0.0 consistency (random)
    directional_consistency = abs(win_rate - 0.5) * 2.0

    return {
        'avg_abs_return': avg_abs_return,
        'std_return': std_return,
        'max_positive_return': max_positive,
        'max_negative_return': max_negative,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'win_rate': win_rate,
        'directional_consistency': directional_consistency,
        'earnings_count': len(returns)
    }


def store_patterns(ticker, earnings_date, data):
    """Store historical patterns in database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO historical_earnings_patterns
        (ticker, earnings_date, avg_abs_return, std_return,
         max_positive_return, max_negative_return,
         positive_count, negative_count, win_rate,
         directional_consistency, earnings_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        earnings_date,
        data['avg_abs_return'],
        data['std_return'],
        data['max_positive_return'],
        data['max_negative_return'],
        data['positive_count'],
        data['negative_count'],
        data['win_rate'],
        data['directional_consistency'],
        data['earnings_count']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("="*80)
    print("CALCULATING HISTORICAL EARNINGS PATTERNS")
    print("="*80)
    print()
    print("For each ticker, calculating patterns from PRIOR earnings only:")
    print("  - Average absolute return (typical move size)")
    print("  - Standard deviation (consistency)")
    print("  - Max positive/negative moves")
    print("  - Win rate and directional consistency")
    print()

    # Create table
    create_patterns_table()

    # Get all earnings data
    all_data = get_all_earnings_data()

    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(all_data, columns=['ticker', 'earnings_date', 'day_return'])

    print(f"Found {len(df)} earnings events across {df['ticker'].nunique()} unique tickers")
    print()

    # Group by ticker
    ticker_groups = df.groupby('ticker')

    total_processed = 0
    has_history_count = 0
    no_history_count = 0

    for ticker, group in ticker_groups:
        # Sort by date
        group = group.sort_values('earnings_date')

        # For each earnings date, calculate patterns from prior earnings
        for idx, row in group.iterrows():
            current_date = row['earnings_date']

            # Get all prior earnings for this ticker
            prior_earnings = group[group['earnings_date'] < current_date]

            if len(prior_earnings) > 0:
                historical_returns = prior_earnings['day_return'].values
                patterns = calculate_historical_patterns(ticker, current_date, historical_returns)

                # Store patterns
                store_patterns(ticker, current_date, patterns)

                if patterns['avg_abs_return'] is not None:
                    print(f"[{total_processed+1}] {ticker:12} {current_date}  "
                          f"n={patterns['earnings_count']:2}  "
                          f"avg_abs={patterns['avg_abs_return']:5.2f}%  "
                          f"std={patterns['std_return']:5.2f}%  "
                          f"win_rate={patterns['win_rate']*100:5.1f}%  "
                          f"max=[{patterns['max_negative_return']:+6.2f}%, {patterns['max_positive_return']:+6.2f}%]")
                    has_history_count += 1
                else:
                    print(f"[{total_processed+1}] {ticker:12} {current_date}  n={patterns['earnings_count']:2}  (insufficient history)")
                    no_history_count += 1
            else:
                # First earnings for this ticker - no prior history
                patterns = {
                    'avg_abs_return': None,
                    'std_return': None,
                    'max_positive_return': None,
                    'max_negative_return': None,
                    'positive_count': 0,
                    'negative_count': 0,
                    'win_rate': None,
                    'directional_consistency': None,
                    'earnings_count': 0
                }
                store_patterns(ticker, current_date, patterns)
                print(f"[{total_processed+1}] {ticker:12} {current_date}  n=0  (first earnings)")
                no_history_count += 1

            total_processed += 1

    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total processed: {total_processed}")
    print(f"  ✓ With history (2+): {has_history_count} ({has_history_count/total_processed*100:.1f}%)")
    print(f"  ⚠ No history (0-1): {no_history_count} ({no_history_count/total_processed*100:.1f}%)")
    print()
    print("Data stored in historical_earnings_patterns table")
    print("="*80)


if __name__ == '__main__':
    main()
