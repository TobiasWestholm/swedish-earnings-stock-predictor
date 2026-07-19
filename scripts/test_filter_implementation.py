#!/usr/bin/env python3
"""
Quick test to verify filter implementation works correctly.

Tests:
1. Data preloading includes all new fundamental metrics
2. Filters correctly exclude stocks based on criteria
3. No errors in filter logic
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection


def test_data_availability():
    """Test that all required tables have data."""
    print("=" * 80)
    print("TESTING DATA AVAILABILITY")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    tables = {
        'earnings_intraday_analysis': 'Intraday price data',
        'earnings_fundamentals': 'Basic fundamentals',
        'earnings_52week_position': '52-week position',
        'market_cap_liquidity': 'Liquidity metrics',
        'earnings_volatility': 'Volatility metrics',
        'earnings_momentum': 'Momentum metrics',
        'earnings_valuation_metrics': 'Valuation metrics'
    }

    all_good = True

    for table, description in tables.items():
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]

        if count > 0:
            print(f"✓ {table:35s}: {count:4d} records ({description})")
        else:
            print(f"✗ {table:35s}: {count:4d} records ({description}) - MISSING DATA!")
            all_good = False

    conn.close()

    print()
    if all_good:
        print("✓ All tables have data")
    else:
        print("✗ Some tables are missing data")

    return all_good


def test_filter_logic():
    """Test that filter logic works on a small sample."""
    print()
    print("=" * 80)
    print("TESTING FILTER LOGIC")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    # Get a sample stock with all data
    cursor.execute("""
        SELECT
            ia.ticker,
            ia.earnings_date,
            pos.position_in_range,
            liq.liquidity_score,
            vol.volatility_20d,
            mom.momentum_252d,
            val.trailing_pe
        FROM earnings_intraday_analysis ia
        LEFT JOIN earnings_52week_position pos
            ON ia.ticker = pos.ticker AND ia.earnings_date = pos.earnings_date
        LEFT JOIN market_cap_liquidity liq
            ON ia.ticker = liq.ticker AND ia.earnings_date = liq.earnings_date
        LEFT JOIN earnings_volatility vol
            ON ia.ticker = vol.ticker AND ia.earnings_date = vol.earnings_date
        LEFT JOIN earnings_momentum mom
            ON ia.ticker = mom.ticker AND ia.earnings_date = mom.earnings_date
        LEFT JOIN earnings_valuation_metrics val
            ON ia.ticker = val.ticker AND ia.earnings_date = val.earnings_date
        WHERE ia.time_of_day = '17:00'
        LIMIT 10
    """)

    print("Sample stocks and filter results:")
    print("-" * 80)

    results = cursor.fetchall()
    conn.close()

    if not results:
        print("✗ No data found for testing")
        return False

    for row in results:
        ticker, date, pos_range, liq_score, vol_20d, mom_252d, pe = row

        # Test each filter
        filters = {
            'position ≤ 0.85': pos_range is not None and pos_range <= 0.85,
            'liquidity ≥ 30': liq_score is not None and liq_score >= 30,
            'volatility ≥ 2.0': vol_20d is not None and vol_20d >= 2.0,
            'momentum ≤ 20': mom_252d is not None and mom_252d <= 20,
            'has P/E data': pe is not None
        }

        passes_all = all([
            filters['position ≤ 0.85'],
            filters['liquidity ≥ 30'],
            filters['volatility ≥ 2.0'],
            filters['momentum ≤ 20']
        ])

        status = "✓ PASS" if passes_all else "✗ FAIL"

        print(f"{ticker:15s} {date}  {status}")

        # Format values with proper handling of None
        pos_str = f"{pos_range:.2f}" if pos_range is not None else "N/A"
        liq_str = f"{liq_score:.0f}" if liq_score is not None else "N/A"
        vol_str = f"{vol_20d:.1f}%" if vol_20d is not None else "N/A"
        mom_str = f"{mom_252d:+.1f}%" if mom_252d is not None else "N/A"
        pe_str = f"{pe:.1f}" if pe is not None else "N/A"

        print(f"  Position: {pos_str:>6s}  Liquidity: {liq_str:>6s}  "
              f"Vol: {vol_str:>7s}  Mom: {mom_str:>7s}  P/E: {pe_str:>6s}")

    print()
    print("✓ Filter logic test complete")
    return True


def test_filter_coverage():
    """Test what percentage of stocks pass each filter."""
    print()
    print("=" * 80)
    print("TESTING FILTER COVERAGE")
    print("=" * 80)
    print()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN pos.position_in_range IS NOT NULL AND pos.position_in_range <= 0.85 THEN 1 ELSE 0 END) as pass_position,
            SUM(CASE WHEN liq.liquidity_score IS NOT NULL AND liq.liquidity_score >= 30 THEN 1 ELSE 0 END) as pass_liquidity,
            SUM(CASE WHEN vol.volatility_20d IS NOT NULL AND vol.volatility_20d >= 2.0 THEN 1 ELSE 0 END) as pass_volatility,
            SUM(CASE WHEN mom.momentum_252d IS NOT NULL AND mom.momentum_252d <= 20 THEN 1 ELSE 0 END) as pass_momentum
        FROM earnings_intraday_analysis ia
        LEFT JOIN earnings_52week_position pos
            ON ia.ticker = pos.ticker AND ia.earnings_date = pos.earnings_date
        LEFT JOIN market_cap_liquidity liq
            ON ia.ticker = liq.ticker AND ia.earnings_date = liq.earnings_date
        LEFT JOIN earnings_volatility vol
            ON ia.ticker = vol.ticker AND ia.earnings_date = vol.earnings_date
        LEFT JOIN earnings_momentum mom
            ON ia.ticker = mom.ticker AND ia.earnings_date = mom.earnings_date
        WHERE ia.time_of_day = '17:00'
    """)

    row = cursor.fetchone()
    total, pass_pos, pass_liq, pass_vol, pass_mom = row

    conn.close()

    print(f"Total stocks: {total}")
    print()
    print("Filter pass rates:")
    print(f"  Position ≤ 0.85:     {pass_pos:3d} / {total} ({pass_pos/total*100:5.1f}%)")
    print(f"  Liquidity ≥ 30:      {pass_liq:3d} / {total} ({pass_liq/total*100:5.1f}%)")
    print(f"  Volatility ≥ 2.0%:   {pass_vol:3d} / {total} ({pass_vol/total*100:5.1f}%)")
    print(f"  Momentum ≤ 20%:      {pass_mom:3d} / {total} ({pass_mom/total*100:5.1f}%)")
    print()

    # Calculate combined pass rate (all filters)
    cursor = get_connection().cursor()
    cursor.execute("""
        SELECT COUNT(*) as pass_all
        FROM earnings_intraday_analysis ia
        JOIN earnings_52week_position pos
            ON ia.ticker = pos.ticker AND ia.earnings_date = pos.earnings_date
        JOIN market_cap_liquidity liq
            ON ia.ticker = liq.ticker AND ia.earnings_date = liq.earnings_date
        JOIN earnings_volatility vol
            ON ia.ticker = vol.ticker AND ia.earnings_date = vol.earnings_date
        JOIN earnings_momentum mom
            ON ia.ticker = mom.ticker AND ia.earnings_date = mom.earnings_date
        WHERE ia.time_of_day = '17:00'
          AND pos.position_in_range <= 0.85
          AND liq.liquidity_score >= 30
          AND vol.volatility_20d >= 2.0
          AND mom.momentum_252d <= 20
    """)

    pass_all = cursor.fetchone()[0]
    cursor.connection.close()

    print(f"Pass ALL filters:    {pass_all:3d} / {total} ({pass_all/total*100:5.1f}%)")
    print()

    if pass_all == 0:
        print("⚠️  WARNING: No stocks pass all filters! Consider relaxing thresholds.")
    elif pass_all < 10:
        print("⚠️  WARNING: Very few stocks pass all filters. May need to relax thresholds.")
    elif pass_all < 30:
        print("✓ Acceptable number of stocks pass all filters")
    else:
        print("✓ Good number of stocks pass all filters")

    return True


def main():
    """Run all tests."""
    print()
    print("=" * 80)
    print("FILTER IMPLEMENTATION TEST SUITE")
    print("=" * 80)
    print()

    # Test 1: Data availability
    test1 = test_data_availability()

    if not test1:
        print()
        print("✗ Data availability test failed. Fix data issues before proceeding.")
        return

    # Test 2: Filter logic
    test2 = test_filter_logic()

    # Test 3: Filter coverage
    test3 = test_filter_coverage()

    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()

    if test1 and test2 and test3:
        print("✓ All tests passed")
        print()
        print("Next steps:")
        print("  1. Run grid search with baseline (all filters = None)")
        print("  2. Test liquidity filter first (min_liquidity_score = 30)")
        print("  3. Add high priority filters one by one")
        print("  4. Test combinations")
        print()
        print("Run: python scripts/grid_search_earnings.py")
    else:
        print("✗ Some tests failed. Fix issues before running grid search.")

    print()


if __name__ == '__main__':
    main()
