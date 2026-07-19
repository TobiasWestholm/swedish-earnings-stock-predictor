#!/usr/bin/env python3
"""
Fetch historical earnings dates and returns for all tickers.

For each ticker, fetches:
  - All historical earnings announcement dates from yfinance
  - Actual price returns on each earnings day
  - Stores in earnings_day_returns table

This populates the historical patterns database with real historical data
instead of waiting for it to accumulate over time.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import yfinance as yf
from datetime import datetime, timedelta
import time
import pandas as pd


def get_all_tickers():
    """Get all unique tickers from the dataset."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker
        FROM earnings_intraday_analysis
        ORDER BY ticker
    """)

    results = [row[0] for row in cursor.fetchall()]
    conn.close()

    return results


def fetch_historical_earnings_dates(ticker):
    """
    Fetch all historical earnings dates for a ticker from yfinance.

    Returns list of earnings dates (as datetime objects).
    """
    try:
        stock = yf.Ticker(ticker)

        # Get earnings dates (historical)
        # This returns a DataFrame with dates as index
        earnings_dates = stock.earnings_dates

        if earnings_dates is None or earnings_dates.empty:
            return []

        # Extract dates from index
        dates = []
        for date in earnings_dates.index:
            # Convert to datetime.date
            date_obj = pd.to_datetime(date).date()
            dates.append(date_obj)

        # Sort by date (oldest first)
        dates.sort()

        return dates

    except Exception as e:
        print(f"Error fetching earnings dates for {ticker}: {e}")
        return []


def fetch_earnings_day_return(ticker, earnings_date):
    """
    Fetch earnings day return for a specific date.

    Returns the actual price movement on earnings day.
    (Same logic as fetch_earnings_day_returns.py)
    """
    try:
        stock = yf.Ticker(ticker)

        # Convert to datetime if it's a date object
        if isinstance(earnings_date, datetime):
            earnings_dt = earnings_date
        else:
            earnings_dt = datetime.combine(earnings_date, datetime.min.time())

        # Fetch 5 days around earnings to get prev close and earnings day data
        start_date = earnings_dt - timedelta(days=5)
        end_date = earnings_dt + timedelta(days=2)

        hist = stock.history(start=start_date, end=end_date, interval='1d')

        if hist.empty:
            return None

        # Find the earnings day
        earnings_day_data = None
        prev_close = None

        for i, (date, row) in enumerate(hist.iterrows()):
            date_only = date.date()
            if date_only == earnings_dt.date():
                earnings_day_data = row
                # Get previous trading day close
                if i > 0:
                    prev_close = hist.iloc[i-1]['Close']
                break

        if earnings_day_data is None or prev_close is None:
            return None

        # Calculate returns
        earnings_close = float(earnings_day_data['Close'])
        earnings_high = float(earnings_day_data['High'])
        earnings_low = float(earnings_day_data['Low'])
        prev_close = float(prev_close)

        earnings_day_return = ((earnings_close - prev_close) / prev_close) * 100
        earnings_day_high_pct = ((earnings_high - prev_close) / prev_close) * 100
        earnings_day_low_pct = ((earnings_low - prev_close) / prev_close) * 100

        return {
            'prev_close': prev_close,
            'earnings_close': earnings_close,
            'earnings_high': earnings_high,
            'earnings_low': earnings_low,
            'earnings_day_return': earnings_day_return,
            'earnings_day_high_pct': earnings_day_high_pct,
            'earnings_day_low_pct': earnings_day_low_pct,
            'data_quality': 'found',
            'fetch_error': None
        }

    except Exception as e:
        return None


def store_earnings_day_return(ticker, earnings_date, data):
    """Store earnings day return in database."""
    conn = get_connection()
    cursor = conn.cursor()

    # Convert date to string
    if isinstance(earnings_date, datetime):
        date_str = earnings_date.strftime('%Y-%m-%d')
    else:
        date_str = str(earnings_date)

    cursor.execute("""
        INSERT OR REPLACE INTO earnings_day_returns
        (ticker, earnings_date, prev_close, earnings_close,
         earnings_high, earnings_low, earnings_day_return,
         earnings_day_high_pct, earnings_day_low_pct,
         data_quality, fetch_error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker,
        date_str,
        data['prev_close'],
        data['earnings_close'],
        data['earnings_high'],
        data['earnings_low'],
        data['earnings_day_return'],
        data['earnings_day_high_pct'],
        data['earnings_day_low_pct'],
        data['data_quality'],
        data['fetch_error']
    ))

    conn.commit()
    conn.close()


def main():
    """Main execution."""
    print("="*80)
    print("FETCHING HISTORICAL EARNINGS DATES & RETURNS")
    print("="*80)
    print()
    print("This will fetch all historical earnings dates for each ticker")
    print("and calculate actual returns on those earnings days.")
    print()

    # Get all tickers
    tickers = get_all_tickers()
    total_tickers = len(tickers)

    print(f"Found {total_tickers} unique tickers")
    print()

    # Process each ticker
    total_earnings = 0
    total_returns_fetched = 0
    tickers_with_history = 0
    tickers_no_history = 0

    for idx, ticker in enumerate(tickers, 1):
        print(f"[{idx}/{total_tickers}] {ticker}...", end=" ")

        # Fetch historical earnings dates
        earnings_dates = fetch_historical_earnings_dates(ticker)

        if not earnings_dates:
            print(f"No historical earnings dates found")
            tickers_no_history += 1
            time.sleep(0.2)
            continue

        print(f"Found {len(earnings_dates)} historical earnings dates", end="")
        total_earnings += len(earnings_dates)
        tickers_with_history += 1

        # Fetch returns for each earnings date
        returns_fetched = 0
        for earnings_date in earnings_dates:
            data = fetch_earnings_day_return(ticker, earnings_date)

            if data is not None:
                store_earnings_day_return(ticker, earnings_date, data)
                returns_fetched += 1

            time.sleep(0.1)  # Small delay between dates for same ticker

        print(f" -> Got {returns_fetched} returns")
        total_returns_fetched += returns_fetched

        # Rate limiting between tickers
        if idx % 10 == 0:
            time.sleep(1)
        else:
            time.sleep(0.3)

    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total tickers processed: {total_tickers}")
    print(f"  ✓ With historical earnings: {tickers_with_history} ({tickers_with_history/total_tickers*100:.1f}%)")
    print(f"  ⚠ No historical data:       {tickers_no_history} ({tickers_no_history/total_tickers*100:.1f}%)")
    print()
    print(f"Total historical earnings dates found: {total_earnings}")
    print(f"Total returns successfully fetched: {total_returns_fetched}")
    if total_earnings > 0:
        print(f"Success rate: {total_returns_fetched/total_earnings*100:.1f}%")
    print()

    if tickers_with_history > 0:
        avg_earnings_per_ticker = total_earnings / tickers_with_history
        print(f"Average earnings per ticker (with history): {avg_earnings_per_ticker:.1f}")

    print()
    print("Data stored in earnings_day_returns table")
    print("Run calculate_historical_earnings_patterns.py to update patterns")
    print("="*80)


if __name__ == '__main__':
    main()
