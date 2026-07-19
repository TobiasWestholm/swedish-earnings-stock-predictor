#!/usr/bin/env python3
"""
Quality Assurance for Fundamental Predictor Data

Checks:
1. Value ranges (e.g., position_in_range should be 0-1)
2. Missing data patterns and suspicious gaps
3. Outliers and impossible values
4. Data consistency across tables
5. Sample verification - manually check a few stocks
6. Look-ahead bias - verify dates are before earnings
7. Join integrity - ensure keys match across tables
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
from datetime import datetime, timedelta
import yfinance as yf


def check_52week_position():
    """QA check for 52-week position data."""
    print("=" * 80)
    print("QA: 52-WEEK POSITION DATA")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Check 1: Value ranges
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN position_in_range < 0 OR position_in_range > 1 THEN 1 END) as out_of_range,
            MIN(position_in_range) as min_pos,
            MAX(position_in_range) as max_pos,
            AVG(position_in_range) as avg_pos,
            COUNT(CASE WHEN position_in_range IS NULL THEN 1 END) as null_pos
        FROM earnings_52week_position
    """)

    row = cursor.fetchone()
    total, out_of_range, min_pos, max_pos, avg_pos, null_pos = row

    print(f"Total records: {total}")
    print(f"NULL position_in_range: {null_pos} ({null_pos/total*100:.1f}%)")
    print(f"Out of range [0,1]: {out_of_range} ({out_of_range/total*100:.1f}%)")
    print(f"Min position: {min_pos:.3f}")
    print(f"Max position: {max_pos:.3f}")
    print(f"Avg position: {avg_pos:.3f}")
    print()

    if out_of_range > 0:
        print(f"⚠️  WARNING: {out_of_range} records have position_in_range outside [0,1]")
        cursor.execute("""
            SELECT ticker, earnings_date, position_in_range, week_52_high, week_52_low, current_price
            FROM earnings_52week_position
            WHERE position_in_range < 0 OR position_in_range > 1
            LIMIT 5
        """)
        print("Sample bad records:")
        for row in cursor.fetchall():
            print(f"  {row}")
        print()
    else:
        print("✓ All position_in_range values in valid range [0,1]")
        print()

    # Check 2: Impossible relationships
    cursor.execute("""
        SELECT
            COUNT(*) as bad_highs
        FROM earnings_52week_position
        WHERE current_price > week_52_high * 1.01
    """)
    bad_highs = cursor.fetchone()[0]

    cursor.execute("""
        SELECT
            COUNT(*) as bad_lows
        FROM earnings_52week_position
        WHERE current_price < week_52_low * 0.99
    """)
    bad_lows = cursor.fetchone()[0]

    if bad_highs > 0:
        print(f"⚠️  WARNING: {bad_highs} records have current_price > 52w_high (should be impossible)")
    else:
        print("✓ No stocks with current_price > 52w_high")

    if bad_lows > 0:
        print(f"⚠️  WARNING: {bad_lows} records have current_price < 52w_low (should be impossible)")
    else:
        print("✓ No stocks with current_price < 52w_low")
    print()

    # Check 3: Sample verification
    print("Sample records for manual verification:")
    cursor.execute("""
        SELECT ticker, earnings_date, week_52_high, week_52_low, current_price,
               position_in_range, distance_from_high_pct, distance_from_low_pct
        FROM earnings_52week_position
        ORDER BY RANDOM()
        LIMIT 3
    """)

    for row in cursor.fetchall():
        ticker, date, high, low, current, pos, dist_high, dist_low = row

        # Manually calculate position
        expected_pos = (current - low) / (high - low) if high != low else 0.5
        expected_dist_high = ((high - current) / high) * 100
        expected_dist_low = ((current - low) / low) * 100

        pos_match = abs(pos - expected_pos) < 0.001
        high_match = abs(dist_high - expected_dist_high) < 0.1
        low_match = abs(dist_low - expected_dist_low) < 0.1

        status = "✓" if pos_match and high_match and low_match else "✗"

        print(f"\n{ticker} on {date}:")
        print(f"  52w High: {high:.2f}, 52w Low: {low:.2f}, Current: {current:.2f}")
        print(f"  Position: {pos:.3f} (expected {expected_pos:.3f}) {status}")
        print(f"  Dist from high: {dist_high:.1f}% (expected {expected_dist_high:.1f}%) {status}")
        print(f"  Dist from low: {dist_low:.1f}% (expected {expected_dist_low:.1f}%) {status}")

    conn.close()
    print()


def check_valuation_metrics():
    """QA check for valuation metrics."""
    print("=" * 80)
    print("QA: VALUATION METRICS DATA")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Check 1: Coverage
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(trailing_pe) as has_pe,
            COUNT(forward_pe) as has_fpe,
            COUNT(price_to_book) as has_pb,
            COUNT(price_to_sales) as has_ps,
            COUNT(valuation_category) as has_category
        FROM earnings_valuation_metrics
    """)

    row = cursor.fetchone()
    total, has_pe, has_fpe, has_pb, has_ps, has_cat = row

    print(f"Total records: {total}")
    print(f"Has trailing P/E: {has_pe} ({has_pe/total*100:.1f}%)")
    print(f"Has forward P/E: {has_fpe} ({has_fpe/total*100:.1f}%)")
    print(f"Has P/B: {has_pb} ({has_pb/total*100:.1f}%)")
    print(f"Has P/S: {has_ps} ({has_ps/total*100:.1f}%)")
    print(f"Has category: {has_cat} ({has_cat/total*100:.1f}%)")
    print()

    # Check 2: Outlier P/E ratios
    cursor.execute("""
        SELECT
            MIN(trailing_pe) as min_pe,
            MAX(trailing_pe) as max_pe,
            AVG(trailing_pe) as avg_pe,
            COUNT(CASE WHEN trailing_pe < 0 THEN 1 END) as negative_pe,
            COUNT(CASE WHEN trailing_pe > 100 THEN 1 END) as extreme_pe
        FROM earnings_valuation_metrics
        WHERE trailing_pe IS NOT NULL
    """)

    row = cursor.fetchone()
    min_pe, max_pe, avg_pe, neg_pe, extreme_pe = row

    print(f"P/E Ratio Statistics:")
    print(f"  Min: {min_pe:.2f}")
    print(f"  Max: {max_pe:.2f}")
    print(f"  Avg: {avg_pe:.2f}")
    print(f"  Negative P/E: {neg_pe} (loss-making companies)")
    print(f"  Extreme P/E (>100): {extreme_pe}")
    print()

    if max_pe > 500:
        print(f"⚠️  WARNING: Some P/E ratios > 500 (may indicate data quality issues)")
        cursor.execute("""
            SELECT ticker, earnings_date, trailing_pe, valuation_category
            FROM earnings_valuation_metrics
            WHERE trailing_pe > 500
            LIMIT 5
        """)
        print("Sample extreme P/E records:")
        for row in cursor.fetchall():
            ticker, date, pe, category = row
            pe_str = f"{pe:.1f}" if pe != float('inf') else "inf"
            print(f"  {ticker} on {date}: P/E={pe_str}, category={category}")
        print()
    else:
        print("✓ No extreme P/E outliers (>500)")
        print()

    # Check 3: Valuation category distribution
    cursor.execute("""
        SELECT valuation_category, COUNT(*) as count
        FROM earnings_valuation_metrics
        WHERE valuation_category IS NOT NULL
        GROUP BY valuation_category
        ORDER BY count DESC
    """)

    print("Valuation Category Distribution:")
    for row in cursor.fetchall():
        category, count = row
        print(f"  {category:20s}: {count:3d} ({count/has_cat*100:5.1f}%)")
    print()

    # Check 4: Verify category logic
    cursor.execute("""
        SELECT ticker, earnings_date, trailing_pe, valuation_category
        FROM earnings_valuation_metrics
        WHERE trailing_pe IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 5
    """)

    print("Sample category verification:")
    for row in cursor.fetchall():
        ticker, date, pe, category = row

        # Determine expected category
        if pe < 0:
            expected = "Negative Earnings"
        elif pe < 10:
            expected = "Deep Value"
        elif pe < 15:
            expected = "Value"
        elif pe < 25:
            expected = "Moderate"
        elif pe < 40:
            expected = "Growth"
        else:
            expected = "High Growth"

        match = "✓" if expected == category else "✗"
        print(f"  {ticker}: P/E={pe:.1f} → {category} (expected {expected}) {match}")

    conn.close()
    print()


def check_analyst_coverage():
    """QA check for analyst coverage data."""
    print("=" * 80)
    print("QA: ANALYST COVERAGE DATA")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Check 1: Coverage statistics
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(num_analysts) as has_analyst_count,
            COUNT(CASE WHEN num_analysts > 0 THEN 1 END) as has_analysts,
            COUNT(avg_rating) as has_rating,
            COUNT(eps_current_year) as has_eps,
            COUNT(target_price_mean) as has_target
        FROM earnings_analyst_coverage
    """)

    row = cursor.fetchone()
    total, has_count, has_analysts, has_rating, has_eps, has_target = row

    print(f"Total records: {total}")
    print(f"Has analyst count: {has_count} ({has_count/total*100:.1f}%)")
    print(f"Has analysts (>0): {has_analysts} ({has_analysts/total*100:.1f}%)")
    print(f"Has rating: {has_rating} ({has_rating/total*100:.1f}%)")
    print(f"Has EPS estimate: {has_eps} ({has_eps/total*100:.1f}%)")
    print(f"Has price target: {has_target} ({has_target/total*100:.1f}%)")
    print()

    # Check 2: Analyst count distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN num_analysts = 0 THEN 'No coverage'
                WHEN num_analysts BETWEEN 1 AND 2 THEN '1-2 analysts'
                WHEN num_analysts BETWEEN 3 AND 5 THEN '3-5 analysts'
                WHEN num_analysts BETWEEN 6 AND 10 THEN '6-10 analysts'
                ELSE '10+ analysts'
            END as coverage_level,
            COUNT(*) as count
        FROM earnings_analyst_coverage
        GROUP BY coverage_level
        ORDER BY MIN(num_analysts)
    """)

    print("Analyst Coverage Distribution:")
    for row in cursor.fetchall():
        level, count = row
        print(f"  {level:20s}: {count:3d} ({count/total*100:5.1f}%)")
    print()

    # Check 3: Rating validity (should be 1-5 scale)
    cursor.execute("""
        SELECT
            MIN(avg_rating) as min_rating,
            MAX(avg_rating) as max_rating,
            AVG(avg_rating) as avg_rating,
            COUNT(CASE WHEN avg_rating < 1 OR avg_rating > 5 THEN 1 END) as out_of_range
        FROM earnings_analyst_coverage
        WHERE avg_rating IS NOT NULL AND avg_rating > 0
    """)

    row = cursor.fetchone()
    if row[0] is not None:
        min_rating, max_rating, avg_rating, out_of_range = row

        print(f"Rating Statistics (1=Strong Buy, 5=Strong Sell):")
        print(f"  Min: {min_rating:.2f}")
        print(f"  Max: {max_rating:.2f}")
        print(f"  Avg: {avg_rating:.2f}")

        if out_of_range > 0:
            print(f"⚠️  WARNING: {out_of_range} ratings outside [1,5] range")
        else:
            print("✓ All ratings in valid range [1,5]")
        print()
    else:
        print("No rating data available")
        print()

    # Check 4: Upside calculation verification
    cursor.execute("""
        SELECT ticker, earnings_date, target_price_current, target_price_mean, upside_to_mean_target
        FROM earnings_analyst_coverage
        WHERE target_price_mean IS NOT NULL AND target_price_mean > 0
        ORDER BY RANDOM()
        LIMIT 5
    """)

    print("Sample upside calculation verification:")
    for row in cursor.fetchall():
        ticker, date, current, target, upside = row
        if current and target:
            expected_upside = ((target - current) / current) * 100
            match = abs(upside - expected_upside) < 0.5
            status = "✓" if match else "✗"
            print(f"  {ticker}: Current={current:.2f}, Target={target:.2f}")
            print(f"    Upside: {upside:.1f}% (expected {expected_upside:.1f}%) {status}")

    conn.close()
    print()


def check_data_joins():
    """Verify that joins work correctly across tables."""
    print("=" * 80)
    print("QA: DATA JOIN INTEGRITY")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Check 1: Verify all earnings dates have matching fundamental data
    cursor.execute("""
        SELECT
            COUNT(DISTINCT ia.ticker || '|' || ia.earnings_date) as total_earnings,
            COUNT(DISTINCT CASE WHEN pos.ticker IS NOT NULL THEN pos.ticker || '|' || pos.earnings_date END) as has_52w,
            COUNT(DISTINCT CASE WHEN liq.ticker IS NOT NULL THEN liq.ticker || '|' || liq.earnings_date END) as has_liquidity,
            COUNT(DISTINCT CASE WHEN vol.ticker IS NOT NULL THEN vol.ticker || '|' || vol.earnings_date END) as has_volatility,
            COUNT(DISTINCT CASE WHEN mom.ticker IS NOT NULL THEN mom.ticker || '|' || mom.earnings_date END) as has_momentum,
            COUNT(DISTINCT CASE WHEN val.ticker IS NOT NULL THEN val.ticker || '|' || val.earnings_date END) as has_valuation
        FROM (SELECT DISTINCT ticker, earnings_date FROM earnings_intraday_analysis WHERE time_of_day = '17:00') ia
        LEFT JOIN earnings_52week_position pos ON ia.ticker = pos.ticker AND ia.earnings_date = pos.earnings_date
        LEFT JOIN market_cap_liquidity liq ON ia.ticker = liq.ticker AND ia.earnings_date = liq.earnings_date
        LEFT JOIN earnings_volatility vol ON ia.ticker = vol.ticker AND ia.earnings_date = vol.earnings_date
        LEFT JOIN earnings_momentum mom ON ia.ticker = mom.ticker AND ia.earnings_date = mom.earnings_date
        LEFT JOIN earnings_valuation_metrics val ON ia.ticker = val.ticker AND ia.earnings_date = val.earnings_date
    """)

    row = cursor.fetchone()
    total, has_52w, has_liq, has_vol, has_mom, has_val = row

    print(f"Total unique (ticker, earnings_date) combinations: {total}")
    print(f"Have 52-week position: {has_52w} ({has_52w/total*100:.1f}%)")
    print(f"Have liquidity: {has_liq} ({has_liq/total*100:.1f}%)")
    print(f"Have volatility: {has_vol} ({has_vol/total*100:.1f}%)")
    print(f"Have momentum: {has_mom} ({has_mom/total*100:.1f}%)")
    print(f"Have valuation: {has_val} ({has_val/total*100:.1f}%)")
    print()

    if has_52w != total or has_liq != total or has_vol != total or has_mom != total:
        print("⚠️  WARNING: Not all earnings dates have complete fundamental data")

        # Find missing records
        cursor.execute("""
            SELECT ia.ticker, ia.earnings_date
            FROM (SELECT DISTINCT ticker, earnings_date FROM earnings_intraday_analysis WHERE time_of_day = '17:00') ia
            LEFT JOIN earnings_52week_position pos ON ia.ticker = pos.ticker AND ia.earnings_date = pos.earnings_date
            WHERE pos.ticker IS NULL
            LIMIT 5
        """)

        missing = cursor.fetchall()
        if missing:
            print(f"Sample earnings dates missing 52w position data:")
            for row in missing:
                print(f"  {row}")
        print()
    else:
        print("✓ All earnings dates have 52w position, liquidity, volatility, and momentum data")
        print()

    # Check 2: Verify no orphan records (fundamentals without earnings dates)
    cursor.execute("""
        SELECT COUNT(*) as orphans
        FROM earnings_52week_position pos
        WHERE NOT EXISTS (
            SELECT 1 FROM earnings_intraday_analysis ia
            WHERE ia.ticker = pos.ticker AND ia.earnings_date = pos.earnings_date
        )
    """)

    orphans = cursor.fetchone()[0]
    if orphans > 0:
        print(f"⚠️  WARNING: {orphans} 52w position records have no matching earnings date")
    else:
        print("✓ No orphan 52w position records")

    conn.close()
    print()


def check_look_ahead_bias():
    """Verify no look-ahead bias - all data is from BEFORE earnings date."""
    print("=" * 80)
    print("QA: LOOK-AHEAD BIAS CHECK")
    print("=" * 80)
    print()

    print("Checking sample stocks to verify data is from BEFORE earnings...")
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Get a few sample records
    cursor.execute("""
        SELECT DISTINCT ia.ticker, ia.earnings_date
        FROM earnings_intraday_analysis ia
        WHERE ia.time_of_day = '17:00'
        ORDER BY RANDOM()
        LIMIT 3
    """)

    samples = cursor.fetchall()

    for ticker, earnings_date in samples:
        print(f"{ticker} - Earnings on {earnings_date}")

        # Get the stored 52w position data
        cursor.execute("""
            SELECT current_price, week_52_high, week_52_low, position_in_range
            FROM earnings_52week_position
            WHERE ticker = ? AND earnings_date = ?
        """, (ticker, earnings_date))

        stored = cursor.fetchone()
        if stored:
            stored_price, stored_high, stored_low, stored_pos = stored
            print(f"  Stored: Price={stored_price:.2f}, 52w range=[{stored_low:.2f}, {stored_high:.2f}], pos={stored_pos:.3f}")

            # Fetch fresh data from yfinance to verify
            try:
                stock = yf.Ticker(ticker)
                earnings_dt = datetime.strptime(earnings_date, '%Y-%m-%d')
                end_date = earnings_dt - timedelta(days=1)  # Day BEFORE earnings
                start_date = end_date - timedelta(days=370)

                hist = stock.history(start=start_date, end=end_date, interval='1d')

                if not hist.empty:
                    actual_price = float(hist['Close'].iloc[-1])
                    prices = hist['Close'].tail(252)
                    actual_high = float(prices.max())
                    actual_low = float(prices.min())
                    actual_pos = (actual_price - actual_low) / (actual_high - actual_low)

                    price_match = abs(stored_price - actual_price) / actual_price < 0.05
                    pos_match = abs(stored_pos - actual_pos) < 0.05

                    status = "✓" if price_match and pos_match else "⚠️"

                    print(f"  Actual: Price={actual_price:.2f}, 52w range=[{actual_low:.2f}, {actual_high:.2f}], pos={actual_pos:.3f}")
                    print(f"  {status} Match: Price diff={abs(stored_price-actual_price)/actual_price*100:.1f}%, Pos diff={abs(stored_pos-actual_pos)*100:.1f}%")
                else:
                    print(f"  ⚠️  Could not fetch historical data for verification")
            except Exception as e:
                print(f"  ⚠️  Error verifying: {e}")

        print()

    conn.close()
    print("Note: Small differences (<5%) are acceptable due to yfinance data updates")
    print()


def check_correlation_consistency():
    """Verify fundamental metrics distributions make sense."""
    print("=" * 80)
    print("QA: FUNDAMENTAL METRICS DISTRIBUTIONS")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Check volatility distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN vol.volatility_20d >= 2.0 THEN 'High Vol (>=2%)'
                WHEN vol.volatility_20d >= 1.0 THEN 'Med Vol (1-2%)'
                ELSE 'Low Vol (<1%)'
            END as vol_bucket,
            COUNT(*) as count,
            AVG(vol.volatility_20d) as avg_vol,
            MIN(vol.volatility_20d) as min_vol,
            MAX(vol.volatility_20d) as max_vol
        FROM earnings_volatility vol
        GROUP BY vol_bucket
        ORDER BY MIN(vol.volatility_20d) DESC
    """)

    print("Volatility Distribution:")
    for row in cursor.fetchall():
        bucket, count, avg_vol, min_vol, max_vol = row
        print(f"  {bucket:20s}: {count:3d} stocks (avg={avg_vol:.2f}%, range={min_vol:.2f}%-{max_vol:.2f}%)")
    print()

    # Check 52w position distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN pos.position_in_range >= 0.85 THEN 'Near High (>=85%)'
                WHEN pos.position_in_range >= 0.50 THEN 'Mid Range (50-85%)'
                ELSE 'Near Low (<50%)'
            END as pos_bucket,
            COUNT(*) as count,
            AVG(pos.position_in_range) as avg_pos
        FROM earnings_52week_position pos
        GROUP BY pos_bucket
        ORDER BY MIN(pos.position_in_range) DESC
    """)

    print("52-Week Position Distribution:")
    for row in cursor.fetchall():
        bucket, count, avg_pos = row
        print(f"  {bucket:20s}: {count:3d} stocks (avg position={avg_pos:.2f})")
    print()

    # Check momentum distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN mom.momentum_252d >= 20 THEN 'Strong (+20%+)'
                WHEN mom.momentum_252d >= 0 THEN 'Positive (0-20%)'
                WHEN mom.momentum_252d >= -30 THEN 'Moderate Neg (-30-0%)'
                ELSE 'Weak (<-30%)'
            END as mom_bucket,
            COUNT(*) as count,
            AVG(mom.momentum_252d) as avg_mom,
            MIN(mom.momentum_252d) as min_mom,
            MAX(mom.momentum_252d) as max_mom
        FROM earnings_momentum mom
        GROUP BY mom_bucket
        ORDER BY MIN(mom.momentum_252d) DESC
    """)

    print("1-Year Momentum Distribution:")
    for row in cursor.fetchall():
        bucket, count, avg_mom, min_mom, max_mom = row
        print(f"  {bucket:20s}: {count:3d} stocks (avg={avg_mom:+.1f}%, range={min_mom:+.1f}% to {max_mom:+.1f}%)")
    print()

    # Check liquidity distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN liq.liquidity_score >= 50 THEN 'High Liquidity (>=50)'
                WHEN liq.liquidity_score >= 30 THEN 'Med Liquidity (30-50)'
                WHEN liq.liquidity_score >= 10 THEN 'Low Liquidity (10-30)'
                ELSE 'Very Low (<10)'
            END as liq_bucket,
            COUNT(*) as count,
            AVG(liq.liquidity_score) as avg_liq
        FROM market_cap_liquidity liq
        GROUP BY liq_bucket
        ORDER BY MIN(liq.liquidity_score) DESC
    """)

    print("Liquidity Score Distribution:")
    for row in cursor.fetchall():
        bucket, count, avg_liq = row
        print(f"  {bucket:25s}: {count:3d} stocks (avg score={avg_liq:.1f})")
    print()

    conn.close()


def main():
    """Run all QA checks."""
    print()
    print("=" * 80)
    print("FUNDAMENTAL DATA QUALITY ASSURANCE")
    print("=" * 80)
    print()

    try:
        check_52week_position()
        check_valuation_metrics()
        check_analyst_coverage()
        check_data_joins()
        check_look_ahead_bias()
        check_correlation_consistency()

        print("=" * 80)
        print("QA SUMMARY")
        print("=" * 80)
        print()
        print("✓ QA checks complete. Review any warnings above.")
        print()

    except Exception as e:
        print(f"✗ QA failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
