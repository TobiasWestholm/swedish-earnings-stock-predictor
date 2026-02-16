"""Historical data fetching and earnings day detection."""

import pandas as pd
import logging
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from src.data.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


class EarningsDayDetector:
    """
    Detects actual earnings report days using yfinance earnings_dates.

    Uses yfinance's built-in earnings calendar data which provides
    historical earnings report dates with EPS estimates and reported EPS.
    """

    def __init__(self, data_provider: YFinanceProvider = None):
        """Initialize detector."""
        self.data_provider = data_provider or YFinanceProvider()

    def scan_period(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Scan a time period for actual earnings report days.

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of dictionaries with earnings days
        """
        logger.info(f"Fetching earnings dates for {ticker} from {start_date} to {end_date}")

        try:
            # Use yfinance to get historical earnings dates
            ticker_obj = yf.Ticker(ticker)

            # Get earnings dates (default limit is 25, but we can get more)
            earnings_df = ticker_obj.earnings_dates

            if earnings_df is None or earnings_df.empty:
                logger.warning(f"No earnings dates found for {ticker}")
                return []

            logger.info(f"Found {len(earnings_df)} total earnings dates for {ticker}")

            # Convert date range to datetime
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)

            # Filter earnings dates to the specified period
            # earnings_df index is already datetime with timezone
            earnings_in_period = earnings_df[
                (earnings_df.index.date >= start_dt.date()) &
                (earnings_df.index.date <= end_dt.date())
            ]

            earnings_days = []

            for earnings_date in earnings_in_period.index:
                # Convert to date string (just the date part, ignore time/timezone)
                date_str = earnings_date.date().strftime('%Y-%m-%d')

                # Get EPS data if available
                eps_estimate = earnings_in_period.loc[earnings_date, 'EPS Estimate']
                reported_eps = earnings_in_period.loc[earnings_date, 'Reported EPS']
                surprise_pct = earnings_in_period.loc[earnings_date, 'Surprise(%)']

                earnings_days.append({
                    'ticker': ticker,
                    'date': date_str,
                    'earnings_datetime': earnings_date.isoformat(),
                    'eps_estimate': float(eps_estimate) if pd.notna(eps_estimate) else None,
                    'reported_eps': float(reported_eps) if pd.notna(reported_eps) else None,
                    'surprise_pct': float(surprise_pct) if pd.notna(surprise_pct) else None
                })

                logger.info(
                    f"✓ Earnings date found: {ticker} on {date_str} "
                    f"(EPS Est: {eps_estimate if pd.notna(eps_estimate) else 'N/A'}, "
                    f"Reported: {reported_eps if pd.notna(reported_eps) else 'N/A'})"
                )

            logger.info(f"Found {len(earnings_days)} earnings dates for {ticker} in specified period")
            return earnings_days

        except Exception as e:
            logger.error(f"Error fetching earnings dates for {ticker}: {e}")
            return []
