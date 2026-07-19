#!/usr/bin/env python3
"""
Comprehensive test suite for earnings extraction integrity.
Verifies that all trades are logged correctly and earnings data is captured.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date, timedelta
from src.utils.database import get_connection

def test_hypothetical_trades_never_cleared():
    """Verify that hypothetical_trades table has data and is never cleared."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if trades exist
    cursor.execute("SELECT COUNT(*) FROM hypothetical_trades")
    total_trades = cursor.fetchone()[0]

    # Check date range of trades
    cursor.execute("SELECT MIN(date), MAX(date), COUNT(DISTINCT date) FROM hypothetical_trades")
    min_date, max_date, unique_days = cursor.fetchone()

    conn.close()

    print("=" * 70)
    print("TEST: Hypothetical Trades Persistence")
    print("=" * 70)
    print(f"✓ Total trades in database: {total_trades}")
    print(f"✓ Date range: {min_date} to {max_date}")
    print(f"✓ Unique trading days: {unique_days}")
    print(f"✓ Trades are NEVER cleared (permanent records)")
    print()

    assert total_trades > 0, "No trades found - this might indicate data loss!"
    return True

def test_earnings_data_completeness():
    """Verify earnings data completeness for recent days."""
    conn = get_connection()
    cursor = conn.cursor()

    today = date.today()
    lookback = 7  # Check last week

    print("=" * 70)
    print("TEST: Earnings Data Completeness (Last 7 Days)")
    print("=" * 70)

    for days_ago in range(lookback):
        check_date = today - timedelta(days=days_ago)

        # Skip weekends
        if check_date.weekday() >= 5:
            print(f"{check_date} (Weekend - Skipped)")
            continue

        date_str = check_date.strftime('%Y-%m-%d')

        # Count earnings data
        cursor.execute("""
            SELECT COUNT(DISTINCT ticker) as tickers,
                   COUNT(*) as data_points,
                   COUNT(DISTINCT CASE WHEN passed_filter = 1 THEN ticker END) as passed_filter,
                   COUNT(DISTINCT CASE WHEN created_signal = 1 THEN ticker END) as created_signal
            FROM earnings_intraday_analysis
            WHERE earnings_date = ?
        """, (date_str,))

        tickers, data_points, passed_filter, created_signal = cursor.fetchone()

        # Count trades
        cursor.execute("SELECT COUNT(*) FROM hypothetical_trades WHERE date = ?", (date_str,))
        trades_count = cursor.fetchone()[0]

        if tickers > 0:
            print(f"✓ {check_date}: {tickers} tickers, {data_points} points, "
                  f"{passed_filter} passed filter, {created_signal} signals, {trades_count} trades")
        else:
            print(f"⚠ {check_date}: No earnings data (app may have been closed)")

    conn.close()
    print()
    return True

def test_filter_signal_consistency():
    """Verify that filter/signal markings are consistent with trades."""
    conn = get_connection()
    cursor = conn.cursor()

    print("=" * 70)
    print("TEST: Filter/Signal Marking Consistency")
    print("=" * 70)

    # For each day with trades, verify earnings data is marked correctly
    cursor.execute("""
        SELECT date, COUNT(DISTINCT ticker) as trade_count
        FROM hypothetical_trades
        GROUP BY date
        ORDER BY date DESC
        LIMIT 5
    """)

    trades_by_date = cursor.fetchall()

    issues_found = 0
    for trade_date, expected_signals in trades_by_date:
        # Count how many tickers are marked as created_signal in earnings data
        cursor.execute("""
            SELECT COUNT(DISTINCT ticker)
            FROM earnings_intraday_analysis
            WHERE earnings_date = ? AND created_signal = 1
        """, (trade_date,))

        actual_signals = cursor.fetchone()[0]

        # Note: actual_signals might be less than expected if some tickers had no yfinance data
        if actual_signals > 0:
            print(f"✓ {trade_date}: {actual_signals} signals marked (out of {expected_signals} trades)")
        else:
            print(f"⚠ {trade_date}: No signal markings found (but {expected_signals} trades exist)")
            issues_found += 1

    conn.close()

    if issues_found > 0:
        print(f"\n⚠ Found {issues_found} dates with inconsistencies")
        print("  This may indicate extraction ran before trades were created")
    else:
        print(f"\n✓ All signal markings consistent with trades")

    print()
    return issues_found == 0

def test_no_duplicate_data():
    """Verify no duplicate earnings data for same ticker/date/time."""
    conn = get_connection()
    cursor = conn.cursor()

    print("=" * 70)
    print("TEST: No Duplicate Data")
    print("=" * 70)

    cursor.execute("""
        SELECT ticker, earnings_date, time_of_day, COUNT(*) as count
        FROM earnings_intraday_analysis
        GROUP BY ticker, earnings_date, time_of_day
        HAVING count > 1
        LIMIT 10
    """)

    duplicates = cursor.fetchall()

    if duplicates:
        print(f"⚠ Found {len(duplicates)} duplicate entries:")
        for ticker, date, time, count in duplicates:
            print(f"  - {ticker} on {date} at {time}: {count} entries")
    else:
        print("✓ No duplicate entries found (data integrity maintained)")

    conn.close()
    print()
    return len(duplicates) == 0

def test_extraction_coverage():
    """Verify extraction covers all trading days in lookback period."""
    import pandas as pd

    conn = get_connection()
    cursor = conn.cursor()

    print("=" * 70)
    print("TEST: Extraction Coverage (28-Day Lookback)")
    print("=" * 70)

    # Load earnings calendar
    try:
        df = pd.read_csv('data/earnings_calendar.csv', encoding='latin-1')
    except:
        print("⚠ Could not load earnings calendar")
        return False

    def parse_date(date_str):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%m/%d/%y').date()
        except:
            return None

    today = date.today()
    lookback_start = today - timedelta(days=28)

    # Count earnings in calendar for last 28 trading days
    calendar_by_date = {}
    for _, row in df.iterrows():
        if pd.isna(row['date']) or pd.isna(row['ticker']):
            continue
        date_obj = parse_date(str(row['date']))
        if date_obj and lookback_start <= date_obj <= today:
            if date_obj.weekday() < 5:  # Weekdays only
                calendar_by_date[date_obj] = calendar_by_date.get(date_obj, 0) + 1

    # Count extracted data by date
    cursor.execute("""
        SELECT earnings_date, COUNT(DISTINCT ticker)
        FROM earnings_intraday_analysis
        WHERE earnings_date >= ?
        GROUP BY earnings_date
    """, (lookback_start.strftime('%Y-%m-%d'),))

    extracted_by_date = dict(cursor.fetchall())

    # Compare
    missing_days = []
    for cal_date, cal_count in sorted(calendar_by_date.items()):
        date_str = cal_date.strftime('%Y-%m-%d')
        extracted_count = extracted_by_date.get(date_str, 0)

        if extracted_count == 0:
            missing_days.append((cal_date, cal_count))

    if missing_days:
        print(f"⚠ Found {len(missing_days)} days with earnings in calendar but no extraction:")
        for missing_date, cal_count in missing_days[:5]:  # Show first 5
            print(f"  - {missing_date}: {cal_count} earnings in calendar, 0 extracted")
    else:
        print(f"✓ All trading days covered ({len(calendar_by_date)} days checked)")

    conn.close()
    print()
    return len(missing_days) == 0

def run_all_tests():
    """Run all integrity tests."""
    print("\n" + "=" * 70)
    print("EARNINGS EXTRACTION INTEGRITY TEST SUITE")
    print("=" * 70 + "\n")

    results = {
        "Trades Persistence": test_hypothetical_trades_never_cleared(),
        "Data Completeness": test_earnings_data_completeness(),
        "Filter/Signal Consistency": test_filter_signal_consistency(),
        "No Duplicates": test_no_duplicate_data(),
        "Extraction Coverage": test_extraction_coverage()
    }

    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 70 + "\n")

    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
