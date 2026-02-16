"""Earnings report calendar management."""

import pandas as pd
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ReportCalendar:
    """Manages earnings report calendar from CSV file."""

    def __init__(self, csv_path: str = None):
        """
        Initialize report calendar.

        Args:
            csv_path: Path to earnings calendar CSV file
        """
        if csv_path is None:
            from src.utils.config import get_config_value
            csv_path = get_config_value('data.earnings_calendar_path', 'data/earnings_calendar.csv')

        self.csv_path = Path(csv_path)
        logger.info(f"Initialized ReportCalendar with {self.csv_path}")

    def load_calendar(self) -> pd.DataFrame:
        """
        Load earnings calendar from CSV.

        Returns:
            DataFrame with columns: date, ticker, company_name, report_time (optional)
        """
        if not self.csv_path.exists():
            logger.error(f"Earnings calendar file not found: {self.csv_path}")
            raise FileNotFoundError(f"Earnings calendar not found: {self.csv_path}")

        try:
            # Try UTF-8 first, then fall back to latin-1 (for Swedish characters)
            try:
                df = pd.read_csv(self.csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                logger.debug("UTF-8 decoding failed, trying latin-1")
                df = pd.read_csv(self.csv_path, encoding='latin-1')

            # Remove completely empty rows
            df = df.dropna(how='all')

            # Validate required columns (report_time is now optional)
            required_cols = ['date', 'ticker', 'company_name']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")

            # Parse dates (handle various formats)
            df['date'] = pd.to_datetime(df['date'], format='mixed').dt.date

            # Add report_time column if missing (with default value)
            if 'report_time' not in df.columns:
                df['report_time'] = 'Unknown'
                logger.debug("report_time column not present, added with 'Unknown' default")

            logger.info(f"Loaded {len(df)} earnings reports from calendar")
            return df

        except Exception as e:
            logger.error(f"Error loading earnings calendar: {e}")
            raise

    def get_reports_for_date(self, target_date: date = None) -> List[Dict[str, Any]]:
        """
        Get all earnings reports for a specific date.

        Args:
            target_date: Date to filter (defaults to today)

        Returns:
            List of dictionaries with report information
        """
        if target_date is None:
            target_date = date.today()

        df = self.load_calendar()

        # Filter for target date
        reports = df[df['date'] == target_date]

        if reports.empty:
            logger.info(f"No earnings reports found for {target_date}")
            return []

        # Convert to list of dicts
        result = reports.to_dict('records')

        logger.info(f"Found {len(result)} earnings reports for {target_date}")
        return result

    def get_upcoming_reports(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get earnings reports for the next N days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of dictionaries with report information
        """
        df = self.load_calendar()

        today = date.today()
        end_date = today + pd.Timedelta(days=days)

        # Filter for date range
        reports = df[(df['date'] >= today) & (df['date'] <= end_date)]

        if reports.empty:
            logger.info(f"No earnings reports found in next {days} days")
            return []

        # Sort by date
        reports = reports.sort_values('date')
        result = reports.to_dict('records')

        logger.info(f"Found {len(result)} earnings reports in next {days} days")
        return result

    def add_report(
        self,
        report_date: date,
        ticker: str,
        company_name: str,
        report_time: str = 'Unknown'
    ):
        """
        Add a new earnings report to the calendar.

        Args:
            report_date: Date of earnings report
            ticker: Stock ticker symbol (PRIMARY IDENTIFIER)
            company_name: Company name
            report_time: Time of report (optional, e.g., '08:00', '07:30')
        """
        # Load existing calendar
        try:
            df = self.load_calendar()
        except FileNotFoundError:
            # Create new DataFrame if file doesn't exist
            df = pd.DataFrame(columns=['date', 'ticker', 'company_name'])

        # Create new row
        new_row = {
            'date': report_date,
            'ticker': ticker,
            'company_name': company_name
        }

        # Only add report_time if it's not the default
        if report_time and report_time != 'Unknown':
            new_row['report_time'] = report_time

        # Append and save
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        # Remove duplicates (same date and ticker)
        df = df.drop_duplicates(subset=['date', 'ticker'], keep='last')

        # Sort by date
        df = df.sort_values('date')

        # Save to CSV
        self.save_calendar(df)

        logger.info(f"Added earnings report: {ticker} on {report_date}")

    def save_calendar(self, df: pd.DataFrame):
        """
        Save calendar DataFrame to CSV.

        Args:
            df: DataFrame to save
        """
        # Ensure directory exists
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to CSV
        df.to_csv(self.csv_path, index=False)

        logger.info(f"Saved {len(df)} reports to {self.csv_path}")
