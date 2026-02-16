"""Data quality validation for market data."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates market data quality and identifies issues."""

    def __init__(self, staleness_threshold: int = 120):
        """
        Initialize data validator.

        Args:
            staleness_threshold: Seconds threshold for considering data stale
        """
        self.staleness_threshold = staleness_threshold

    def calculate_quality_score(self, df: pd.DataFrame) -> float:
        """
        Calculate overall quality score for data.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Quality score from 0-100 (100 = perfect quality)
        """
        if df is None or df.empty:
            return 0.0

        score = 100.0
        penalties = []

        # Check for missing values
        missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
        if missing_pct > 0:
            penalty = min(missing_pct * 2, 30)  # Max 30 point penalty
            score -= penalty
            penalties.append(f"Missing values: -{penalty:.1f}")

        # Check for suspicious gaps (if daily data)
        if len(df) > 1:
            # Look for price gaps > 20%
            if 'Close' in df.columns:
                price_changes = df['Close'].pct_change().abs()
                large_gaps = (price_changes > 0.20).sum()
                if large_gaps > 0:
                    penalty = min(large_gaps * 10, 20)
                    score -= penalty
                    penalties.append(f"Large price gaps: -{penalty:.1f}")

            # Check for zero volume days (suspicious)
            if 'Volume' in df.columns:
                zero_volume = (df['Volume'] == 0).sum()
                if zero_volume > 0:
                    penalty = min(zero_volume * 5, 15)
                    score -= penalty
                    penalties.append(f"Zero volume days: -{penalty:.1f}")

        # Check for data recency (if index is datetime)
        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 0:
            latest = df.index[-1]
            if latest.tzinfo is None:
                latest = latest.tz_localize('UTC')
            age_seconds = (datetime.now(latest.tzinfo) - latest).total_seconds()

            if age_seconds > self.staleness_threshold:
                penalty = min((age_seconds - self.staleness_threshold) / 60, 20)  # 1 point per minute
                score -= penalty
                penalties.append(f"Stale data ({age_seconds:.0f}s): -{penalty:.1f}")

        score = max(0, min(100, score))

        if penalties:
            logger.debug(f"Quality score: {score:.1f}/100. Penalties: {', '.join(penalties)}")

        return score

    def check_data_completeness(self, df: pd.DataFrame, expected_rows: int = None) -> Dict[str, Any]:
        """
        Check if data is complete (no gaps).

        Args:
            df: DataFrame with OHLCV data
            expected_rows: Expected number of rows (optional)

        Returns:
            Dictionary with completeness metrics
        """
        if df is None or df.empty:
            return {
                'is_complete': False,
                'missing_rows': expected_rows if expected_rows else 0,
                'issues': ['Data is empty']
            }

        issues = []
        missing_rows = 0

        # Check expected row count
        if expected_rows:
            if len(df) < expected_rows:
                missing_rows = expected_rows - len(df)
                issues.append(f"Missing {missing_rows} rows (expected {expected_rows}, got {len(df)})")

        # Check for NaN values
        null_counts = df.isnull().sum()
        for col, count in null_counts.items():
            if count > 0:
                issues.append(f"{col}: {count} missing values")

        is_complete = len(issues) == 0

        return {
            'is_complete': is_complete,
            'missing_rows': missing_rows,
            'total_rows': len(df),
            'issues': issues
        }

    def detect_data_gaps(self, df: pd.DataFrame, interval: str = "1d") -> List[str]:
        """
        Detect time gaps in the data.

        Args:
            df: DataFrame with datetime index
            interval: Expected data interval ('1d', '1h', '1m')

        Returns:
            List of detected gaps (as strings)
        """
        if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
            return []

        gaps = []

        # Expected timedelta based on interval
        interval_map = {
            '1m': timedelta(minutes=1),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '1h': timedelta(hours=1),
            '1d': timedelta(days=1)
        }

        expected_delta = interval_map.get(interval)
        if not expected_delta:
            return gaps

        # Check for gaps
        for i in range(1, len(df)):
            time_diff = df.index[i] - df.index[i-1]

            # Allow some tolerance (2x expected interval)
            if time_diff > expected_delta * 2:
                gap_msg = f"Gap from {df.index[i-1]} to {df.index[i]} ({time_diff})"
                gaps.append(gap_msg)

        if gaps:
            logger.warning(f"Detected {len(gaps)} time gaps in data")

        return gaps

    def validate_ohlcv(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate OHLCV data integrity.

        Args:
            df: DataFrame with OHLCV columns

        Returns:
            Dictionary with validation results
        """
        issues = []

        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            issues.append(f"Missing columns: {missing_columns}")
            return {'is_valid': False, 'issues': issues}

        # Check OHLC relationships
        invalid_high = (df['High'] < df['Low']).sum()
        if invalid_high > 0:
            issues.append(f"{invalid_high} rows where High < Low")

        invalid_high_close = (df['High'] < df['Close']).sum()
        if invalid_high_close > 0:
            issues.append(f"{invalid_high_close} rows where High < Close")

        invalid_low_close = (df['Low'] > df['Close']).sum()
        if invalid_low_close > 0:
            issues.append(f"{invalid_low_close} rows where Low > Close")

        # Check for negative prices
        negative_prices = (
            (df['Open'] < 0) | (df['High'] < 0) |
            (df['Low'] < 0) | (df['Close'] < 0)
        ).sum()
        if negative_prices > 0:
            issues.append(f"{negative_prices} rows with negative prices")

        # Check for negative volume
        negative_volume = (df['Volume'] < 0).sum()
        if negative_volume > 0:
            issues.append(f"{negative_volume} rows with negative volume")

        is_valid = len(issues) == 0

        return {
            'is_valid': is_valid,
            'issues': issues
        }
