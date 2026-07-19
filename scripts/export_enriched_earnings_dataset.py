#!/usr/bin/env python3
"""
Export enriched earnings dataset with all fundamental metrics.

This script exports a comprehensive CSV dataset that joins:
  - Intraday price data (earnings_intraday_analysis)
  - Earnings day returns (earnings_day_returns)
  - Historical earnings patterns (historical_earnings_patterns)
  - Market cap & liquidity (market_cap_liquidity)
  - Earnings surprise (earnings_surprise)
  - Volatility metrics (earnings_volatility)
  - Volume patterns (earnings_volume)
  - Momentum indicators (earnings_momentum)
  - Analyst revisions (earnings_analyst_revisions)

The exported dataset enables:
  1. Correlation analysis between fundamental metrics and earnings performance
  2. Feature selection for machine learning models
  3. Manual strategy design and filter optimization
  4. Identifying high-value predictors

Usage:
    python scripts/export_enriched_earnings_dataset.py
    python scripts/export_enriched_earnings_dataset.py --output my_dataset.csv
    python scripts/export_enriched_earnings_dataset.py --time 17:00  # Export specific time only
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import csv
import argparse
from datetime import datetime


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Export enriched earnings dataset to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--output',
        type=str,
        default='enriched_earnings_dataset.csv',
        help='Output CSV filename (default: enriched_earnings_dataset.csv)'
    )

    parser.add_argument(
        '--time',
        type=str,
        default='17:00',
        help='Time of day to export (default: 17:00 for end-of-day data)'
    )

    parser.add_argument(
        '--min-date',
        type=str,
        default='2020-01-01',
        help='Minimum earnings date to include (default: 2020-01-01)'
    )

    return parser.parse_args()


def export_enriched_dataset(output_file: str, time_of_day: str = '17:00', min_date: str = '2020-01-01'):
    """
    Export enriched earnings dataset with all fundamental metrics.

    Args:
        output_file: Output CSV filename
        time_of_day: Time of day to export (e.g., '17:00')
        min_date: Minimum earnings date to include
    """
    print("=" * 80)
    print("EXPORTING ENRICHED EARNINGS DATASET")
    print("=" * 80)
    print(f"Time of day: {time_of_day}")
    print(f"Min date: {min_date}")
    print(f"Output file: {output_file}")
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Complex JOIN query to gather all metrics
    query = """
    SELECT
        -- Core identifiers
        ia.ticker,
        ia.earnings_date,
        ia.time_of_day,

        -- Intraday price data
        ia.price,
        ia.normalized_price,
        ia.base_price,
        ia.filter_score,
        ia.passed_filter,
        ia.created_signal,
        ia.top_20pct_performer,
        ia.bottom_30pct_performer,

        -- Earnings day returns (actual outcome)
        edr.prev_close,
        edr.earnings_close,
        edr.earnings_high,
        edr.earnings_low,
        edr.earnings_day_return,
        edr.earnings_day_high_pct,
        edr.earnings_day_low_pct,

        -- Historical earnings patterns (per-ticker behavior)
        hep.avg_abs_return,
        hep.std_return,
        hep.max_positive_return,
        hep.max_negative_return,
        hep.positive_count,
        hep.negative_count,
        hep.win_rate,
        hep.directional_consistency,
        hep.earnings_count,

        -- Market cap & liquidity (tradability filters)
        mcl.market_cap_usd,
        mcl.shares_outstanding,
        mcl.float_shares,
        mcl.float_percent,
        mcl.avg_volume_10d,
        mcl.avg_volume_3m,
        mcl.dollar_volume_daily,
        mcl.liquidity_score,
        mcl.currency,
        mcl.exchange,

        -- 52-week position (momentum and expectation indicator)
        pos52.week_52_high,
        pos52.week_52_low,
        pos52.current_price as price_day_before,
        pos52.position_in_range,
        pos52.distance_from_high_pct,
        pos52.distance_from_low_pct,
        pos52.weeks_since_high,
        pos52.weeks_since_low,

        -- Earnings surprise (fundamental signal)
        es.eps_actual,
        es.eps_estimate,
        es.eps_difference,
        es.surprise_percent,

        -- Volatility metrics (risk assessment)
        ev.volatility_20d,
        ev.volatility_60d,
        ev.volatility_252d,
        ev.data_points_20d as volatility_data_points_20d,
        ev.data_points_60d as volatility_data_points_60d,
        ev.data_points_252d as volatility_data_points_252d,

        -- Volume patterns (liquidity and interest)
        evol.avg_volume_20d as volume_avg_20d,
        evol.avg_volume_60d as volume_avg_60d,
        evol.avg_volume_252d as volume_avg_252d,
        evol.day_before_volume,
        evol.volume_trend_ratio,
        evol.data_points_20d as volume_data_points_20d,
        evol.data_points_60d as volume_data_points_60d,
        evol.data_points_252d as volume_data_points_252d,

        -- Momentum indicators (trend strength)
        em.momentum_20d,
        em.momentum_60d,
        em.momentum_252d,
        em.relative_strength,
        em.data_points_20d as momentum_data_points_20d,
        em.data_points_60d as momentum_data_points_60d,
        em.data_points_252d as momentum_data_points_252d,

        -- Analyst revisions (EPS trend tracking)
        ear.eps_revisions_up_last_7d,
        ear.eps_revisions_down_last_7d,
        ear.eps_revisions_up_last_30d,
        ear.eps_revisions_down_last_30d,
        ear.eps_trend_current,
        ear.eps_trend_7days_ago,
        ear.eps_trend_30days_ago,
        ear.eps_trend_60days_ago

    FROM earnings_intraday_analysis ia

    -- LEFT JOINs to preserve all intraday records even if fundamentals missing
    LEFT JOIN earnings_day_returns edr
        ON ia.ticker = edr.ticker
        AND ia.earnings_date = edr.earnings_date

    LEFT JOIN historical_earnings_patterns hep
        ON ia.ticker = hep.ticker
        AND ia.earnings_date = hep.earnings_date

    LEFT JOIN market_cap_liquidity mcl
        ON ia.ticker = mcl.ticker
        AND ia.earnings_date = mcl.earnings_date

    LEFT JOIN earnings_52week_position pos52
        ON ia.ticker = pos52.ticker
        AND ia.earnings_date = pos52.earnings_date

    LEFT JOIN earnings_surprise es
        ON ia.ticker = es.ticker
        AND ia.earnings_date = es.earnings_date

    LEFT JOIN earnings_volatility ev
        ON ia.ticker = ev.ticker
        AND ia.earnings_date = ev.earnings_date

    LEFT JOIN earnings_volume evol
        ON ia.ticker = evol.ticker
        AND ia.earnings_date = evol.earnings_date

    LEFT JOIN earnings_momentum em
        ON ia.ticker = em.ticker
        AND ia.earnings_date = em.earnings_date

    LEFT JOIN earnings_analyst_revisions ear
        ON ia.ticker = ear.ticker
        AND ia.earnings_date = ear.earnings_date

    WHERE ia.time_of_day = ?
      AND ia.earnings_date >= ?

    ORDER BY ia.earnings_date DESC, ia.ticker
    """

    print("Executing query to gather all metrics...")
    cursor.execute(query, (time_of_day, min_date))

    # Get column names
    columns = [description[0] for description in cursor.description]

    print(f"Found {len(columns)} columns:")
    print(f"  - Core identifiers: 3")
    print(f"  - Intraday price data: 8")
    print(f"  - Earnings day returns: 7")
    print(f"  - Historical patterns: 9")
    print(f"  - Market cap & liquidity: 10")
    print(f"  - 52-week position: 8")
    print(f"  - Earnings surprise: 4")
    print(f"  - Volatility: 6")
    print(f"  - Volume: 8")
    print(f"  - Momentum: 7")
    print(f"  - Analyst revisions: 8")
    print()

    # Write to CSV
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write header
        writer.writerow(columns)

        # Write data
        row_count = 0
        for row in cursor.fetchall():
            writer.writerow(row)
            row_count += 1

    conn.close()

    print("=" * 80)
    print("EXPORT COMPLETE")
    print("=" * 80)
    print(f"✓ Exported {row_count:,} records")
    print(f"✓ Saved to: {output_file}")
    print()

    # Calculate coverage statistics
    print("COVERAGE SUMMARY:")
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN edr.earnings_day_return IS NOT NULL THEN 1 ELSE 0 END) as with_returns,
            SUM(CASE WHEN hep.avg_abs_return IS NOT NULL THEN 1 ELSE 0 END) as with_patterns,
            SUM(CASE WHEN mcl.market_cap_usd IS NOT NULL THEN 1 ELSE 0 END) as with_mcap,
            SUM(CASE WHEN pos52.position_in_range IS NOT NULL THEN 1 ELSE 0 END) as with_52week,
            SUM(CASE WHEN es.eps_difference IS NOT NULL THEN 1 ELSE 0 END) as with_surprise,
            SUM(CASE WHEN ev.volatility_20d IS NOT NULL THEN 1 ELSE 0 END) as with_volatility,
            SUM(CASE WHEN evol.avg_volume_20d IS NOT NULL THEN 1 ELSE 0 END) as with_volume,
            SUM(CASE WHEN em.momentum_20d IS NOT NULL THEN 1 ELSE 0 END) as with_momentum,
            SUM(CASE WHEN ear.eps_revisions_up_last_7d IS NOT NULL THEN 1 ELSE 0 END) as with_revisions
        FROM earnings_intraday_analysis ia
        LEFT JOIN earnings_day_returns edr ON ia.ticker = edr.ticker AND ia.earnings_date = edr.earnings_date
        LEFT JOIN historical_earnings_patterns hep ON ia.ticker = hep.ticker AND ia.earnings_date = hep.earnings_date
        LEFT JOIN market_cap_liquidity mcl ON ia.ticker = mcl.ticker AND ia.earnings_date = mcl.earnings_date
        LEFT JOIN earnings_52week_position pos52 ON ia.ticker = pos52.ticker AND ia.earnings_date = pos52.earnings_date
        LEFT JOIN earnings_surprise es ON ia.ticker = es.ticker AND ia.earnings_date = es.earnings_date
        LEFT JOIN earnings_volatility ev ON ia.ticker = ev.ticker AND ia.earnings_date = ev.earnings_date
        LEFT JOIN earnings_volume evol ON ia.ticker = evol.ticker AND ia.earnings_date = evol.earnings_date
        LEFT JOIN earnings_momentum em ON ia.ticker = em.ticker AND ia.earnings_date = em.earnings_date
        LEFT JOIN earnings_analyst_revisions ear ON ia.ticker = ear.ticker AND ia.earnings_date = ear.earnings_date
        WHERE ia.time_of_day = ? AND ia.earnings_date >= ?
    """, (time_of_day, min_date))

    stats = cursor.fetchone()
    total = stats[0]

    if total > 0:
        print(f"  Total records: {total:,}")
        print(f"  Earnings day returns: {stats[1]:,} ({stats[1]/total*100:.1f}%)")
        print(f"  Historical patterns: {stats[2]:,} ({stats[2]/total*100:.1f}%)")
        print(f"  Market cap & liquidity: {stats[3]:,} ({stats[3]/total*100:.1f}%)")
        print(f"  52-week position: {stats[4]:,} ({stats[4]/total*100:.1f}%)")
        print(f"  Earnings surprise: {stats[5]:,} ({stats[5]/total*100:.1f}%)")
        print(f"  Volatility metrics: {stats[6]:,} ({stats[6]/total*100:.1f}%)")
        print(f"  Volume patterns: {stats[7]:,} ({stats[7]/total*100:.1f}%)")
        print(f"  Momentum indicators: {stats[8]:,} ({stats[8]/total*100:.1f}%)")
        print(f"  Analyst revisions: {stats[9]:,} ({stats[9]/total*100:.1f}%)")

    conn.close()

    print()
    print("=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print(f"1. Load dataset in Python:")
    print(f"   import pandas as pd")
    print(f"   df = pd.read_csv('{output_file}')")
    print()
    print(f"2. Analyze correlations with earnings returns:")
    print(f"   df.corr()['earnings_day_return'].sort_values(ascending=False)")
    print()
    print(f"3. Identify high-value predictors:")
    print(f"   - Market cap & liquidity (tradability filters)")
    print(f"   - Historical patterns (per-ticker behavior)")
    print(f"   - Earnings surprise (fundamental signal)")
    print(f"   - Momentum + Volatility (technical setup)")
    print()
    print(f"4. Design filters for grid search:")
    print(f"   - Min market cap (e.g., $50M USD)")
    print(f"   - Min liquidity score (e.g., 30/100)")
    print(f"   - Min historical earnings count (e.g., 4)")
    print(f"   - Max avg_abs_return for 'high-reaction' stocks")
    print("=" * 80)


def main():
    """Main entry point."""
    args = parse_args()

    export_enriched_dataset(
        output_file=args.output,
        time_of_day=args.time,
        min_date=args.min_date
    )


if __name__ == '__main__':
    main()
