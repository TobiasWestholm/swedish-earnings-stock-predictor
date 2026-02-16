"""Interactive dashboard for paper trading tracking."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtesting.paper_trading_tracker import PaperTradingTracker
from src.utils.logger import setup_logger
from datetime import datetime, timedelta

# Setup logging
setup_logger()

# Expected backtest metrics (from STRATEGY_CONFIGURATION.md)
BACKTEST_METRICS = {
    'win_rate': 54.5,
    'avg_pnl': 4.54,
    'profit_factor': 4.89,
    'trades_executed': 11,
    'total_pnl': 49.98
}


def show_menu():
    """Display main menu."""
    print("\n" + "="*80)
    print("PAPER TRADING DASHBOARD")
    print("="*80)
    print("\n1. View today's signals")
    print("2. View pending outcomes (need to log results)")
    print("3. Log trade outcome")
    print("4. Mark signal as executed")
    print("5. Mark signal as skipped")
    print("6. View summary (all time)")
    print("7. View summary (last 7 days)")
    print("8. View summary (last 30 days)")
    print("9. Compare to backtest expectations")
    print("10. Export signals to CSV")
    print("0. Exit")
    print()


def view_today_signals(tracker):
    """Show all signals from today."""
    signals = tracker.get_today_signals()

    if not signals:
        print("\n📭 No signals detected today yet.\n")
        return

    print(f"\n📊 Today's Signals ({len(signals)})")
    print("-" * 120)
    print(f"{'ID':<5} {'Time':<8} {'Ticker':<12} {'Entry':<10} {'VWAP':<10} {'Open':<10} {'Confidence':<12} {'Status':<15}")
    print("-" * 120)

    for sig in signals:
        status = "✅ Executed" if sig['executed'] else ("⏭️  Skipped" if sig['skipped'] else "⏳ Pending")
        conf = f"{sig['confidence_score']:.0%}" if sig['confidence_score'] else "N/A"

        print(f"{sig['id']:<5} {sig['signal_time']:<8} {sig['ticker']:<12} "
              f"{sig['entry_price']:<10.2f} {sig['vwap'] or 0:<10.2f} "
              f"{sig['open_price'] or 0:<10.2f} {conf:<12} {status:<15}")

    print()


def view_pending_outcomes(tracker):
    """Show signals that need outcomes logged."""
    signals = tracker.get_pending_outcomes()

    if not signals:
        print("\n✅ No pending outcomes - all executed trades have results logged.\n")
        return

    print(f"\n⏳ Pending Outcomes ({len(signals)})")
    print("-" * 100)
    print(f"{'ID':<5} {'Date':<12} {'Time':<8} {'Ticker':<12} {'Entry':<10} {'Notes':<30}")
    print("-" * 100)

    for sig in signals:
        notes = (sig['notes'] or '')[:27] + '...' if sig['notes'] and len(sig['notes']) > 30 else (sig['notes'] or '')
        print(f"{sig['id']:<5} {sig['signal_date']:<12} {sig['signal_time']:<8} "
              f"{sig['ticker']:<12} {sig['entry_price']:<10.2f} {notes:<30}")

    print()


def log_trade_outcome(tracker):
    """Interactive prompt to log a trade outcome."""
    signal_id = input("\nEnter signal ID: ").strip()

    try:
        signal_id = int(signal_id)
    except ValueError:
        print("❌ Invalid signal ID")
        return

    # Get signal details
    import sqlite3
    conn = sqlite3.connect(tracker.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT ticker, entry_price FROM paper_signals WHERE id = ?', (signal_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        print(f"❌ Signal {signal_id} not found")
        return

    ticker, entry_price = result
    print(f"\n📝 Logging outcome for {ticker} (Entry: {entry_price:.2f} SEK)")

    exit_price = float(input("Exit price (SEK): ").strip())
    exit_time = input("Exit time (HH:MM): ").strip()

    print("\nExit reason:")
    print("1. Stop loss")
    print("2. End of day")
    print("3. Manual exit")
    print("4. Other")
    choice = input("Select (1-4): ").strip()

    exit_reasons = {
        '1': 'stop_loss',
        '2': 'end_of_day',
        '3': 'manual_exit',
        '4': 'other'
    }
    exit_reason = exit_reasons.get(choice, 'other')

    notes = input("Notes (optional): ").strip() or None

    tracker.log_outcome(signal_id, exit_price, exit_time, exit_reason, notes)

    pnl = exit_price - entry_price
    pnl_pct = (pnl / entry_price) * 100
    print(f"\n✅ Outcome logged: {pnl:+.2f} SEK ({pnl_pct:+.1f}%)\n")


def mark_executed(tracker):
    """Mark a signal as executed."""
    signal_id = input("\nEnter signal ID: ").strip()

    try:
        signal_id = int(signal_id)
    except ValueError:
        print("❌ Invalid signal ID")
        return

    notes = input("Execution notes (optional): ").strip() or None
    tracker.mark_executed(signal_id, notes)
    print(f"✅ Signal {signal_id} marked as executed\n")


def mark_skipped(tracker):
    """Mark a signal as skipped."""
    signal_id = input("\nEnter signal ID: ").strip()

    try:
        signal_id = int(signal_id)
    except ValueError:
        print("❌ Invalid signal ID")
        return

    print("\nReason for skipping:")
    print("1. Data too stale")
    print("2. Risk limit reached")
    print("3. Market conditions")
    print("4. Other")
    choice = input("Select (1-4): ").strip()

    reasons = {
        '1': 'Data too stale',
        '2': 'Risk limit reached',
        '3': 'Market conditions',
        '4': input("Specify reason: ").strip()
    }
    reason = reasons.get(choice, 'Not specified')

    tracker.mark_skipped(signal_id, reason)
    print(f"✅ Signal {signal_id} marked as skipped: {reason}\n")


def view_summary(tracker, days=None):
    """Display performance summary."""
    if days:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        tracker.print_summary(str(start_date), str(end_date))
    else:
        tracker.print_summary()


def compare_to_backtest(tracker):
    """Compare paper trading to backtest results."""
    comparison = tracker.compare_to_backtest(BACKTEST_METRICS)

    if 'error' in comparison:
        print(f"\n{comparison['error']}\n")
        return

    print("\n" + "="*80)
    print("BACKTEST VS PAPER TRADING COMPARISON")
    print("="*80)

    print(f"\n📊 WIN RATE")
    print(f"  Backtest:        {comparison['win_rate']['backtest']:.1f}%")
    print(f"  Paper Trading:   {comparison['win_rate']['paper_trading']:.1f}%")
    print(f"  Variance:        {comparison['win_rate']['variance']:+.1f}%")

    print(f"\n💰 AVERAGE P&L")
    print(f"  Backtest:        {comparison['avg_pnl']['backtest']:.2f} SEK")
    print(f"  Paper Trading:   {comparison['avg_pnl']['paper_trading']:.2f} SEK")
    print(f"  Variance:        {comparison['avg_pnl']['variance']:+.2f} SEK")

    print(f"\n📈 PROFIT FACTOR")
    bt_pf = comparison['profit_factor']['backtest']
    pt_pf = comparison['profit_factor']['paper_trading']
    print(f"  Backtest:        {bt_pf:.2f}")
    print(f"  Paper Trading:   {pt_pf if pt_pf != float('inf') else '∞'}")

    print(f"\n📝 ASSESSMENT")
    print(f"  {comparison['assessment']}")

    print("\n" + "="*80 + "\n")


def export_signals(tracker):
    """Export signals to CSV."""
    filepath = input("\nEnter output filepath (e.g., paper_trades.csv): ").strip()

    if not filepath:
        print("❌ Filepath required")
        return

    include_date_filter = input("Filter by date range? (y/n): ").strip().lower() == 'y'

    start_date = None
    end_date = None

    if include_date_filter:
        start_date = input("Start date (YYYY-MM-DD): ").strip() or None
        end_date = input("End date (YYYY-MM-DD): ").strip() or None

    tracker.export_to_csv(filepath, start_date, end_date)
    print(f"✅ Signals exported to {filepath}\n")


def main():
    """Main dashboard loop."""
    tracker = PaperTradingTracker()

    while True:
        show_menu()
        choice = input("Select option (0-10): ").strip()

        if choice == '0':
            print("\n👋 Exiting paper trading dashboard.\n")
            break
        elif choice == '1':
            view_today_signals(tracker)
        elif choice == '2':
            view_pending_outcomes(tracker)
        elif choice == '3':
            log_trade_outcome(tracker)
        elif choice == '4':
            mark_executed(tracker)
        elif choice == '5':
            mark_skipped(tracker)
        elif choice == '6':
            view_summary(tracker)
        elif choice == '7':
            view_summary(tracker, days=7)
        elif choice == '8':
            view_summary(tracker, days=30)
        elif choice == '9':
            compare_to_backtest(tracker)
        elif choice == '10':
            export_signals(tracker)
        else:
            print("\n❌ Invalid option\n")

        input("Press Enter to continue...")


if __name__ == '__main__':
    main()
