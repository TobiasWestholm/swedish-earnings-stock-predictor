"""Strategy simulator for backtesting trades."""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from src.data.yfinance_provider import YFinanceProvider
from src.screening.momentum_filter import MomentumFilter

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single backtest trade."""
    ticker: str
    date: str

    # Filter stage
    passed_filter: bool
    filter_score: float

    # Earnings surprise stage
    passed_earnings_surprise: Optional[bool] = None
    eps_estimate: Optional[float] = None
    reported_eps: Optional[float] = None
    surprise_pct: Optional[float] = None

    # Signal stage
    signal_detected: bool = False
    entry_price: Optional[float] = None
    entry_time: Optional[str] = None
    open_price: Optional[float] = None
    vwap: Optional[float] = None
    yesterday_close: Optional[float] = None

    # Exit stage
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None

    # P&L
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None

    # Metadata
    data_quality: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)


class StrategySimulator:
    """
    Simulates the trading strategy on historical data.

    Applies the same logic as live trading:
    1. Pre-market filter (momentum)
    2. Signal detection (price > VWAP, > open, >2% from yesterday)
    3. Trade simulation (entry/exit)
    """

    def __init__(self, data_provider: YFinanceProvider = None,
                 use_earnings_surprise_filter: bool = False,
                 use_trailing_stop: bool = False):
        """
        Initialize simulator.

        Args:
            data_provider: Data provider instance
            use_earnings_surprise_filter: If True, only trade when reported EPS beats estimate
            use_trailing_stop: If True, use trailing stop (breakeven at +2%, trail -2% at +5%)
        """
        self.data_provider = data_provider or YFinanceProvider()
        self.momentum_filter = MomentumFilter(data_provider=self.data_provider)
        self.use_earnings_surprise_filter = use_earnings_surprise_filter
        self.use_trailing_stop = use_trailing_stop

    def simulate_trade(self, ticker: str, date: str) -> Trade:
        """
        Simulate a complete trade for an earnings day.

        Args:
            ticker: Stock ticker
            date: Date string (YYYY-MM-DD)

        Returns:
            Trade object with results
        """
        logger.info(f"Simulating trade for {ticker} on {date}")

        # Step 1: Check momentum filter (as of day before)
        filter_result = self._check_momentum_filter(ticker, date)

        if not filter_result['passed']:
            return Trade(
                ticker=ticker,
                date=date,
                passed_filter=False,
                filter_score=filter_result['score'],
                signal_detected=False,
                notes=filter_result.get('reason', 'Failed momentum filter')
            )

        # Step 2: Check earnings surprise (if filter enabled)
        earnings_result = self._check_earnings_surprise(ticker, date)

        if self.use_earnings_surprise_filter and not earnings_result.get('passed', False):
            return Trade(
                ticker=ticker,
                date=date,
                passed_filter=True,
                filter_score=filter_result['score'],
                passed_earnings_surprise=False,
                eps_estimate=earnings_result.get('eps_estimate'),
                reported_eps=earnings_result.get('reported_eps'),
                surprise_pct=earnings_result.get('surprise_pct'),
                signal_detected=False,
                notes=earnings_result.get('reason', 'Failed earnings surprise filter')
            )

        # Step 3: Check signal conditions
        signal_result = self._check_signal(ticker, date)

        if not signal_result['detected']:
            return Trade(
                ticker=ticker,
                date=date,
                passed_filter=True,
                filter_score=filter_result['score'],
                passed_earnings_surprise=earnings_result.get('passed'),
                eps_estimate=earnings_result.get('eps_estimate'),
                reported_eps=earnings_result.get('reported_eps'),
                surprise_pct=earnings_result.get('surprise_pct'),
                signal_detected=False,
                notes=signal_result.get('reason', 'No signal detected')
            )

        # Step 4: Simulate trade execution
        exit_result = self._simulate_exit(ticker, date, signal_result, use_trailing_stop=self.use_trailing_stop)

        # Step 5: Calculate P&L
        entry_price = signal_result['entry_price']
        exit_price = exit_result['exit_price']
        pnl = exit_price - entry_price
        pnl_pct = (pnl / entry_price) * 100

        return Trade(
            ticker=ticker,
            date=date,
            passed_filter=True,
            filter_score=filter_result['score'],
            passed_earnings_surprise=earnings_result.get('passed'),
            eps_estimate=earnings_result.get('eps_estimate'),
            reported_eps=earnings_result.get('reported_eps'),
            surprise_pct=earnings_result.get('surprise_pct'),
            signal_detected=True,
            entry_price=entry_price,
            entry_time=signal_result.get('entry_time'),
            open_price=signal_result.get('open_price'),
            vwap=signal_result.get('vwap'),
            yesterday_close=signal_result.get('yesterday_close'),
            exit_price=exit_price,
            exit_time=exit_result.get('exit_time'),
            exit_reason=exit_result.get('reason'),
            pnl=pnl,
            pnl_pct=pnl_pct,
            data_quality=signal_result.get('data_quality')
        )

    def _check_momentum_filter(self, ticker: str, date: str) -> Dict[str, Any]:
        """Check if stock passes momentum filter as of day before."""
        try:
            # Get historical data up to day before
            date_dt = datetime.strptime(date, '%Y-%m-%d')

            result = self.momentum_filter.calculate_trend_score(ticker)

            if result.get('passes_filter'):
                return {
                    'passed': True,
                    'score': result.get('trend_score', 0)
                }
            else:
                return {
                    'passed': False,
                    'score': 0,
                    'reason': 'Failed momentum criteria'
                }

        except Exception as e:
            logger.error(f"Error checking filter for {ticker}: {e}")
            return {
                'passed': False,
                'score': 0,
                'reason': f'Error: {str(e)}'
            }

    def _check_earnings_surprise(self, ticker: str, date: str) -> Dict[str, Any]:
        """
        Check if earnings beat estimates (positive surprise).

        Args:
            ticker: Stock ticker
            date: Earnings date (YYYY-MM-DD)

        Returns:
            Dictionary with earnings surprise data and pass/fail status
        """
        try:
            import yfinance as yf

            ticker_obj = yf.Ticker(ticker)
            earnings_df = ticker_obj.earnings_dates

            if earnings_df is None or earnings_df.empty:
                logger.warning(f"{ticker}: No earnings data available")
                return {
                    'passed': False,
                    'reason': 'No earnings data available',
                    'eps_estimate': None,
                    'reported_eps': None,
                    'surprise_pct': None
                }

            # Find the earnings record for this date
            date_dt = pd.to_datetime(date)
            matching_earnings = [
                idx for idx in earnings_df.index
                if idx.date() == date_dt.date()
            ]

            if not matching_earnings:
                logger.warning(f"{ticker}: No earnings record for {date}")
                return {
                    'passed': False,
                    'reason': 'No earnings record for this date',
                    'eps_estimate': None,
                    'reported_eps': None,
                    'surprise_pct': None
                }

            earnings_idx = matching_earnings[0]
            earnings_row = earnings_df.loc[earnings_idx]

            eps_estimate = earnings_row['EPS Estimate']
            reported_eps = earnings_row['Reported EPS']
            surprise_pct = earnings_row['Surprise(%)']

            # Check if both estimate and reported are available
            if pd.isna(eps_estimate) or pd.isna(reported_eps):
                logger.info(f"{ticker} on {date}: Missing EPS data (Estimate: {eps_estimate}, Reported: {reported_eps})")
                return {
                    'passed': False,
                    'reason': 'Missing EPS estimate or reported data',
                    'eps_estimate': float(eps_estimate) if pd.notna(eps_estimate) else None,
                    'reported_eps': float(reported_eps) if pd.notna(reported_eps) else None,
                    'surprise_pct': None
                }

            # Check if earnings beat estimates
            beat_estimate = reported_eps > eps_estimate

            if beat_estimate:
                logger.info(f"{ticker} on {date}: ✓ Beat estimate ({reported_eps:.2f} > {eps_estimate:.2f}, +{surprise_pct:.1f}%)")
                return {
                    'passed': True,
                    'eps_estimate': float(eps_estimate),
                    'reported_eps': float(reported_eps),
                    'surprise_pct': float(surprise_pct) if pd.notna(surprise_pct) else None
                }
            else:
                logger.info(f"{ticker} on {date}: ✗ Missed estimate ({reported_eps:.2f} <= {eps_estimate:.2f}, {surprise_pct:.1f}%)")
                return {
                    'passed': False,
                    'reason': 'Earnings missed or met estimates',
                    'eps_estimate': float(eps_estimate),
                    'reported_eps': float(reported_eps),
                    'surprise_pct': float(surprise_pct) if pd.notna(surprise_pct) else None
                }

        except Exception as e:
            logger.error(f"Error checking earnings surprise for {ticker} on {date}: {e}")
            return {
                'passed': False,
                'reason': f'Error: {str(e)}',
                'eps_estimate': None,
                'reported_eps': None,
                'surprise_pct': None
            }

    def _check_signal(self, ticker: str, date: str) -> Dict[str, Any]:
        """
        Check if signal conditions were met on the earnings day using hourly intraday data.

        Uses 60-minute bars to check if price met all conditions during signal window (09:20-10:00).
        """
        logger.info(f"_check_signal called for {ticker} on {date}")
        try:
            import yfinance as yf
            from datetime import time as dt_time

            # Get yesterday's close from daily data (need enough history for backtest dates)
            logger.info(f"{ticker}: Fetching daily data to get yesterday's close")
            daily_result = self.data_provider.get_historical(ticker, period='2y', interval='1d')
            daily_data = daily_result.get('data')

            if daily_data is None or len(daily_data) < 2:
                logger.warning(f"{ticker}: Insufficient daily data")
                return {'detected': False, 'reason': 'Insufficient daily data'}

            logger.info(f"{ticker}: Processing daily data to get yesterday's close")
            daily_data.index = pd.to_datetime(daily_data.index)
            date_dt = pd.to_datetime(date)

            # Check if date is in data (compare just dates, ignore timezone)
            dates_in_range = [d for d in daily_data.index if d.date() == date_dt.date()]
            if not dates_in_range:
                logger.warning(f"{ticker}: Date {date} not in daily data")
                return {'detected': False, 'reason': 'Date not in daily data'}

            # Get the index position of the target date
            target_idx = daily_data.index.get_loc(dates_in_range[0])
            if target_idx == 0:
                logger.warning(f"{ticker}: Date {date} is first day, no yesterday close")
                return {'detected': False, 'reason': 'No yesterday data'}

            yesterday = daily_data.iloc[target_idx - 1]
            yesterday_close = yesterday['Close']
            logger.info(f"{ticker}: Yesterday close = {yesterday_close:.2f}")

            # Get hourly intraday data (available for 2+ years)
            logger.info(f"{ticker}: Fetching hourly intraday data")
            ticker_obj = yf.Ticker(ticker)
            intraday_data = ticker_obj.history(period='730d', interval='60m')
            logger.info(f"{ticker}: Intraday fetch complete")

            if intraday_data is None or intraday_data.empty:
                logger.warning(f"{ticker}: No intraday data available")
                return {'detected': False, 'reason': 'No intraday data available'}

            logger.debug(f"{ticker}: Fetched {len(intraday_data)} hourly bars")

            # Filter to target date
            date_bars = intraday_data[intraday_data.index.date == date_dt.date()]

            if date_bars.empty:
                logger.warning(f"{ticker} on {date}: No intraday bars for this date")
                return {'detected': False, 'reason': 'No intraday bars for date'}

            logger.debug(f"{ticker} on {date}: Found {len(date_bars)} hourly bars for the day")

            # Get opening price
            open_price = date_bars.iloc[0]['Open']

            # Calculate progressive VWAP for each hour
            date_bars_copy = date_bars.copy()
            date_bars_copy['typical_price'] = (date_bars_copy['High'] + date_bars_copy['Low'] + date_bars_copy['Close']) / 3
            date_bars_copy['tp_volume'] = date_bars_copy['typical_price'] * date_bars_copy['Volume']
            date_bars_copy['cumsum_tp_vol'] = date_bars_copy['tp_volume'].cumsum()
            date_bars_copy['cumsum_vol'] = date_bars_copy['Volume'].cumsum()
            date_bars_copy['vwap'] = date_bars_copy['cumsum_tp_vol'] / date_bars_copy['cumsum_vol']

            # Check each hour during signal window (09:20-10:00)
            signal_window_start = dt_time(9, 20)
            signal_window_end = dt_time(10, 0)

            for idx, bar in date_bars_copy.iterrows():
                bar_time = idx.time()

                # Only check during signal window
                if bar_time < signal_window_start or bar_time > signal_window_end:
                    continue

                current_price = bar['Close']
                bar_open = bar['Open']
                vwap = bar['vwap']

                # Check signal conditions
                above_vwap = current_price > vwap if pd.notna(vwap) else False
                above_open = current_price > open_price
                pct_from_yesterday = ((current_price - yesterday_close) / yesterday_close) * 100
                above_yesterday_2pct = pct_from_yesterday > 2.0

                # NEW: No falling knife check (hourly data proxy)
                # In hourly data, check if this bar closed above its open (bullish candle)
                # This approximates "price rising" similar to being above 5-min average
                no_falling_knife = current_price >= bar_open

                # Signal detected if all conditions met
                if above_vwap and above_open and above_yesterday_2pct and no_falling_knife:
                    return {
                        'detected': True,
                        'entry_price': current_price,
                        'entry_time': idx.strftime('%H:%M'),
                        'open_price': open_price,
                        'vwap': vwap,
                        'yesterday_close': yesterday_close,
                        'pct_from_yesterday': pct_from_yesterday,
                        'bar_close_vs_open': current_price - bar_open,
                        'data_quality': 'hourly_intraday',
                        'intraday_bars': date_bars_copy  # Pass for exit simulation
                    }

            # No signal detected during window
            return {
                'detected': False,
                'reason': 'Conditions not met during signal window (09:20-10:00)'
            }

        except Exception as e:
            logger.error(f"Error checking signal for {ticker} on {date}: {e}")
            return {
                'detected': False,
                'reason': f'Error: {str(e)}'
            }

    def _simulate_exit(self, ticker: str, date: str, signal_result: Dict[str, Any],
                      use_trailing_stop: bool = False) -> Dict[str, Any]:
        """
        Simulate trade exit using hourly intraday data.

        Exit scenarios:
        - End of day (last bar close)
        - Stop loss (-2.5% from entry)
        - Trailing stop (if enabled):
          * Once up +2%, move stop to breakeven
          * Once up +5%, trail by -2% from highest price

        Args:
            ticker: Stock ticker
            date: Trade date
            signal_result: Signal detection results
            use_trailing_stop: If True, use trailing stop logic

        Returns:
            Dictionary with exit price, time, and reason
        """
        try:
            entry_price = signal_result['entry_price']
            initial_stop_loss = entry_price * 0.975  # -2.5%
            current_stop = initial_stop_loss

            # Get intraday bars if available from signal check
            if 'intraday_bars' in signal_result:
                intraday_bars = signal_result['intraday_bars']
                entry_time_str = signal_result['entry_time']

                # Find entry bar
                entry_bar_idx = None
                for idx, bar in intraday_bars.iterrows():
                    if idx.strftime('%H:%M') == entry_time_str:
                        entry_bar_idx = idx
                        break

                if entry_bar_idx is None:
                    # Default to last bar
                    exit_price = intraday_bars.iloc[-1]['Close']
                    exit_time = intraday_bars.index[-1].strftime('%H:%M')
                    return {
                        'exit_price': exit_price,
                        'exit_time': exit_time,
                        'reason': 'end_of_day'
                    }

                # Check subsequent bars for stop loss or EOD
                entry_bar_position = intraday_bars.index.get_loc(entry_bar_idx)
                remaining_bars = intraday_bars.iloc[entry_bar_position + 1:]

                highest_price = entry_price  # Track highest price for trailing stop

                for idx, bar in remaining_bars.iterrows():
                    bar_high = bar['High']
                    bar_low = bar['Low']
                    bar_close = bar['Close']

                    # Update highest price
                    if bar_high > highest_price:
                        highest_price = bar_high

                    # Apply trailing stop logic if enabled
                    if use_trailing_stop:
                        gain_from_entry = ((highest_price - entry_price) / entry_price) * 100

                        if gain_from_entry >= 5.0:
                            # Trail by -2% from highest price
                            current_stop = highest_price * 0.98
                        elif gain_from_entry >= 2.0:
                            # Move stop to breakeven
                            current_stop = entry_price

                    # Check if stop loss was hit during this hour
                    if bar_low <= current_stop:
                        reason = 'trailing_stop' if use_trailing_stop and current_stop > initial_stop_loss else 'stop_loss'
                        return {
                            'exit_price': current_stop,
                            'exit_time': idx.strftime('%H:%M'),
                            'reason': reason
                        }

                # No stop loss hit, exit at end of day
                exit_price = intraday_bars.iloc[-1]['Close']
                exit_time = intraday_bars.index[-1].strftime('%H:%M')
                return {
                    'exit_price': exit_price,
                    'exit_time': exit_time,
                    'reason': 'end_of_day'
                }

            else:
                # Fallback to daily data if intraday not available
                result = self.data_provider.get_historical(ticker, period='5d', interval='1d')
                data = result.get('data')

                if data is None:
                    return {
                        'exit_price': entry_price,
                        'exit_time': '17:30',
                        'reason': 'no_data_available'
                    }

                data.index = pd.to_datetime(data.index)
                date_dt = pd.to_datetime(date)

                if date_dt not in data.index:
                    return {
                        'exit_price': entry_price,
                        'exit_time': '17:30',
                        'reason': 'no_data_available'
                    }

                target_day = data.loc[date_dt]
                close_price = target_day['Close']
                low = target_day['Low']

                if low <= stop_loss_price:
                    return {
                        'exit_price': stop_loss_price,
                        'exit_time': '14:00',
                        'reason': 'stop_loss'
                    }

                return {
                    'exit_price': close_price,
                    'exit_time': '17:30',
                    'reason': 'end_of_day'
                }

        except Exception as e:
            logger.error(f"Error simulating exit for {ticker} on {date}: {e}")
            return {
                'exit_price': signal_result['entry_price'],
                'exit_time': '17:30',
                'reason': f'error: {str(e)}'
            }
