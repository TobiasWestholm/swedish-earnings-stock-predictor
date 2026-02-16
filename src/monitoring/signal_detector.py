"""Signal detection logic for entry opportunities."""

from datetime import datetime, time as dt_time
from typing import Dict, Any, Optional
import logging
import pytz

logger = logging.getLogger(__name__)


class SignalDetector:
    """
    Detects entry signals during the signal window (09:20-10:00).

    Entry conditions:
    - Price above VWAP
    - Price above open
    - Price above yesterday close + 2%
    - Price above 5-minute average (no falling knife)
    - During signal window (09:20-10:00 CET)
    """

    def __init__(self, timezone: str = 'Europe/Stockholm'):
        """
        Initialize signal detector.

        Args:
            timezone: Timezone for signal window checking
        """
        self.timezone = pytz.timezone(timezone)
        self.signal_window_start = dt_time(9, 20)
        self.signal_window_end = dt_time(10, 0)

        logger.info(f"Initialized SignalDetector (window={self.signal_window_start}-{self.signal_window_end})")

    def is_signal_window(self, check_time: datetime = None) -> bool:
        """
        Check if current time is within signal detection window.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if within 09:30-09:45 window
        """
        if check_time is None:
            check_time = datetime.now(self.timezone)
        elif check_time.tzinfo is None:
            check_time = self.timezone.localize(check_time)

        current_time = check_time.time()

        # Check if it's a weekday
        is_weekday = check_time.weekday() < 5

        return is_weekday and self.signal_window_start <= current_time <= self.signal_window_end

    def check_signal(self, ticker: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if stock meets entry signal conditions.

        Args:
            ticker: Stock ticker symbol
            data: Dictionary with price data including:
                - current_price: Current stock price
                - open_price: Opening price
                - vwap: Volume weighted average price
                - yesterday_close: Previous day's closing price
                - avg_price_5min: 5-minute average price (optional)
                - data_age_seconds: Age of data in seconds

        Returns:
            Signal dictionary if conditions met, None otherwise
        """
        # Extract required fields
        current_price = data.get('current_price')
        open_price = data.get('open_price')
        vwap = data.get('vwap')
        yesterday_close = data.get('yesterday_close')
        avg_price_5min = data.get('avg_price_5min')
        data_age = data.get('data_age_seconds', 0)

        # Validate we have all required data
        if not all([current_price, open_price, vwap, yesterday_close]):
            logger.debug(f"{ticker}: Missing required data for signal check")
            return None

        # Check if we're in signal window
        if not self.is_signal_window():
            return None

        # Check signal conditions
        above_vwap = current_price > vwap
        above_open = current_price > open_price

        # Calculate percentage increase from yesterday's close
        pct_from_yesterday = ((current_price - yesterday_close) / yesterday_close) * 100
        above_yesterday_2pct = pct_from_yesterday > 2.0

        # NEW: Check if price is above 5-minute average (no falling knife)
        above_5min_avg = True  # Default to True if data not available
        if avg_price_5min is not None:
            above_5min_avg = current_price > avg_price_5min

        # All four conditions must be met
        if not (above_vwap and above_open and above_yesterday_2pct and above_5min_avg):
            logger.debug(
                f"{ticker}: Signal conditions not met "
                f"(above_vwap={above_vwap}, above_open={above_open}, "
                f"above_yesterday_2pct={above_yesterday_2pct}, pct_from_yesterday={pct_from_yesterday:.2f}%, "
                f"above_5min_avg={above_5min_avg})"
            )
            return None

        # Calculate metrics
        vwap_distance = ((current_price - vwap) / vwap) * 100  # Percentage above VWAP
        open_distance = ((current_price - open_price) / open_price) * 100  # Percentage above open

        # Calculate confidence score (0-1)
        # Higher confidence if:
        # - Price comfortably above both VWAP and open (but not too extended)
        # - Data is fresh
        confidence = 0.5  # Base confidence

        # Bonus for being above VWAP (up to +0.2)
        if vwap_distance > 0:
            confidence += min(vwap_distance / 2, 0.2)

        # Bonus for being above open (up to +0.2)
        if open_distance > 0:
            confidence += min(open_distance / 2, 0.2)

        # Penalty for stale data (down to -0.3)
        if data_age > 120:  # More than 2 minutes old
            confidence -= min((data_age - 120) / 600, 0.3)

        # Clamp confidence to 0-1
        confidence = max(0, min(1, confidence))

        # Build signal dictionary
        signal = {
            'ticker': ticker,
            'signal_time': datetime.now(self.timezone).isoformat(),
            'entry_price': current_price,
            'open_price': open_price,
            'vwap': vwap,
            'yesterday_close': yesterday_close,
            'avg_price_5min': avg_price_5min,
            'pct_from_yesterday': pct_from_yesterday,
            'vwap_distance_pct': vwap_distance,
            'open_distance_pct': open_distance,
            'data_age_seconds': data_age,
            'confidence_score': confidence,
            'conditions': {
                'above_vwap': bool(above_vwap),
                'above_open': bool(above_open),
                'above_yesterday_2pct': bool(above_yesterday_2pct),
                'above_5min_avg': bool(above_5min_avg),
                'data_fresh': bool(data_age < 120)
            }
        }

        logger.info(
            f"🔔 SIGNAL DETECTED: {ticker} @ {current_price:.2f} SEK "
            f"(VWAP: {vwap:.2f}, Open: {open_price:.2f}, "
            f"Confidence: {confidence:.0%})"
        )

        return signal

    def check_batch(self, stock_data: Dict[str, Dict[str, Any]]) -> list:
        """
        Check multiple stocks for signals.

        Args:
            stock_data: Dictionary mapping ticker -> data dict

        Returns:
            List of signal dictionaries for stocks meeting conditions
        """
        signals = []

        for ticker, data in stock_data.items():
            signal = self.check_signal(ticker, data)
            if signal:
                signals.append(signal)

        return signals
