"""Abstract data source interface for market data."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
from datetime import datetime


class DataSource(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    def get_historical(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> Dict[str, Any]:
        """
        Get historical OHLCV data for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Data period (e.g., '1y', '6mo', '3mo')
            interval: Data interval (e.g., '1d', '1h', '1m')

        Returns:
            Dictionary with:
                - data: pandas DataFrame with OHLCV data
                - quality_score: Data quality score (0-100)
                - timestamp: When data was fetched
                - errors: List of any errors encountered
        """
        pass

    @abstractmethod
    def get_intraday(
        self,
        ticker: str,
        interval: str = "1m"
    ) -> Dict[str, Any]:
        """
        Get intraday data for a ticker.

        Args:
            ticker: Stock ticker symbol
            interval: Data interval ('1m', '5m', '15m')

        Returns:
            Dictionary with:
                - data: pandas DataFrame with OHLCV data
                - quality_score: Data quality score (0-100)
                - timestamp: When data was fetched
                - data_age_seconds: Age of most recent data point
                - errors: List of any errors encountered
        """
        pass

    @abstractmethod
    def get_current_price(self, ticker: str) -> Dict[str, Any]:
        """
        Get current price for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with:
                - price: Current price
                - timestamp: When price was fetched
                - data_age_seconds: Estimated data staleness
                - errors: List of any errors encountered
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the data source is available.

        Returns:
            True if data source can be accessed
        """
        pass
