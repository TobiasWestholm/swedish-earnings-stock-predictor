"""Run live monitoring with paper trading tracking enabled."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.monitoring.live_monitor import LiveMonitor
from src.backtesting.paper_trading_tracker import PaperTradingTracker
from src.backtesting.strategy_simulator import StrategySimulator
from src.utils.logger import setup_logger
from src.utils.config import load_config
import sqlite3
from datetime import datetime
import logging

# Setup logging
logger = setup_logger()


class PaperTradingMonitor:
    """
    Extends LiveMonitor to automatically log signals to paper trading tracker.

    This allows you to validate the strategy in real-time without risking capital.
    """

    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        Initialize paper trading monitor.

        Args:
            config_path: Path to configuration file
        """
        self.config = load_config(config_path)
        self.tracker = PaperTradingTracker()
        self.monitor = LiveMonitor(config_path=config_path)

        # Create strategy simulator with production config
        self.simulator = StrategySimulator(
            use_earnings_surprise_filter=True,  # ✅ Production config
            use_trailing_stop=False              # ❌ Production config
        )

        logger.info("Initialized PaperTradingMonitor with production configuration")
        logger.info("  ✅ Earnings Surprise Filter: ENABLED")
        logger.info("  ❌ Trailing Stop: DISABLED")

    def get_todays_watchlist(self):
        """Get today's watchlist from database."""
        conn = sqlite3.connect('data/trades.db')
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT ticker FROM watchlist
            WHERE date = DATE('now')
        ''')

        tickers = [row[0] for row in cursor.fetchall()]
        conn.close()

        return tickers

    def check_earnings_surprise(self, ticker: str) -> dict:
        """
        Check if ticker passed earnings surprise filter.

        Args:
            ticker: Stock ticker

        Returns:
            Earnings surprise data dictionary
        """
        today = datetime.now().strftime('%Y-%m-%d')
        return self.simulator._check_earnings_surprise(ticker, today)

    def start_monitoring(self):
        """Start monitoring with automatic paper trading logging."""
        tickers = self.get_todays_watchlist()

        if not tickers:
            logger.warning("No tickers in today's watchlist. Run screener first.")
            print("\n⚠️  No tickers in today's watchlist.")
            print("Run the screener first: python scripts/run_screener.py\n")
            return

        logger.info(f"Starting paper trading monitoring for {len(tickers)} tickers")
        print("\n" + "="*80)
        print("PAPER TRADING MONITOR")
        print("="*80)
        print(f"\nMonitoring {len(tickers)} tickers: {', '.join(tickers)}")
        print(f"Signal window: {self.config['monitoring']['signal_window_start']} - "
              f"{self.config['monitoring']['signal_window_end']}")
        print("\n✅ Earnings Surprise Filter: ENABLED")
        print("❌ Trailing Stop: DISABLED")
        print("\nAll signals will be automatically logged to paper trading tracker.")
        print("Use paper_trading_dashboard.py to review signals and log outcomes.")
        print("\nPress Ctrl+C to stop monitoring.\n")
        print("="*80 + "\n")

        # Custom signal callback to log to paper trading tracker
        def on_signal_detected(signal):
            """Callback when signal is detected."""
            ticker = signal['ticker']

            # Check earnings surprise for this ticker
            earnings_data = self.check_earnings_surprise(ticker)

            # Log to paper trading tracker
            signal_id = self.tracker.log_signal(signal, earnings_data)

            # Enhanced console notification
            print("\n" + "🔔" * 40)
            print(f"SIGNAL DETECTED: {ticker} @ {signal['entry_price']:.2f} SEK")
            print("=" * 80)
            print(f"Signal ID:         {signal_id}")
            print(f"Time:              {signal['signal_time']}")
            print(f"Entry Price:       {signal['entry_price']:.2f} SEK")
            print(f"VWAP:              {signal['vwap']:.2f} SEK (+{signal['vwap_distance_pct']:.1f}%)")
            print(f"Open:              {signal['open_price']:.2f} SEK (+{signal['open_distance_pct']:.1f}%)")
            print(f"Yesterday Close:   {signal['yesterday_close']:.2f} SEK (+{signal['pct_from_yesterday']:.1f}%)")
            print(f"Confidence:        {signal['confidence_score']:.0%}")
            print(f"Data Age:          {signal['data_age_seconds']} seconds")

            # Earnings surprise info
            if earnings_data.get('passed'):
                print(f"\n✅ EARNINGS SURPRISE: PASSED")
                print(f"  Estimate:  {earnings_data['eps_estimate']:.2f}")
                print(f"  Reported:  {earnings_data['reported_eps']:.2f}")
                print(f"  Surprise:  {earnings_data.get('surprise_pct', 0):+.1f}%")
            else:
                print(f"\n⚠️  Earnings Surprise: {earnings_data.get('reason', 'Not checked')}")

            # Risk management (1% of 100k account = 1000 SEK risk)
            entry_price = signal['entry_price']
            stop_loss = entry_price * 0.975  # -2.5%
            risk_per_share = entry_price - stop_loss
            shares = int(1000 / risk_per_share)
            capital_required = shares * entry_price

            print(f"\n💼 RISK MANAGEMENT (1% of 100k account):")
            print(f"  Entry:          {entry_price:.2f} SEK")
            print(f"  Stop Loss:      {stop_loss:.2f} SEK (-2.5%)")
            print(f"  Position Size:  {shares} shares")
            print(f"  Capital:        {capital_required:,.0f} SEK")
            print(f"  Risk:           {shares * risk_per_share:.0f} SEK")

            print("\n" + "="*80)
            print(f"📝 Signal logged to paper trading tracker (ID: {signal_id})")
            print("Use paper_trading_dashboard.py to:")
            print("  - Mark as executed if you take the trade")
            print("  - Mark as skipped if you don't trade")
            print("  - Log outcome at end of day")
            print("🔔" * 40 + "\n")

        # Start monitoring with custom callback
        try:
            self.monitor.start(tickers, on_signal_callback=on_signal_detected)
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user.")
            print("\nToday's Summary:")

            today_signals = self.tracker.get_today_signals()
            if today_signals:
                print(f"  Signals detected: {len(today_signals)}")
                print(f"  Executed: {sum(1 for s in today_signals if s['executed'])}")
                print(f"  Skipped: {sum(1 for s in today_signals if s['skipped'])}")
                print(f"  Pending: {sum(1 for s in today_signals if not s['executed'] and not s['skipped'])}")
            else:
                print("  No signals detected today")

            print("\nRun paper_trading_dashboard.py to review and log outcomes.\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Run paper trading monitor')
    parser.add_argument('--config', default='config/config.yaml',
                       help='Path to config file')
    args = parser.parse_args()

    monitor = PaperTradingMonitor(config_path=args.config)
    monitor.start_monitoring()


if __name__ == '__main__':
    main()
