"""Scheduled tasks for daily operations."""

import logging
import threading
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)


class DailyScheduler:
    """
    Manages daily scheduled tasks for the trading system.

    Tasks:
    - 08:30 CET: Run screener for today's earnings
    - 09:00 CET: Start live monitor (runs until 10:30)
    - 17:00 CET: Close all open hypothetical trades (end of trading)
    - 17:30 CET: Clear old watchlist and signals (end of trading day)
    """

    def __init__(self, timezone='Europe/Stockholm'):
        """
        Initialize scheduler.

        Args:
            timezone: Timezone for scheduling (default: Europe/Stockholm)
        """
        self.timezone = pytz.timezone(timezone)
        self.scheduler = BackgroundScheduler(timezone=self.timezone)
        self.monitor_thread = None
        logger.info(f"Initialized DailyScheduler (timezone={timezone})")

    def start(self):
        """Start the scheduler with all configured tasks."""
        # Schedule morning screener (08:30 CET)
        self.scheduler.add_job(
            func=self._run_morning_screener,
            trigger=CronTrigger(hour=8, minute=30, timezone=self.timezone),
            id='morning_screener',
            name='Morning Screener (08:30)',
            replace_existing=True
        )

        # Schedule live monitor start (09:00 CET)
        self.scheduler.add_job(
            func=self._start_live_monitor,
            trigger=CronTrigger(hour=9, minute=0, timezone=self.timezone),
            id='start_monitor',
            name='Start Live Monitor (09:00)',
            replace_existing=True
        )

        # Schedule close hypothetical trades (17:00 CET)
        self.scheduler.add_job(
            func=self._close_hypothetical_trades,
            trigger=CronTrigger(hour=17, minute=0, timezone=self.timezone),
            id='close_trades',
            name='Close Hypothetical Trades (17:00)',
            replace_existing=True
        )

        # Schedule end-of-day cleanup (17:30 CET)
        self.scheduler.add_job(
            func=self._run_end_of_day_cleanup,
            trigger=CronTrigger(hour=17, minute=30, timezone=self.timezone),
            id='eod_cleanup',
            name='End of Day Cleanup (17:30)',
            replace_existing=True
        )

        # Start scheduler
        self.scheduler.start()
        logger.info("Scheduler started - tasks will run automatically")
        logger.info("  - 08:30 CET: Morning screener")
        logger.info("  - 09:00 CET: Start live monitor (runs until 10:30)")
        logger.info("  - 17:00 CET: Close hypothetical trades")
        logger.info("  - 17:30 CET: End of day cleanup")

        # Run catch-up for any missed tasks
        self._catch_up_missed_tasks()

    def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

    def _catch_up_missed_tasks(self):
        """
        Check and run any tasks that should have already executed today.
        Called on scheduler startup to handle late starts.
        """
        from datetime import time as dt_time
        from src.utils.database import get_watchlist, get_open_hypothetical_trades

        now = datetime.now(self.timezone)
        current_time = now.time()
        today = now.date()

        logger.info("=" * 80)
        logger.info("CATCH-UP CHECK: Looking for missed tasks...")
        logger.info(f"Current time: {now.strftime('%H:%M:%S')} CET")
        logger.info("=" * 80)

        # Task 1: Morning Screener (08:30)
        # Run if: Current time >= 08:30 AND < 17:30 AND watchlist is empty
        if current_time >= dt_time(8, 30) and current_time < dt_time(17, 30):
            try:
                watchlist = get_watchlist(today.strftime('%Y-%m-%d'))
                if not watchlist:
                    logger.info("⚠️  Missed Task: Morning screener has not run yet")
                    logger.info("   Running screener now (catch-up)...")
                    self._run_morning_screener()
                else:
                    logger.info("✓ Morning screener: Already completed (found %d stocks)", len(watchlist))
            except Exception as e:
                logger.error(f"Error checking screener status: {e}")

        # Task 2: Live Monitor (09:00)
        # Run if: Current time >= 09:00 AND < 10:00 AND monitor not running
        if current_time >= dt_time(9, 0) and current_time < dt_time(10, 0):
            # Check if monitor thread is already running
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                logger.info("⚠️  Missed Task: Live monitor has not started yet")
                logger.info("   Starting monitor now (catch-up)...")

                # Calculate remaining time until 10:30
                target_end = datetime.combine(today, dt_time(10, 30))
                target_end = self.timezone.localize(target_end)
                remaining_minutes = int((target_end - now).total_seconds() / 60)

                if remaining_minutes > 0:
                    logger.info(f"   Monitor will run for {remaining_minutes} minutes (until 10:30)")

                    # Start monitor with remaining time
                    from src.monitoring.live_monitor import LiveMonitor
                    monitor = LiveMonitor()

                    def run_monitor():
                        try:
                            monitor.run(duration_minutes=remaining_minutes)
                            logger.info("Live monitor completed successfully (catch-up)")
                        except Exception as e:
                            logger.error(f"Error in catch-up monitor thread: {e}", exc_info=True)

                    self.monitor_thread = threading.Thread(target=run_monitor, daemon=True)
                    self.monitor_thread.start()
                else:
                    logger.info("   Skipping monitor: Too late (past 10:30 window)")
            else:
                logger.info("✓ Live monitor: Already running")
        elif current_time >= dt_time(10, 0):
            logger.info("✓ Live monitor: Window passed (9:20-10:00), skipping")

        # Task 3: Close Hypothetical Trades (17:00)
        # Run if: Current time >= 17:00 AND < 17:30 AND open trades exist
        if current_time >= dt_time(17, 0) and current_time < dt_time(17, 30):
            try:
                open_trades = get_open_hypothetical_trades(today)
                if open_trades:
                    logger.info("⚠️  Missed Task: Trades have not been closed yet")
                    logger.info(f"   Found {len(open_trades)} open trades")
                    logger.info("   Closing trades now (catch-up)...")
                    self._close_hypothetical_trades()
                else:
                    logger.info("✓ Close trades: Already completed (no open trades)")
            except Exception as e:
                logger.error(f"Error checking trade status: {e}")

        # Task 4: Daily Cleanup (17:30)
        # Run if: Current time >= 17:30 AND today's data still exists
        if current_time >= dt_time(17, 30):
            try:
                # Check if today's watchlist still exists (indicates cleanup hasn't run)
                watchlist = get_watchlist(today.strftime('%Y-%m-%d'))
                if watchlist:
                    logger.info("⚠️  Missed Task: Daily cleanup has not run yet")
                    logger.info(f"   Found {len(watchlist)} watchlist entries from today")
                    logger.info("   Running cleanup now (catch-up)...")
                    self._run_end_of_day_cleanup()
                else:
                    logger.info("✓ Daily cleanup: Already completed (no old data found)")
            except Exception as e:
                logger.error(f"Error checking cleanup status: {e}")

        logger.info("=" * 80)
        logger.info("Catch-up check complete")
        logger.info("=" * 80)

    def _run_morning_screener(self):
        """Run the morning screener at 08:30."""
        try:
            logger.info("=" * 80)
            logger.info("SCHEDULED TASK: Morning Screener (08:30)")
            logger.info("=" * 80)

            from src.screening.screener import Screener

            today = date.today()
            logger.info(f"Running screener for {today}")

            screener = Screener()
            watchlist = screener.run_and_save(today)

            logger.info(f"Morning screener complete: {len(watchlist)} stocks found")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in morning screener: {e}", exc_info=True)

    def _start_live_monitor(self):
        """Start the live monitor at 09:00 (runs until 10:30)."""
        try:
            logger.info("=" * 80)
            logger.info("SCHEDULED TASK: Start Live Monitor (09:00)")
            logger.info("=" * 80)

            from src.monitoring.live_monitor import LiveMonitor

            today = date.today()
            logger.info(f"Starting live monitor for {today}")
            logger.info("Monitor will run for 90 minutes (09:00-10:30)")

            # Create monitor instance
            monitor = LiveMonitor()

            # Run monitor in a separate thread to avoid blocking scheduler
            def run_monitor():
                try:
                    # Run for 90 minutes (covers signal window 9:20-10:00 with buffer)
                    monitor.run(duration_minutes=90)
                    logger.info("Live monitor completed successfully")
                except Exception as e:
                    logger.error(f"Error in live monitor thread: {e}", exc_info=True)

            self.monitor_thread = threading.Thread(target=run_monitor, daemon=True)
            self.monitor_thread.start()

            logger.info("Live monitor started in background thread")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error starting live monitor: {e}", exc_info=True)

    def _close_hypothetical_trades(self):
        """Close all open hypothetical trades at 17:00 (end of trading)."""
        try:
            logger.info("=" * 80)
            logger.info("SCHEDULED TASK: Close Hypothetical Trades (17:00)")
            logger.info("=" * 80)

            from src.utils.database import get_open_hypothetical_trades, close_hypothetical_trade
            from src.data.yfinance_provider import YFinanceProvider

            today = date.today()
            logger.info(f"Closing open trades for {today}")

            # Get all open trades for today
            open_trades = get_open_hypothetical_trades(today)

            if not open_trades:
                logger.info("No open hypothetical trades to close")
                logger.info("=" * 80)
                return

            logger.info(f"Found {len(open_trades)} open trades to close")

            # Initialize data provider
            data_provider = YFinanceProvider()

            # Close each trade
            closed_count = 0
            for trade in open_trades:
                try:
                    ticker = trade['ticker']
                    trade_id = trade['id']

                    # Fetch current price
                    logger.info(f"Fetching exit price for {ticker}...")
                    result = data_provider.get_current_price(ticker)

                    if result['errors']:
                        logger.warning(f"{ticker}: {result['errors']}")

                    exit_price = result.get('price')

                    if exit_price is None:
                        logger.error(f"Could not get exit price for {ticker}, skipping")
                        continue

                    # Close the trade
                    exit_time = datetime.now(self.timezone)
                    success = close_hypothetical_trade(trade_id, exit_time, exit_price)

                    if success:
                        entry_price = trade['entry_price']
                        pnl = ((exit_price - entry_price) / entry_price) * 100
                        logger.info(f"✓ Closed {ticker}: Entry {entry_price:.2f} → Exit {exit_price:.2f} ({pnl:+.2f}%)")
                        closed_count += 1

                except Exception as e:
                    logger.error(f"Error closing trade for {ticker}: {e}")

            logger.info(f"Closed {closed_count}/{len(open_trades)} hypothetical trades")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in close hypothetical trades: {e}", exc_info=True)

    def _run_end_of_day_cleanup(self):
        """Clean up old data at end of trading day (17:30)."""
        try:
            logger.info("=" * 80)
            logger.info("SCHEDULED TASK: End of Day Cleanup (17:30)")
            logger.info("=" * 80)

            from src.utils.database import clear_old_watchlist, clear_old_signals

            today = date.today()
            logger.info(f"Clearing data for {today}")

            # Clear today's watchlist (will be repopulated tomorrow morning)
            watchlist_count = clear_old_watchlist(today)
            logger.info(f"Cleared {watchlist_count} watchlist entries")

            # Clear today's signals
            signals_count = clear_old_signals(today)
            logger.info(f"Cleared {signals_count} signal entries")

            logger.info("End of day cleanup complete")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in end of day cleanup: {e}", exc_info=True)

    def list_jobs(self):
        """List all scheduled jobs."""
        jobs = self.scheduler.get_jobs()
        if not jobs:
            logger.info("No scheduled jobs")
            return

        logger.info("Scheduled Jobs:")
        for job in jobs:
            logger.info(f"  - {job.name}: {job.next_run_time}")

    def run_screener_now(self):
        """Manually trigger the screener (for testing)."""
        logger.info("Manually triggering morning screener")
        self._run_morning_screener()

    def run_cleanup_now(self):
        """Manually trigger cleanup (for testing)."""
        logger.info("Manually triggering end of day cleanup")
        self._run_end_of_day_cleanup()

    def close_trades_now(self):
        """Manually trigger close hypothetical trades (for testing)."""
        logger.info("Manually triggering close hypothetical trades")
        self._close_hypothetical_trades()

    def start_monitor_now(self):
        """Manually trigger live monitor (for testing)."""
        logger.info("Manually triggering live monitor")
        self._start_live_monitor()


def start_scheduler():
    """
    Start the daily scheduler as a background service.

    Returns:
        DailyScheduler instance
    """
    scheduler = DailyScheduler()
    scheduler.start()
    return scheduler


if __name__ == '__main__':
    # Test the scheduler
    import time
    from src.utils.logger import setup_logger

    setup_logger()

    logger.info("Starting scheduler test...")
    scheduler = DailyScheduler()
    scheduler.start()

    # List scheduled jobs
    scheduler.list_jobs()

    # Keep running
    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        scheduler.stop()
