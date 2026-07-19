#!/usr/bin/env python3
"""
Test historical replay functionality.

Tests that the system can recreate trades and signals from historical data
when the app was down.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date, timedelta
from src.utils.database import get_connection
from src.backtesting.historical_replay import HistoricalReplay


def test_historical_replay_simulation():
    """Test historical replay by simulating app downtime."""
    print("=" * 70)
    print("TEST: Historical Replay Simulation")
    print("=" * 70)

    # Choose a recent date that had earnings (Feb 19, 2026)
    test_date = date(2026, 2, 19)

    conn = get_connection()
    cursor = conn.cursor()

    print(f"\nTest date: {test_date}")
    print("\nStep 1: Capture current state...")

    # Capture current state
    cursor.execute("SELECT COUNT(*) FROM watchlist WHERE date = ?", (test_date.strftime('%Y-%m-%d'),))
    original_watchlist_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM signals WHERE DATE(signal_time) = ?", (test_date.strftime('%Y-%m-%d'),))
    original_signals_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hypothetical_trades WHERE date = ?", (test_date.strftime('%Y-%m-%d'),))
    original_trades_count = cursor.fetchone()[0]

    print(f"  Original watchlist: {original_watchlist_count}")
    print(f"  Original signals: {original_signals_count}")
    print(f"  Original trades: {original_trades_count}")

    # Delete all data for this date to simulate app being down
    print("\nStep 2: Simulating app downtime (deleting data)...")
    cursor.execute("DELETE FROM watchlist WHERE date = ?", (test_date.strftime('%Y-%m-%d'),))
    cursor.execute("DELETE FROM signals WHERE DATE(signal_time) = ?", (test_date.strftime('%Y-%m-%d'),))
    cursor.execute("DELETE FROM hypothetical_trades WHERE date = ?", (test_date.strftime('%Y-%m-%d'),))
    conn.commit()

    print("  ✓ Data deleted")

    # Run historical replay
    print("\nStep 3: Running historical replay...")
    replay = HistoricalReplay()
    stats = replay.replay_day(test_date)

    print(f"\n  Replay results:")
    print(f"    Screener passed: {stats['screener_passed']}")
    print(f"    Signals detected: {stats['signals_detected']}")
    print(f"    Trades created: {stats['trades_created']}")
    print(f"    Trades closed: {stats['trades_closed']}")

    # Check new state
    print("\nStep 4: Verifying reconstructed data...")
    cursor.execute("SELECT COUNT(*) FROM watchlist WHERE date = ?", (test_date.strftime('%Y-%m-%d'),))
    new_watchlist_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM signals WHERE DATE(signal_time) = ?", (test_date.strftime('%Y-%m-%d'),))
    new_signals_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hypothetical_trades WHERE date = ?", (test_date.strftime('%Y-%m-%d'),))
    new_trades_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hypothetical_trades WHERE date = ? AND status = 'closed'",
                   (test_date.strftime('%Y-%m-%d'),))
    closed_trades_count = cursor.fetchone()[0]

    print(f"  New watchlist: {new_watchlist_count}")
    print(f"  New signals: {new_signals_count}")
    print(f"  New trades: {new_trades_count}")
    print(f"  Closed trades: {closed_trades_count}")

    conn.close()

    # Analysis
    print("\n" + "=" * 70)
    print("RESULTS:")
    print("=" * 70)

    success = True

    if new_watchlist_count > 0:
        print(f"✓ Screener reconstructed: {new_watchlist_count} stocks")
    else:
        print(f"✗ Screener failed: No watchlist created")
        success = False

    if new_signals_count > 0:
        print(f"✓ Signals reconstructed: {new_signals_count} signals")
    else:
        print(f"⚠ No signals detected (might be expected if conditions not met)")

    if new_trades_count > 0:
        print(f"✓ Trades reconstructed: {new_trades_count} trades")
    else:
        print(f"⚠ No trades created (expected if no signals)")

    if new_trades_count > 0 and closed_trades_count == new_trades_count:
        print(f"✓ All trades closed correctly")
    elif new_trades_count > 0:
        print(f"⚠ Some trades not closed: {closed_trades_count}/{new_trades_count}")

    print("\n" + "=" * 70)

    if success:
        print("✓ HISTORICAL REPLAY TEST PASSED")
    else:
        print("✗ HISTORICAL REPLAY TEST FAILED")

    print("=" * 70)

    return success


if __name__ == '__main__':
    try:
        success = test_historical_replay_simulation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
