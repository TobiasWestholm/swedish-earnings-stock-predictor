"""Technical indicators for intraday monitoring."""

import pandas as pd
import numpy as np
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def calculate_vwap(prices: pd.Series, volumes: pd.Series) -> float:
    """
    Calculate Volume Weighted Average Price.

    VWAP = Sum(Price * Volume) / Sum(Volume)

    Args:
        prices: Series of prices (typically Close or typical price)
        volumes: Series of volumes

    Returns:
        VWAP value, or None if calculation fails
    """
    try:
        if len(prices) == 0 or len(volumes) == 0:
            return None

        if len(prices) != len(volumes):
            logger.warning(f"Price and volume length mismatch: {len(prices)} vs {len(volumes)}")
            return None

        # Remove any NaN values
        valid_mask = ~(pd.isna(prices) | pd.isna(volumes))
        prices = prices[valid_mask]
        volumes = volumes[valid_mask]

        if len(prices) == 0:
            return None

        # Calculate VWAP
        total_volume = volumes.sum()
        if total_volume == 0:
            logger.warning("Total volume is zero, cannot calculate VWAP")
            return None

        vwap = (prices * volumes).sum() / total_volume

        return float(vwap)

    except Exception as e:
        logger.error(f"Error calculating VWAP: {e}")
        return None


def calculate_cumulative_vwap(df: pd.DataFrame, typical_price: bool = True) -> pd.Series:
    """
    Calculate cumulative VWAP for each timestamp.

    Args:
        df: DataFrame with OHLCV data
        typical_price: If True, use (H+L+C)/3, else use Close

    Returns:
        Series with cumulative VWAP values
    """
    try:
        if df.empty:
            return pd.Series(dtype=float)

        # Calculate typical price if requested
        if typical_price and all(col in df.columns for col in ['High', 'Low', 'Close']):
            price = (df['High'] + df['Low'] + df['Close']) / 3
        else:
            price = df['Close']

        volume = df['Volume']

        # Calculate cumulative VWAP
        cumulative_pv = (price * volume).cumsum()
        cumulative_volume = volume.cumsum()

        # Avoid division by zero
        vwap = cumulative_pv / cumulative_volume.replace(0, np.nan)

        return vwap

    except Exception as e:
        logger.error(f"Error calculating cumulative VWAP: {e}")
        return pd.Series(dtype=float)


def calculate_sma(prices: pd.Series, period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average.

    Args:
        prices: Series of prices
        period: Number of periods for SMA

    Returns:
        SMA value, or None if insufficient data
    """
    try:
        if len(prices) < period:
            return None

        sma = prices.tail(period).mean()
        return float(sma)

    except Exception as e:
        logger.error(f"Error calculating SMA: {e}")
        return None


def calculate_ema(prices: pd.Series, period: int) -> Optional[float]:
    """
    Calculate Exponential Moving Average.

    Args:
        prices: Series of prices
        period: Number of periods for EMA

    Returns:
        EMA value, or None if insufficient data
    """
    try:
        if len(prices) < period:
            return None

        ema = prices.ewm(span=period, adjust=False).mean().iloc[-1]
        return float(ema)

    except Exception as e:
        logger.error(f"Error calculating EMA: {e}")
        return None


def calculate_price_change(current_price: float, reference_price: float) -> dict:
    """
    Calculate price change metrics.

    Args:
        current_price: Current price
        reference_price: Reference price (e.g., open, previous close)

    Returns:
        Dictionary with change amount and percentage
    """
    try:
        change = current_price - reference_price
        change_pct = (change / reference_price) * 100 if reference_price != 0 else 0

        return {
            'change': change,
            'change_pct': change_pct
        }

    except Exception as e:
        logger.error(f"Error calculating price change: {e}")
        return {'change': 0, 'change_pct': 0}


def calculate_intraday_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate comprehensive intraday metrics.

    Args:
        df: DataFrame with OHLCV intraday data

    Returns:
        Dictionary with various metrics
    """
    try:
        if df.empty:
            return {}

        metrics = {
            'open': float(df['Open'].iloc[0]),
            'high': float(df['High'].max()),
            'low': float(df['Low'].min()),
            'close': float(df['Close'].iloc[-1]),
            'volume': int(df['Volume'].sum()),
            'bar_count': len(df)
        }

        # Calculate VWAP
        vwap = calculate_vwap(df['Close'], df['Volume'])
        if vwap is not None:
            metrics['vwap'] = vwap

        # Price changes
        change_info = calculate_price_change(metrics['close'], metrics['open'])
        metrics['change'] = change_info['change']
        metrics['change_pct'] = change_info['change_pct']

        # High/Low of first 15 minutes (if available)
        if len(df) >= 15:
            first_15min = df.head(15)
            metrics['high_15min'] = float(first_15min['High'].max())
            metrics['low_15min'] = float(first_15min['Low'].min())

        # 5-minute average price (for falling knife detection)
        # Use last 5 bars (5 minutes if 1-minute data)
        if len(df) >= 5:
            last_5_bars = df.tail(5)
            avg_price_5min = last_5_bars['Close'].mean()
            metrics['avg_price_5min'] = float(avg_price_5min)
        else:
            # If less than 5 bars, use available data
            metrics['avg_price_5min'] = float(df['Close'].mean())

        return metrics

    except Exception as e:
        logger.error(f"Error calculating intraday metrics: {e}")
        return {}
