"""yfinance data provider implementation."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

from src.data.data_source import DataSource
from src.data.data_validator import DataValidator

logger = logging.getLogger(__name__)


class YFinanceProvider(DataSource):
    """Market data provider using yfinance library."""

    def __init__(self):
        """Initialize yfinance provider."""
        self.validator = DataValidator()
        logger.info("Initialized YFinanceProvider")

    def get_historical(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """
        Get historical OHLCV data using yfinance.

        Args:
            ticker: Stock ticker symbol (e.g., 'VOLV-B.ST')
            period: Data period ('1y', '6mo', '3mo', '1mo')
            interval: Data interval ('1d', '1h')

        Returns:
            Dictionary with data, quality_score, timestamp, errors
        """
        errors = []
        data = None
        quality_score = 0

        try:
            logger.debug(f"Fetching historical data for {ticker}, period={period}, interval={interval}")

            # Download data
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)

            if df.empty:
                errors.append(f"No data returned for {ticker}")
                logger.warning(f"Empty data returned for {ticker}")
            else:
                data = df
                # Validate data quality
                quality_score = self.validator.calculate_quality_score(df)
                logger.info(f"Fetched {len(df)} rows for {ticker}, quality score: {quality_score}")

        except Exception as e:
            error_msg = f"Error fetching data for {ticker}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

        return {
            'data': data,
            'quality_score': quality_score,
            'timestamp': datetime.now(timezone.utc),
            'errors': errors
        }

    def get_intraday(
        self,
        ticker: str,
        interval: str = "1m"
    ) -> Dict[str, Any]:
        """
        Get intraday data using yfinance.

        Args:
            ticker: Stock ticker symbol
            interval: Data interval ('1m', '5m', '15m')

        Returns:
            Dictionary with data, quality_score, timestamp, data_age_seconds, errors
        """
        errors = []
        data = None
        quality_score = 0
        data_age_seconds = None

        try:
            logger.debug(f"Fetching intraday data for {ticker}, interval={interval}")

            # Download 1 day of intraday data
            stock = yf.Ticker(ticker)
            df = stock.history(period="1d", interval=interval)

            if df.empty:
                errors.append(f"No intraday data returned for {ticker}")
                logger.warning(f"Empty intraday data for {ticker}")
            else:
                data = df
                quality_score = self.validator.calculate_quality_score(df)

                # Calculate data age
                if not df.empty:
                    latest_timestamp = df.index[-1]
                    # Convert to timezone-aware if needed
                    if latest_timestamp.tzinfo is None:
                        latest_timestamp = latest_timestamp.tz_localize('UTC')
                    now = datetime.now(timezone.utc)
                    data_age_seconds = int((now - latest_timestamp).total_seconds())

                    # Warn if data is stale
                    if data_age_seconds > 120:
                        warning = f"Data is {data_age_seconds}s old (stale)"
                        errors.append(warning)
                        logger.warning(f"{ticker}: {warning}")

                logger.info(f"Fetched {len(df)} intraday rows for {ticker}, age: {data_age_seconds}s")

        except Exception as e:
            error_msg = f"Error fetching intraday data for {ticker}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

        return {
            'data': data,
            'quality_score': quality_score,
            'timestamp': datetime.now(timezone.utc),
            'data_age_seconds': data_age_seconds,
            'errors': errors
        }

    def get_current_price(self, ticker: str) -> Dict[str, Any]:
        """
        Get current price using yfinance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with price, timestamp, data_age_seconds, errors
        """
        errors = []
        price = None
        data_age_seconds = None

        try:
            logger.debug(f"Fetching current price for {ticker}")

            stock = yf.Ticker(ticker)

            # Try to get from info first (faster)
            try:
                info = stock.info
                price = info.get('currentPrice') or info.get('regularMarketPrice')
            except:
                pass

            # Fallback to recent history
            if price is None:
                df = stock.history(period="1d", interval="1m")
                if not df.empty:
                    price = df['Close'].iloc[-1]

                    # Calculate data age
                    latest_timestamp = df.index[-1]
                    if latest_timestamp.tzinfo is None:
                        latest_timestamp = latest_timestamp.tz_localize('UTC')
                    now = datetime.now(timezone.utc)
                    data_age_seconds = int((now - latest_timestamp).total_seconds())

            if price is None:
                errors.append(f"Could not fetch price for {ticker}")
                logger.warning(f"No price available for {ticker}")
            else:
                logger.debug(f"Current price for {ticker}: {price}")

        except Exception as e:
            error_msg = f"Error fetching price for {ticker}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

        return {
            'price': price,
            'timestamp': datetime.now(timezone.utc),
            'data_age_seconds': data_age_seconds,
            'errors': errors
        }

    def is_available(self) -> bool:
        """
        Check if yfinance is available by testing a known ticker.

        Returns:
            True if yfinance can fetch data
        """
        try:
            # Test with a well-known ticker
            result = self.get_current_price("AAPL")
            return result['price'] is not None
        except:
            return False
