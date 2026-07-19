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

    def _fetch_fundamentals_at_eod(self, target_date):
        """
        Fetch all fundamental metrics for earnings on target_date.

        Calls the unified wrapper script fetch_all_fundamentals.py which orchestrates
        fetching of all 5 fundamental metric types:
        1. 52-week position
        2. Valuation metrics
        3. Market cap & liquidity
        4. Momentum
        5. Volatility

        Args:
            target_date: date object for which to fetch fundamentals

        Returns:
            bool: True if successful, False otherwise
        """
        import subprocess
        import sys
        import os

        logger.info(f"Fetching fundamental metrics for {target_date}...")

        # Path to wrapper script
        script_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'scripts', 'fetch_all_fundamentals.py'
        )

        # Run wrapper script
        try:
            result = subprocess.run(
                [sys.executable, script_path, '--date', target_date.strftime('%Y-%m-%d')],
                capture_output=True,
                text=True,
                timeout=900  # 15 minute timeout
            )

            # Log output
            if result.stdout:
                logger.info(f"Fundamental fetch output:\n{result.stdout}")

            if result.returncode != 0:
                logger.error(f"Fundamental fetch failed with code {result.returncode}")
                if result.stderr:
                    logger.error(f"Error output:\n{result.stderr}")
                return False

            logger.info(f"Successfully fetched fundamentals for {target_date}")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Fundamental fetch timed out after 15 minutes")
            return False
        except Exception as e:
            logger.error(f"Error fetching fundamentals: {e}", exc_info=True)
            return False

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
        # Run if: Current time >= 17:00 AND open trades exist
        # Note: No upper time limit - trades should be closed even if app starts late
        if current_time >= dt_time(17, 0):
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

        # Task 4: Daily Cleanup & Multi-Day Earnings Extraction (17:30)
        # Run if: Current time >= 17:30
        if current_time >= dt_time(17, 30):
            try:
                # First, check if today's watchlist still exists (cleanup hasn't run today)
                watchlist = get_watchlist(today.strftime('%Y-%m-%d'))
                if watchlist:
                    logger.info("⚠️  Missed Task: Daily cleanup has not run yet")
                    logger.info(f"   Found {len(watchlist)} watchlist entries from today")
                    logger.info("   Running cleanup now (catch-up)...")
                    self._run_end_of_day_cleanup()
                else:
                    logger.info("✓ Daily cleanup: Already completed for today")

                # Second, check for missed earnings extraction from previous days
                logger.info("\n--- Checking for Missed Earnings Extractions ---")
                self._catch_up_missed_earnings_extractions()

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
            from src.utils.config import load_config

            today = date.today()
            logger.info(f"Closing open trades for {today}")

            # Load profit targets from config
            config = load_config()
            strategies_config = config.get('strategies', {})
            profit_targets_config = strategies_config.get('profit_targets', {})
            profit_targets = profit_targets_config.get('targets', [1.0, 2.0, 3.0, 4.0, 5.0])

            # Get open trades for each strategy
            eod_trades = get_open_hypothetical_trades(today, strategy_type='eod')

            # Collect all profit target trades
            all_target_trades = []
            strategy_counts = {}
            for target_pct in profit_targets:
                strategy_type = f"{int(target_pct)}pct_target"
                target_trades = get_open_hypothetical_trades(today, strategy_type=strategy_type)
                all_target_trades.extend(target_trades)
                strategy_counts[strategy_type] = len(target_trades)

            total_trades = len(eod_trades) + len(all_target_trades)

            if total_trades == 0:
                logger.info("No open hypothetical trades to close")
                logger.info("=" * 80)
                return

            # Log counts
            logger.info(f"Found {len(eod_trades)} EOD trades")
            for strategy_type, count in strategy_counts.items():
                if count > 0:
                    logger.info(f"Found {count} {strategy_type} trades")

            # Initialize data provider
            data_provider = YFinanceProvider()

            # Close EOD strategy trades
            eod_closed_count = 0
            logger.info("\n--- Closing EOD Strategy Trades ---")
            for trade in eod_trades:
                try:
                    ticker = trade['ticker']
                    trade_id = trade['id']

                    # Fetch current price
                    logger.info(f"Fetching exit price for {ticker} (EOD)...")
                    result = data_provider.get_current_price(ticker)

                    if result['errors']:
                        logger.warning(f"{ticker}: {result['errors']}")

                    exit_price = result.get('price')

                    if exit_price is None:
                        logger.error(f"Could not get exit price for {ticker}, skipping")
                        continue

                    # Close the trade with 'eod' reason
                    exit_time = datetime.now(self.timezone)
                    success = close_hypothetical_trade(trade_id, exit_time, exit_price, exit_reason='eod')

                    if success:
                        entry_price = trade['entry_price']
                        pnl = ((exit_price - entry_price) / entry_price) * 100
                        logger.info(f"✓ Closed {ticker} (EOD): Entry {entry_price:.2f} → Exit {exit_price:.2f} ({pnl:+.2f}%)")
                        eod_closed_count += 1

                except Exception as e:
                    logger.error(f"Error closing EOD trade for {ticker}: {e}")

            # Close profit target strategy trades (not yet closed by profit target)
            target_closed_count = 0
            logger.info("\n--- Closing Profit Target Strategy Trades (Fallback) ---")
            for trade in all_target_trades:
                try:
                    ticker = trade['ticker']
                    trade_id = trade['id']
                    strategy_type = trade.get('strategy_type', 'unknown')

                    # Fetch current price
                    logger.info(f"Fetching exit price for {ticker} ({strategy_type} fallback)...")
                    result = data_provider.get_current_price(ticker)

                    if result['errors']:
                        logger.warning(f"{ticker}: {result['errors']}")

                    exit_price = result.get('price')

                    if exit_price is None:
                        logger.error(f"Could not get exit price for {ticker}, skipping")
                        continue

                    # Close the trade with 'eod_fallback' reason
                    exit_time = datetime.now(self.timezone)
                    success = close_hypothetical_trade(trade_id, exit_time, exit_price, exit_reason='eod_fallback')

                    if success:
                        entry_price = trade['entry_price']
                        pnl = ((exit_price - entry_price) / entry_price) * 100
                        logger.info(f"✓ Closed {ticker} ({strategy_type} fallback): Entry {entry_price:.2f} → Exit {exit_price:.2f} ({pnl:+.2f}%)")
                        target_closed_count += 1

                except Exception as e:
                    logger.error(f"Error closing profit target trade for {ticker}: {e}")

            logger.info(f"\nClosed {eod_closed_count} EOD trades and {target_closed_count} profit target trades")
            logger.info(f"Total: {eod_closed_count + target_closed_count}/{total_trades} trades closed")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in close hypothetical trades: {e}", exc_info=True)

    def _run_end_of_day_cleanup(self):
        """Clean up old data at end of trading day (17:30)."""
        try:
            logger.info("=" * 80)
            logger.info("SCHEDULED TASK: End of Day Cleanup (17:30)")
            logger.info("=" * 80)

            from src.utils.database import (
                clear_old_watchlist,
                clear_old_signals,
                extract_earnings_intraday_for_date,
                calculate_top_performers
            )

            today = date.today()
            logger.info(f"Processing end of day tasks for {today}")

            # Extract earnings intraday data for today (before clearing)
            logger.info("\n--- Extracting Earnings Intraday Data ---")
            try:
                earnings_stats = extract_earnings_intraday_for_date(today)
                logger.info(f"✓ Extracted {earnings_stats['extracted']}/{earnings_stats['total_earnings']} earnings")
                logger.info(f"  - Passed filter: {earnings_stats['passed_filter']}")
                logger.info(f"  - Created signals: {earnings_stats['created_signal']}")
                logger.info(f"  - Data points saved: {earnings_stats['data_points']}")

                # Calculate and mark top 20% performers
                if earnings_stats['extracted'] > 0:
                    top_stats = calculate_top_performers(today)
                    logger.info(f"✓ Marked top 20% performers: {top_stats['top_performer_count']}/{top_stats['total_stocks']} stocks")
            except Exception as e:
                logger.error(f"Error extracting earnings data: {e}", exc_info=True)

            # Fetch fundamental metrics for today's earnings
            logger.info("\n--- Fetching Fundamental Metrics ---")
            try:
                from src.utils.config import load_config

                config = load_config()
                if config.get('fundamental_data', {}).get('fetch_at_eod', True):
                    self._fetch_fundamentals_at_eod(today)

                    # Optional: fetch for next trading day (preparation)
                    if config.get('fundamental_data', {}).get('prefetch_next_day', False):
                        tomorrow = today + timedelta(days=1)
                        logger.info(f"Pre-fetching fundamentals for tomorrow ({tomorrow})...")
                        self._fetch_fundamentals_at_eod(tomorrow)
                else:
                    logger.info("Fundamental data fetching is disabled in config")
            except Exception as e:
                logger.error(f"Error fetching fundamental data: {e}", exc_info=True)

            # Check if today is incomplete (screener ran but no trades)
            # This happens when app starts late and misses the signal window
            logger.info("\n--- Checking for Incomplete Day ---")
            try:
                from src.utils.database import get_connection

                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM watchlist WHERE date = ?",
                             (today.strftime('%Y-%m-%d'),))
                watchlist_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM hypothetical_trades WHERE date = ?",
                             (today.strftime('%Y-%m-%d'),))
                trades_count = cursor.fetchone()[0]

                conn.close()

                # If screener ran but no trades exist, we missed the signal window
                if watchlist_count > 0 and trades_count == 0:
                    logger.warning(f"⚠️  Day {today} appears incomplete:")
                    logger.warning(f"   - Watchlist has {watchlist_count} stocks (screener ran)")
                    logger.warning(f"   - But 0 trades exist (signal window missed)")
                    logger.info(f"   → Running HISTORICAL REPLAY to detect missed signals...")

                    # Clear today's incomplete data first
                    from src.utils.database import clear_old_watchlist, clear_old_signals
                    clear_old_watchlist(today)
                    clear_old_signals(today)

                    # Run historical replay for today
                    from src.backtesting.historical_replay import HistoricalReplay
                    replay = HistoricalReplay()
                    replay_stats = replay.replay_day(today)

                    logger.info(f"   ✓ Historical replay complete for {today}:")
                    logger.info(f"     - Screener passed: {replay_stats['screener_passed']}")
                    logger.info(f"     - Signals detected: {replay_stats['signals_detected']}")
                    logger.info(f"     - Trades created: {replay_stats['trades_created']}")
                    logger.info(f"     - Trades closed: {replay_stats['trades_closed']}")

                    # Re-extract earnings with correct signal/filter markings
                    logger.info(f"   → Re-extracting earnings data with complete information...")
                    earnings_stats = extract_earnings_intraday_for_date(today)
                    logger.info(f"   ✓ Re-extracted {earnings_stats['extracted']} earnings")

                    # Calculate and mark top 20% performers
                    if earnings_stats['extracted'] > 0:
                        top_stats = calculate_top_performers(today)
                        logger.info(f"   ✓ Marked top 20% performers: {top_stats['top_performer_count']}/{top_stats['total_stocks']} stocks")
                else:
                    logger.info(f"✓ Day {today} is complete (watchlist={watchlist_count}, trades={trades_count})")

            except Exception as e:
                logger.error(f"Error checking day completeness: {e}", exc_info=True)

            # Clear today's watchlist (will be repopulated tomorrow morning)
            logger.info("\n--- Clearing Temporary Data ---")
            watchlist_count = clear_old_watchlist(today)
            logger.info(f"Cleared {watchlist_count} watchlist entries")

            # Clear today's signals
            signals_count = clear_old_signals(today)
            logger.info(f"Cleared {signals_count} signal entries")

            # IMPORTANT: hypothetical_trades are NEVER cleared - they are permanent records
            # This ensures complete historical trade data for backtesting and analysis

            logger.info("\nEnd of day cleanup complete")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error in end of day cleanup: {e}", exc_info=True)

    def _catch_up_missed_earnings_extractions(self, lookback_days: int = 28):
        """
        Check for missed earnings extractions from previous days and catch up.

        This handles the case where the app was closed for several days (e.g., holidays, system downtime).
        For each trading day in the lookback period:
        1. Checks if the earnings calendar has earnings for that day
        2. Checks if we already have extracted data in the database
        3. If missing, extracts intraday data for all earnings that day
        4. Marks which stocks passed filter and created signals (from watchlist/signals/trades)
        5. Cleans up old watchlist/signals after successful extraction

        IMPORTANT: This preserves the integrity of the earnings visualization by ensuring
        all historical earnings data is captured, even if the app was offline.

        Args:
            lookback_days: How many days back to check (default 28 to cover extended holidays)
        """
        try:
            from src.utils.database import extract_earnings_intraday_for_date, calculate_top_performers, get_connection
            from datetime import timedelta

            today = date.today()
            extracted_any = False

            # Check each day going backwards
            for days_ago in range(1, lookback_days + 1):
                check_date = today - timedelta(days=days_ago)

                # Skip weekends (no trading)
                if check_date.weekday() >= 5:  # Saturday=5, Sunday=6
                    continue

                # Check the earnings calendar CSV for this date
                import pandas as pd

                csv_path = 'data/earnings_calendar.csv'
                try:
                    try:
                        df = pd.read_csv(csv_path, encoding='utf-8')
                    except UnicodeDecodeError:
                        try:
                            df = pd.read_csv(csv_path, encoding='latin-1')
                        except:
                            df = pd.read_csv(csv_path, encoding='cp1252')

                    # Parse and count earnings for this date
                    def parse_date(date_str):
                        try:
                            from datetime import datetime
                            return datetime.strptime(date_str, '%m/%d/%y').date()
                        except:
                            try:
                                from datetime import datetime
                                return datetime.strptime(date_str, '%Y-%m-%d').date()
                            except:
                                return None

                    calendar_count = 0
                    for _, row in df.iterrows():
                        if pd.isna(row['date']) or pd.isna(row['ticker']):
                            continue
                        date_obj = parse_date(str(row['date']))
                        if date_obj == check_date:
                            calendar_count += 1

                except Exception as e:
                    logger.error(f"Error reading earnings calendar: {e}")
                    calendar_count = 0

                # Check if we already have earnings data for this date
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT COUNT(DISTINCT ticker) as count
                    FROM earnings_intraday_analysis
                    WHERE earnings_date = ?
                """, (check_date.strftime('%Y-%m-%d'),))

                existing_count = cursor.fetchone()[0]
                conn.close()

                # Log what we found for this date
                if calendar_count > 0:
                    if existing_count > 0:
                        # Already have data, log for transparency
                        logger.debug(f"  {check_date}: {existing_count} tickers already extracted (skipping)")
                    else:
                        # Missing data - need to replay and extract
                        if not extracted_any:
                            logger.info("Found missed trading days - will replay strategy on historical data:")
                            extracted_any = True

                        logger.info(f"\n⚠️  Processing missed day: {check_date} ({days_ago} days ago)")
                        logger.info(f"   Calendar shows {calendar_count} earnings, database has 0 extracted")

                        # Check if we have filter data for this date (watchlist/signals/trades)
                        conn_check = get_connection()
                        cursor_check = conn_check.cursor()

                        cursor_check.execute("SELECT COUNT(*) FROM watchlist WHERE date = ?",
                                           (check_date.strftime('%Y-%m-%d'),))
                        watchlist_count = cursor_check.fetchone()[0]

                        cursor_check.execute("SELECT COUNT(*) FROM signals WHERE DATE(signal_time) = ?",
                                           (check_date.strftime('%Y-%m-%d'),))
                        signals_count = cursor_check.fetchone()[0]

                        cursor_check.execute("SELECT COUNT(*) FROM hypothetical_trades WHERE date = ?",
                                           (check_date.strftime('%Y-%m-%d'),))
                        trades_count = cursor_check.fetchone()[0]
                        conn_check.close()

                        # Decide: replay strategy or just extract
                        # Key insight: Trades are only created when signals are detected.
                        # If no trades exist, either app was down OR monitoring failed.
                        # Both cases require historical replay to ensure complete data.
                        if trades_count > 0:
                            logger.info(f"   Found {trades_count} trades → Day appears complete")
                            logger.info(f"   → Skipping replay (live trading data exists)")
                        else:
                            if watchlist_count > 0 or signals_count > 0:
                                logger.info(f"   Found incomplete data: watchlist={watchlist_count}, signals={signals_count}, trades=0")
                                logger.info(f"   → App started but missed signal window")
                            else:
                                logger.info(f"   No trading data found → App was closed this day")
                            logger.info(f"   → Running HISTORICAL REPLAY (backtest mode)")

                            try:
                                # REPLAY: Run entire trading strategy on historical data
                                from src.backtesting.historical_replay import HistoricalReplay

                                replay = HistoricalReplay()
                                replay_stats = replay.replay_day(check_date)

                                logger.info(f"   ✓ Historical replay complete:")
                                logger.info(f"     - Screener passed: {replay_stats['screener_passed']}")
                                logger.info(f"     - Signals detected: {replay_stats['signals_detected']}")
                                logger.info(f"     - Trades created: {replay_stats['trades_created']}")
                                logger.info(f"     - Trades closed: {replay_stats['trades_closed']}")

                                # Update counts after replay
                                watchlist_count = replay_stats['screener_passed']
                                signals_count = replay_stats['signals_detected']
                                trades_count = replay_stats['trades_created']

                            except Exception as e:
                                logger.error(f"   ✗ Error in historical replay: {e}", exc_info=True)

                        try:
                            # Extract the earnings intraday data
                            logger.info(f"   → Extracting earnings intraday data...")
                            stats = extract_earnings_intraday_for_date(check_date)
                            logger.info(f"   ✓ Extracted {stats['extracted']}/{stats['total_earnings']} earnings successfully")
                            logger.info(f"     - Marked {stats['passed_filter']} as passed filter")
                            logger.info(f"     - Marked {stats['created_signal']} as created signals")
                            logger.info(f"     - Saved {stats['data_points']} intraday data points")

                            # Calculate and mark top 20% performers
                            if stats['extracted'] > 0:
                                top_stats = calculate_top_performers(check_date)
                                logger.info(f"     - Marked top 20%: {top_stats['top_performer_count']}/{top_stats['total_stocks']} stocks")

                            # Fetch fundamental metrics for this date (catch-up)
                            try:
                                from src.utils.config import load_config
                                config = load_config()
                                if config.get('fundamental_data', {}).get('fetch_at_eod', True):
                                    logger.info(f"   → Fetching fundamental metrics (catch-up)...")
                                    self._fetch_fundamentals_at_eod(check_date)
                            except Exception as e:
                                logger.error(f"   ✗ Error fetching fundamentals for {check_date}: {e}", exc_info=True)

                            # Clean up old watchlist/signals for this date (after successful extraction)
                            if watchlist_count > 0 or signals_count > 0:
                                from src.utils.database import clear_old_watchlist, clear_old_signals
                                cleared_watchlist = clear_old_watchlist(check_date)
                                cleared_signals = clear_old_signals(check_date)
                                logger.info(f"     - Cleaned up old data: {cleared_watchlist} watchlist, {cleared_signals} signals")

                        except Exception as e:
                            logger.error(f"   ✗ Error extracting {check_date}: {e}", exc_info=True)

            if not extracted_any:
                logger.info("✓ No missed earnings extractions found (all caught up)")
            else:
                logger.info("\n✓ Multi-day catch-up complete")

        except Exception as e:
            logger.error(f"Error in multi-day catch-up: {e}", exc_info=True)

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
