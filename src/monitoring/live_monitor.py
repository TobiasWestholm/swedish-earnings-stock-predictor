"""Live intraday monitoring for watchlist stocks."""

import time
from datetime import datetime, date, time as dt_time
from typing import List, Dict, Any
import logging
import pytz

from src.data.yfinance_provider import YFinanceProvider
from src.monitoring.indicators import calculate_intraday_metrics
from src.monitoring.signal_detector import SignalDetector
from src.utils.database import (
    get_watchlist, save_intraday_data, save_signal,
    get_open_hypothetical_trades, close_hypothetical_trade
)
from src.utils.config import load_config

logger = logging.getLogger(__name__)


class LiveMonitor:
    """
    Monitors watchlist stocks during market hours (09:00-17:30 CET).

    Polls prices every 60 seconds, calculates VWAP, and stores data.
    """

    def __init__(self, data_provider: YFinanceProvider = None):
        """
        Initialize live monitor.

        Args:
            data_provider: Data provider instance
        """
        self.data_provider = data_provider or YFinanceProvider()

        # Load configuration
        config = load_config()
        market_config = config.get('market', {})
        monitoring_config = config.get('monitoring', {})

        self.timezone = pytz.timezone(market_config.get('timezone', 'Europe/Stockholm'))
        self.poll_interval = monitoring_config.get('poll_interval', 60)

        self.is_running = False
        self.watchlist_tickers = []

        # Initialize signal detector
        self.signal_detector = SignalDetector(timezone=str(self.timezone))

        logger.info(f"Initialized LiveMonitor (timezone={self.timezone}, poll_interval={self.poll_interval}s)")

    def load_watchlist(self, target_date: date = None) -> List[str]:
        """
        Load watchlist for monitoring.

        Args:
            target_date: Date to load watchlist for (defaults to today)

        Returns:
            List of ticker symbols
        """
        if target_date is None:
            target_date = date.today()

        watchlist = get_watchlist(target_date.strftime('%Y-%m-%d'))

        tickers = [stock['ticker'] for stock in watchlist]
        self.watchlist_tickers = tickers

        logger.info(f"Loaded {len(tickers)} tickers from watchlist for {target_date}")
        return tickers

    def is_market_hours(self, check_time: datetime = None) -> bool:
        """
        Check if current time is within market hours.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if within market hours
        """
        if check_time is None:
            check_time = datetime.now(self.timezone)
        elif check_time.tzinfo is None:
            check_time = self.timezone.localize(check_time)

        current_time = check_time.time()

        # Market hours: 09:00 - 17:30 CET
        market_open = dt_time(9, 0)
        market_close = dt_time(17, 30)

        # Check if it's a weekday
        is_weekday = check_time.weekday() < 5  # 0-4 are Mon-Fri

        return is_weekday and market_open <= current_time <= market_close

    def is_monitoring_window(self, check_time: datetime = None) -> bool:
        """
        Check if current time is within signal detection window.

        Signal window: 09:00 - 10:30 CET (focused on morning session for Phase 4 signals)
        Note: This is different from market hours. Monitoring runs 09:00-17:30,
        but signals are only detected during 09:00-10:30.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if within signal detection window
        """
        if check_time is None:
            check_time = datetime.now(self.timezone)
        elif check_time.tzinfo is None:
            check_time = self.timezone.localize(check_time)

        current_time = check_time.time()

        # Monitoring window: 09:00 - 10:30
        window_start = dt_time(9, 0)
        window_end = dt_time(10, 30)

        # Check if it's a weekday
        is_weekday = check_time.weekday() < 5

        return is_weekday and window_start <= current_time <= window_end

    def fetch_ticker_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch current intraday data for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with current data and metrics
        """
        try:
            # Fetch intraday data (1 day, 1-minute intervals)
            result = self.data_provider.get_intraday(ticker, interval='1m')

            if result['errors']:
                logger.warning(f"{ticker}: {result['errors']}")

            data = result['data']

            if data is None or data.empty:
                logger.warning(f"{ticker}: No intraday data available")
                return None

            # Calculate metrics
            metrics = calculate_intraday_metrics(data)

            # Add metadata
            metrics['ticker'] = ticker
            metrics['timestamp'] = datetime.now(self.timezone)
            metrics['date'] = date.today()
            metrics['data_age_seconds'] = result.get('data_age_seconds')
            metrics['quality_score'] = result.get('quality_score')

            return metrics

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return None

    def poll_watchlist(self) -> List[Dict[str, Any]]:
        """
        Poll all watchlist tickers and fetch current data.

        Returns:
            List of ticker data dictionaries
        """
        results = []

        logger.info(f"Polling {len(self.watchlist_tickers)} tickers...")

        for ticker in self.watchlist_tickers:
            data = self.fetch_ticker_data(ticker)

            if data:
                results.append(data)

                # Save to database
                try:
                    save_intraday_data({
                        'ticker': data['ticker'],
                        'timestamp': data['timestamp'],
                        'date': data['date'],
                        'open_price': data.get('open'),
                        'current_price': data.get('close'),
                        'high': data.get('high'),
                        'low': data.get('low'),
                        'volume': data.get('volume'),
                        'vwap': data.get('vwap'),
                        'data_age_seconds': data.get('data_age_seconds')
                    })
                    logger.debug(f"{ticker}: Saved intraday data (VWAP: {data.get('vwap', 0):.2f})")
                except Exception as e:
                    logger.error(f"Error saving data for {ticker}: {e}")

            # Small delay to avoid rate limits
            time.sleep(0.5)

        logger.info(f"Polling complete: {len(results)}/{len(self.watchlist_tickers)} successful")
        return results

    def check_profit_targets(self, poll_results: List[Dict[str, Any]]):
        """
        Check if profit target trades have reached their profit targets and close them.

        Args:
            poll_results: List of ticker data from poll_watchlist()
        """
        # Load profit targets from config
        config = load_config()
        strategies_config = config.get('strategies', {})
        profit_targets_config = strategies_config.get('profit_targets', {})
        profit_targets = profit_targets_config.get('targets', [1.0, 2.0, 3.0, 4.0, 5.0])

        trade_date = date.today()

        # Create a lookup dict for current prices
        current_prices = {data['ticker']: data.get('close') for data in poll_results if data.get('close')}

        # Check each profit target strategy
        for target_pct in profit_targets:
            # Determine strategy type name
            strategy_type = f"{int(target_pct)}pct_target"

            # Get open trades for this strategy
            open_trades = get_open_hypothetical_trades(trade_date=trade_date, strategy_type=strategy_type)

            if not open_trades:
                continue

            # Check each open trade
            for trade in open_trades:
                ticker = trade['ticker']
                entry_price = trade['entry_price']
                trade_id = trade['id']
                stored_target = trade.get('profit_target_pct', target_pct)

                # Get current price from poll results
                current_price = current_prices.get(ticker)

                if current_price is None:
                    logger.warning(f"{ticker}: No current price available for profit check")
                    continue

                # Calculate P&L percentage
                pnl_pct = ((current_price - entry_price) / entry_price) * 100

                # Check if profit target reached
                if pnl_pct >= stored_target:
                    exit_time = datetime.now(self.timezone)
                    success = close_hypothetical_trade(
                        trade_id=trade_id,
                        exit_time=exit_time,
                        exit_price=current_price,
                        exit_reason='profit_target'
                    )

                    if success:
                        logger.info(f"✓ {ticker} ({strategy_type}): Profit target reached! Closed at {pnl_pct:+.2f}% (target: {stored_target}%)")

    def check_signals(self, poll_results: List[Dict[str, Any]]):
        """
        Check poll results for entry signals and save them to database.

        Args:
            poll_results: List of ticker data from poll_watchlist()
        """
        # Convert poll results to format expected by signal detector
        stock_data = {}
        for data in poll_results:
            ticker = data['ticker']

            # Get yesterday's close from historical data
            yesterday_close = None
            try:
                historical_result = self.data_provider.get_historical(ticker, period='5d')
                historical_df = historical_result.get('data')
                if historical_df is not None and len(historical_df) >= 2:
                    # Get second to last row (yesterday's data)
                    yesterday_close = historical_df.iloc[-2]['Close']
                    logger.debug(f"{ticker}: Yesterday's close: {yesterday_close:.2f}")
            except Exception as e:
                logger.warning(f"{ticker}: Could not fetch yesterday's close: {e}")

            stock_data[ticker] = {
                'current_price': data.get('close'),
                'open_price': data.get('open'),
                'vwap': data.get('vwap'),
                'yesterday_close': yesterday_close,
                'avg_price_5min': data.get('avg_price_5min'),
                'data_age_seconds': data.get('data_age_seconds', 0)
            }

        # Check for signals
        signals = self.signal_detector.check_batch(stock_data)

        # Save detected signals to database and create hypothetical trades
        for signal in signals:
            try:
                # Import hypothetical trade functions
                from src.utils.database import (
                    create_hypothetical_trade,
                    has_hypothetical_trade_today,
                    get_connection
                )

                # Save signal
                signal_id = save_signal(signal)
                logger.info(f"✓ Signal saved to database (ID: {signal_id})")

                # Create multiple hypothetical trades from the same signal (one per strategy)
                ticker = signal['ticker']
                trade_date = date.today()

                # Parse signal time to datetime
                signal_time = signal['signal_time']
                if isinstance(signal_time, str):
                    signal_time = datetime.fromisoformat(signal_time)

                # Load profit targets from config
                config = load_config()
                strategies_config = config.get('strategies', {})
                profit_targets_config = strategies_config.get('profit_targets', {})
                profit_targets = profit_targets_config.get('targets', [1.0, 2.0, 3.0, 4.0, 5.0])

                # Create trades in a transaction for atomicity
                conn = get_connection()
                try:
                    # Trade 1: EOD strategy
                    if not has_hypothetical_trade_today(ticker, trade_date, strategy_type='eod'):
                        eod_trade_id = create_hypothetical_trade(
                            ticker=ticker,
                            signal_id=signal_id,
                            entry_time=signal_time,
                            entry_price=signal['entry_price'],
                            trade_date=trade_date,
                            strategy_type='eod'
                        )
                        if eod_trade_id:
                            logger.info(f"✓ EOD trade created for {ticker} (ID: {eod_trade_id})")

                    # Trades 2-N: Profit target strategies
                    for target_pct in profit_targets:
                        strategy_type = f"{int(target_pct)}pct_target"

                        if not has_hypothetical_trade_today(ticker, trade_date, strategy_type=strategy_type):
                            target_trade_id = create_hypothetical_trade(
                                ticker=ticker,
                                signal_id=signal_id,
                                entry_time=signal_time,
                                entry_price=signal['entry_price'],
                                trade_date=trade_date,
                                strategy_type=strategy_type,
                                profit_target_pct=target_pct
                            )
                            if target_trade_id:
                                logger.info(f"✓ {int(target_pct)}% Target trade created for {ticker} (ID: {target_trade_id})")

                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise e
                finally:
                    conn.close()

            except Exception as e:
                logger.error(f"Error saving signal for {signal['ticker']}: {e}")

    def run(self, duration_minutes: int = None):
        """
        Run live monitoring loop.

        Args:
            duration_minutes: How long to run (None = run until stopped)
        """
        self.is_running = True

        # Load today's watchlist
        self.load_watchlist()

        if not self.watchlist_tickers:
            logger.warning("No tickers in watchlist, nothing to monitor")
            return

        logger.info(f"Starting live monitoring for {len(self.watchlist_tickers)} tickers")
        logger.info(f"Poll interval: {self.poll_interval} seconds")

        if duration_minutes:
            logger.info(f"Will run for {duration_minutes} minutes")

        start_time = datetime.now(self.timezone)
        poll_count = 0

        try:
            while self.is_running:
                # Check if we should stop (duration limit)
                if duration_minutes:
                    elapsed = (datetime.now(self.timezone) - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        logger.info(f"Duration limit reached ({duration_minutes} minutes)")
                        break

                # Check if we're in market hours
                if not self.is_market_hours():
                    logger.info("Outside market hours (09:00-17:30), waiting...")
                    time.sleep(60)  # Check again in 1 minute
                    continue

                # Poll all tickers
                poll_count += 1
                logger.info(f"=== Poll #{poll_count} at {datetime.now(self.timezone).strftime('%H:%M:%S')} ===")

                results = self.poll_watchlist()

                # Display summary
                if results:
                    logger.info("Current prices:")
                    for data in results:
                        vwap = data.get('vwap', 0)
                        current = data.get('close', 0)
                        change_pct = data.get('change_pct', 0)
                        logger.info(f"  {data['ticker']:12} - Price: {current:.2f}, VWAP: {vwap:.2f}, Change: {change_pct:+.2f}%")

                    # Check for entry signals (Phase 4)
                    self.check_signals(results)

                    # Check profit targets for 1pct_target strategy
                    self.check_profit_targets(results)

                # Wait for next poll
                logger.info(f"Waiting {self.poll_interval} seconds until next poll...")
                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}", exc_info=True)
        finally:
            self.is_running = False
            logger.info(f"Monitoring stopped after {poll_count} polls")

    def stop(self):
        """Stop the monitoring loop."""
        logger.info("Stop requested")
        self.is_running = False
