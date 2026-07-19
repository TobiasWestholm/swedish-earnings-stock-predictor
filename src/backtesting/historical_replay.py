#!/usr/bin/env python3
"""
Historical replay module for backtesting missed days.

When the app is down, this replays the entire trading strategy:
1. Runs screener on historical data (determines filter-passed stocks)
2. Simulates live monitor on historical intraday data (detects signals)
3. Creates hypothetical trades based on detected signals
4. Closes trades based on strategy rules (profit targets or EOD)

This ensures complete data for visualization even when app is offline.
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Tuple
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


class HistoricalReplay:
    """Replays trading strategy on historical data for missed days."""

    def __init__(self):
        """Initialize historical replay."""
        from src.utils.config import load_config
        self.config = load_config()

    def replay_day(self, target_date: date) -> Dict[str, Any]:
        """
        Replay the entire trading day using historical data.

        Args:
            target_date: Date to replay

        Returns:
            Statistics about the replay:
            {
                'screener_passed': int,
                'signals_detected': int,
                'trades_created': int,
                'trades_closed': int
            }
        """
        logger.info(f"=" * 70)
        logger.info(f"HISTORICAL REPLAY: {target_date}")
        logger.info(f"=" * 70)

        stats = {
            'screener_passed': 0,
            'signals_detected': 0,
            'trades_created': 0,
            'trades_closed': 0
        }

        # Step 1: Run screener on historical data
        logger.info("Step 1: Running screener on historical data...")
        watchlist = self._run_historical_screener(target_date)
        stats['screener_passed'] = len(watchlist)
        logger.info(f"  ✓ {len(watchlist)} stocks passed filter")

        if len(watchlist) == 0:
            logger.info("  No stocks passed filter, skipping signal detection")
            return stats

        # Step 2: Detect signals on historical intraday data
        logger.info("\nStep 2: Detecting signals on historical intraday data...")
        signals = self._detect_historical_signals(target_date, watchlist)
        stats['signals_detected'] = len(signals)
        logger.info(f"  ✓ {len(signals)} signals detected")

        if len(signals) == 0:
            logger.info("  No signals detected")
            return stats

        # Step 3: Create hypothetical trades from signals
        logger.info("\nStep 3: Creating hypothetical trades...")
        trades_created = self._create_historical_trades(target_date, signals)
        stats['trades_created'] = trades_created
        logger.info(f"  ✓ {trades_created} trades created")

        # Step 4: Close trades based on strategy rules
        logger.info("\nStep 4: Closing trades based on historical data...")
        trades_closed = self._close_historical_trades(target_date)
        stats['trades_closed'] = trades_closed
        logger.info(f"  ✓ {trades_closed} trades closed")

        logger.info(f"\nReplay complete for {target_date}")
        logger.info(f"=" * 70)

        return stats

    def _run_historical_screener(self, target_date: date) -> List[Dict[str, Any]]:
        """
        Run screener on historical data to determine which stocks would have passed.

        Args:
            target_date: Date to screen for

        Returns:
            List of stocks that passed the filter
        """
        from src.screening.screener import Screener

        # Run the screener for this historical date
        # The screener already has run_and_save which handles everything
        screener = Screener()
        watchlist = screener.run_and_save(target_date)

        logger.info(f"  Screener found {len(watchlist)} stocks that passed filter")

        return watchlist

    def _detect_historical_signals(
        self,
        target_date: date,
        watchlist: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect signals by simulating live monitor on historical intraday data.

        Args:
            target_date: Date to check
            watchlist: Stocks that passed filter

        Returns:
            List of detected signals
        """
        from src.monitoring.signal_detector import SignalDetector
        from src.utils.database import save_signal

        signals = []
        detector = SignalDetector()

        # For each stock on watchlist, check intraday data for signals
        for stock in watchlist:
            ticker = stock['ticker']

            try:
                # Fetch historical intraday data
                intraday_data = self._get_historical_intraday(ticker, target_date)

                if not intraday_data:
                    logger.debug(f"  {ticker}: No intraday data")
                    continue

                # Simulate monitoring window (09:20 - 10:00)
                for data_point in intraday_data:
                    timestamp = data_point['timestamp']
                    time_of_day = timestamp.time()

                    # Only check within signal window
                    if not (datetime.strptime('09:20', '%H:%M').time() <= time_of_day <=
                           datetime.strptime('10:00', '%H:%M').time()):
                        continue

                    # Check if signal conditions met
                    signal_data = {
                        'current_price': data_point['price'],
                        'volume': data_point.get('volume', 0),
                        'vwap': data_point.get('vwap'),
                        'open_price': data_point.get('open_price'),
                        'yesterday_close': stock.get('yesterday_close'),
                        'data_age_seconds': 0  # Historical data
                    }

                    signal_detected = detector.check_signal(ticker=ticker, data=signal_data)

                    if signal_detected:
                        # Calculate % from yesterday
                        pct_from_yesterday = None
                        if stock.get('yesterday_close'):
                            pct_from_yesterday = ((data_point['price'] - stock['yesterday_close']) /
                                                stock['yesterday_close']) * 100

                        # Save signal to database
                        signal_data_to_save = {
                            'ticker': ticker,
                            'signal_time': timestamp,
                            'entry_price': data_point['price'],
                            'vwap': data_point.get('vwap'),
                            'open_price': data_point.get('open_price'),
                            'yesterday_close': stock.get('yesterday_close'),
                            'pct_from_yesterday': pct_from_yesterday,
                            'data_age_seconds': 0,
                            'conditions': signal_detected.get('conditions', {}),
                            'confidence_score': signal_detected.get('confidence', 100.0)
                        }

                        signal_id = save_signal(signal_data_to_save)

                        signals.append({
                            'signal_id': signal_id,
                            'ticker': ticker,
                            'signal_time': timestamp,
                            'entry_price': data_point['price']
                        })

                        logger.info(f"  ✓ {ticker}: Signal at {timestamp.strftime('%H:%M')} @ {data_point['price']:.2f}")
                        break  # Only take first signal per stock

            except Exception as e:
                logger.error(f"  {ticker}: Error detecting signals: {e}")

        return signals

    def _get_historical_intraday(
        self,
        ticker: str,
        target_date: date
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical intraday data for a specific date.

        Args:
            ticker: Stock ticker
            target_date: Date to fetch

        Returns:
            List of intraday data points
        """
        try:
            start_date = target_date.strftime('%Y-%m-%d')
            end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date, interval='1m')

            if df is None or len(df) == 0:
                return []

            # Filter for market hours
            try:
                df = df.between_time('09:00', '17:30')
            except:
                pass

            # Convert to list of dicts
            intraday_data = []
            for timestamp, row in df.iterrows():
                intraday_data.append({
                    'timestamp': timestamp.to_pydatetime(),
                    'price': float(row['Close']),
                    'volume': int(row['Volume']) if 'Volume' in row else 0,
                    'open_price': float(row['Open']) if 'Open' in row else None,
                    'high': float(row['High']) if 'High' in row else None,
                    'low': float(row['Low']) if 'Low' in row else None,
                    'vwap': None  # Would need to calculate if needed
                })

            return intraday_data

        except Exception as e:
            logger.error(f"Error fetching intraday data for {ticker}: {e}")
            return []

    def _create_historical_trades(
        self,
        target_date: date,
        signals: List[Dict[str, Any]]
    ) -> int:
        """
        Create hypothetical trades from detected signals.

        Args:
            target_date: Date of trades
            signals: Detected signals

        Returns:
            Number of trades created
        """
        from src.utils.database import create_hypothetical_trade

        trades_created = 0

        # Get profit targets from config
        strategies_config = self.config.get('strategies', {})
        profit_targets_config = strategies_config.get('profit_targets', {})
        profit_targets = profit_targets_config.get('targets', [1.0, 2.0, 3.0, 4.0, 5.0])

        for signal in signals:
            ticker = signal['ticker']
            signal_time = signal['signal_time']
            entry_price = signal['entry_price']
            signal_id = signal.get('signal_id')

            # Create EOD trade
            try:
                trade_id = create_hypothetical_trade(
                    ticker=ticker,
                    signal_id=signal_id,
                    entry_time=signal_time,
                    entry_price=entry_price,
                    trade_date=target_date,
                    strategy_type='eod',
                    profit_target_pct=None
                )

                if trade_id:
                    trades_created += 1
                    logger.debug(f"  Created EOD trade for {ticker}")

            except Exception as e:
                logger.error(f"  Error creating EOD trade for {ticker}: {e}")

            # Create profit target trades
            for target_pct in profit_targets:
                try:
                    strategy_type = f"{int(target_pct)}pct_target"
                    trade_id = create_hypothetical_trade(
                        ticker=ticker,
                        signal_id=signal_id,
                        entry_time=signal_time,
                        entry_price=entry_price,
                        trade_date=target_date,
                        strategy_type=strategy_type,
                        profit_target_pct=target_pct
                    )

                    if trade_id:
                        trades_created += 1
                        logger.debug(f"  Created {strategy_type} trade for {ticker}")

                except Exception as e:
                    logger.error(f"  Error creating {strategy_type} trade for {ticker}: {e}")

        return trades_created

    def _close_historical_trades(self, target_date: date) -> int:
        """
        Close trades based on historical data and strategy rules.

        Args:
            target_date: Date to close trades for

        Returns:
            Number of trades closed
        """
        from src.utils.database import (
            get_open_hypothetical_trades,
            close_hypothetical_trade,
            get_connection
        )
        import pytz

        trades_closed = 0
        timezone = pytz.timezone('Europe/Stockholm')

        # Get all open trades for this date
        all_open_trades = get_open_hypothetical_trades(target_date)

        if not all_open_trades:
            return 0

        # Group trades by ticker to minimize API calls
        trades_by_ticker = {}
        for trade in all_open_trades:
            ticker = trade['ticker']
            if ticker not in trades_by_ticker:
                trades_by_ticker[ticker] = []
            trades_by_ticker[ticker].append(trade)

        # Process each ticker
        for ticker, ticker_trades in trades_by_ticker.items():
            try:
                # Fetch historical intraday data
                intraday_data = self._get_historical_intraday(ticker, target_date)

                if not intraday_data:
                    logger.warning(f"  {ticker}: No intraday data for closing")
                    continue

                # Get entry time from first trade
                entry_time = ticker_trades[0]['entry_time']
                if isinstance(entry_time, str):
                    entry_time = datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S')

                # Filter data to after entry time
                post_entry_data = [
                    d for d in intraday_data
                    if d['timestamp'] > entry_time
                ]

                if not post_entry_data:
                    logger.warning(f"  {ticker}: No data after entry time")
                    continue

                # Close each trade based on its strategy
                for trade in ticker_trades:
                    trade_id = trade['id']
                    entry_price = trade['entry_price']
                    strategy_type = trade.get('strategy_type', 'eod')
                    profit_target = trade.get('profit_target_pct')

                    exit_time = None
                    exit_price = None
                    exit_reason = None

                    if strategy_type == 'eod':
                        # Close at EOD (last available price)
                        exit_time = post_entry_data[-1]['timestamp']
                        exit_price = post_entry_data[-1]['price']
                        exit_reason = 'eod'

                    elif profit_target:
                        # Check if profit target hit
                        target_price = entry_price * (1 + profit_target / 100)

                        for data_point in post_entry_data:
                            if data_point['price'] >= target_price:
                                exit_time = data_point['timestamp']
                                exit_price = data_point['price']
                                exit_reason = 'profit_target'
                                break

                        # If target not hit, close at EOD
                        if not exit_time:
                            exit_time = post_entry_data[-1]['timestamp']
                            exit_price = post_entry_data[-1]['price']
                            exit_reason = 'eod_fallback'

                    if exit_time and exit_price:
                        success = close_hypothetical_trade(
                            trade_id=trade_id,
                            exit_time=exit_time,
                            exit_price=exit_price,
                            exit_reason=exit_reason
                        )

                        if success:
                            trades_closed += 1
                            pnl = ((exit_price - entry_price) / entry_price) * 100
                            logger.debug(f"  Closed {ticker} ({strategy_type}): {pnl:+.2f}%")

            except Exception as e:
                logger.error(f"  Error closing trades for {ticker}: {e}")

        return trades_closed
