"""Momentum and trend filtering for stock screening."""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

from src.data.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


class MomentumFilter:
    """Calculates momentum and trend metrics for stock filtering."""

    def __init__(self, data_provider: YFinanceProvider = None):
        """
        Initialize momentum filter.

        Args:
            data_provider: Data provider instance (defaults to YFinanceProvider)
        """
        self.data_provider = data_provider or YFinanceProvider()

        # Load config
        from src.utils.config import load_config
        config = load_config()
        screening_config = config.get('screening', {})

        self.lookback_3m = screening_config.get('momentum_lookback_3m', 63)
        self.lookback_1y = screening_config.get('momentum_lookback_1y', 252)
        self.sma_period = screening_config.get('sma_period', 200)
        self.require_both = screening_config.get('require_both_momentum', True)
        self.min_score = screening_config.get('min_trend_score', 60)

        logger.info(f"Initialized MomentumFilter (3M={self.lookback_3m}, 1Y={self.lookback_1y}, SMA={self.sma_period})")

    def calculate_trend_score(self, ticker: str) -> Dict[str, Any]:
        """
        Calculate comprehensive trend score for a ticker.

        User confirmed: Both 3M AND 1Y must be positive (stricter filter).

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with:
                - passes_filter: True if passes all binary filters
                - trend_score: Quality score 0-100 (60-100 if passes filter)
                - price_above_sma200: Boolean
                - return_3m: 3-month return (decimal)
                - return_1y: 1-year return (decimal)
                - sma_200: 200-day SMA value
                - current_price: Current price
                - errors: List of errors
        """
        result = {
            'passes_filter': False,
            'trend_score': 0,
            'price_above_sma200': False,
            'return_3m': None,
            'return_1y': None,
            'sma_200': None,
            'current_price': None,
            'yesterday_close': None,
            'errors': []
        }

        try:
            # Fetch 1 year of daily data
            data_result = self.data_provider.get_historical(
                ticker=ticker,
                period='1y',
                interval='1d'
            )

            if data_result['errors']:
                result['errors'].extend(data_result['errors'])

            df = data_result['data']

            if df is None or df.empty or len(df) < self.sma_period:
                result['errors'].append(f"Insufficient data for {ticker} (need {self.sma_period} days)")
                logger.warning(f"Insufficient data for {ticker}")
                return result

            # Calculate 200-day SMA
            df['SMA_200'] = df['Close'].rolling(window=self.sma_period).mean()

            # Get current values
            current_price = df['Close'].iloc[-1]
            sma_200 = df['SMA_200'].iloc[-1]

            # Get yesterday's close (for reference in watchlist)
            yesterday_close = df['Close'].iloc[-2] if len(df) >= 2 else current_price

            result['current_price'] = float(current_price)
            result['yesterday_close'] = float(yesterday_close)
            result['sma_200'] = float(sma_200) if not pd.isna(sma_200) else None

            # Binary filter 1: Price above SMA200
            price_above_sma200 = current_price > sma_200 if not pd.isna(sma_200) else False
            result['price_above_sma200'] = price_above_sma200

            # Calculate returns
            # 3-month return
            if len(df) >= self.lookback_3m:
                price_3m_ago = df['Close'].iloc[-self.lookback_3m]
                return_3m = (current_price - price_3m_ago) / price_3m_ago
                result['return_3m'] = float(return_3m)
            else:
                result['errors'].append(f"Insufficient data for 3M return")
                return result

            # 1-year return
            if len(df) >= self.lookback_1y:
                price_1y_ago = df['Close'].iloc[-self.lookback_1y]
                return_1y = (current_price - price_1y_ago) / price_1y_ago
                result['return_1y'] = float(return_1y)
            else:
                result['errors'].append(f"Insufficient data for 1Y return")
                return result

            # Binary filter 2: 3M return positive
            return_3m_positive = return_3m > 0

            # Binary filter 3: 1Y return positive
            return_1y_positive = return_1y > 0

            # USER CONFIRMED: All three must be true (stricter filter)
            passes_filter = price_above_sma200 and return_3m_positive and return_1y_positive

            result['passes_filter'] = passes_filter

            if not passes_filter:
                # Fails filter, score remains 0
                logger.debug(f"{ticker} fails momentum filter (SMA200={price_above_sma200}, 3M={return_3m_positive}, 1Y={return_1y_positive})")
                return result

            # Calculate quality score (60-100 for stocks that pass filter)
            score = 0

            # 30 points for being above SMA200 (already true)
            score += 30

            # 40 points max for 3M momentum strength
            if return_3m > 0.10:  # >10%
                score += 40
            elif return_3m > 0.05:  # >5%
                score += 30
            else:  # >0%
                score += 20

            # 30 points max for 1Y momentum strength
            if return_1y > 0.20:  # >20%
                score += 30
            elif return_1y > 0.10:  # >10%
                score += 20
            else:  # >0%
                score += 10

            result['trend_score'] = score

            logger.info(f"{ticker}: Score={score}, 3M={return_3m:.2%}, 1Y={return_1y:.2%}, Price={current_price:.2f}, SMA200={sma_200:.2f}")

        except Exception as e:
            error_msg = f"Error calculating trend for {ticker}: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg)

        return result

    def filter_stocks(self, tickers: list) -> Dict[str, Dict[str, Any]]:
        """
        Filter multiple stocks by momentum criteria.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker to trend results
        """
        results = {}

        logger.info(f"Filtering {len(tickers)} stocks by momentum")

        for ticker in tickers:
            try:
                trend_result = self.calculate_trend_score(ticker)
                results[ticker] = trend_result
            except Exception as e:
                logger.error(f"Error filtering {ticker}: {e}")
                results[ticker] = {
                    'passes_filter': False,
                    'trend_score': 0,
                    'errors': [str(e)]
                }

        # Count passing stocks
        passing = sum(1 for r in results.values() if r['passes_filter'])
        logger.info(f"Momentum filter: {passing}/{len(tickers)} stocks passed")

        return results
