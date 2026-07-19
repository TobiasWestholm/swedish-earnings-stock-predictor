#!/usr/bin/env python3
"""
Extract intraday data for ALL stocks from the earnings calendar CSV.
This ensures we capture the complete earnings dataset, not just what's in the database.

The CSV is the source of truth for earnings dates.
"""

import sys
import os
from datetime import datetime, timedelta
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.database import get_connection
from src.utils.logger import setup_logger
import yfinance as yf
import time

logger = setup_logger('calendar_extractor', 'logs/calendar_extraction.log', 'INFO', console=True)

def parse_date(date_str):
    """Parse date from CSV format '2/12/26' to datetime."""
    try:
        # Handle format like "2/12/26" (M/D/YY)
        return datetime.strptime(date_str, '%m/%d/%y').date()
    except:
        try:
            # Try alternate format
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return None

def extract_intraday(ticker, date_str):
    """Extract intraday data for a specific date."""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        start_date = date_obj.strftime('%Y-%m-%d')
        end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date, interval='1m')

        if df is None or len(df) == 0:
            return []

        try:
            df = df.between_time('09:00', '17:30')
        except:
            pass

        if len(df) == 0:
            return []

        # Find base price - prefer 9:00, but accept first available if not found
        base_price = None
        base_time = None

        # First try to find 09:00 or 09:01 (preferred)
        for timestamp, row in df.iterrows():
            time_str = timestamp.strftime('%H:%M')
            if time_str.startswith('09:00') or time_str.startswith('09:01'):
                base_price = row['Close']
                base_time = time_str
                break

        # If not found, use the first available datapoint
        if base_price is None:
            first_row = df.iloc[0]
            base_price = first_row['Close']
            base_time = df.index[0].strftime('%H:%M')
            logger.info(f"{ticker} {date_str}: Using {base_time} as base (09:00 not available)")

        if base_price is None or base_price == 0:
            return []

        # Extract normalized data
        intraday_points = []
        for timestamp, row in df.iterrows():
            time_str = timestamp.strftime('%H:%M')
            price = row['Close']
            if price > 0:
                normalized_price = (price / base_price) * 100
                intraday_points.append({
                    'time': time_str,
                    'price': float(price),
                    'normalized_price': float(normalized_price),
                    'base_price': float(base_price)
                })

        return intraday_points

    except Exception as e:
        logger.error(f"Error extracting {ticker} {date_str}: {e}")
        return []

def save_intraday_data(ticker, date, intraday_data, passed_filter, created_signal, filter_score=100.0):
    """Save intraday data to database."""
    if not intraday_data:
        return 0

    conn = get_connection()
    cursor = conn.cursor()

    saved_count = 0
    for point in intraday_data:
        try:
            timestamp = f"{date} {point['time']}:00"
            cursor.execute("""
                INSERT OR REPLACE INTO earnings_intraday_analysis
                (ticker, earnings_date, time_of_day, timestamp, price,
                 normalized_price, base_price, filter_score, passed_filter, created_signal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, date, point['time'], timestamp, point['price'],
                point['normalized_price'], point['base_price'],
                filter_score, passed_filter, created_signal
            ))
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving {ticker} {date} {point['time']}: {e}")

    conn.commit()
    conn.close()

    return saved_count

def main():
    print("=" * 80)
    print("EXTRACTING FROM EARNINGS CALENDAR CSV")
    print("=" * 80)

    # Load the earnings calendar CSV
    csv_path = 'data/earnings_calendar.csv'
    logger.info(f"Loading earnings calendar from {csv_path}")

    # Try different encodings to handle Swedish characters
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(csv_path, encoding='latin-1')
        except:
            df = pd.read_csv(csv_path, encoding='cp1252')
    logger.info(f"Loaded {len(df)} total entries from CSV")

    # Parse dates and filter for last 30 days
    today = datetime.now().date()
    thirty_days_ago = today - timedelta(days=30)

    valid_entries = []
    for _, row in df.iterrows():
        if pd.isna(row['date']) or pd.isna(row['ticker']):
            continue

        date_obj = parse_date(str(row['date']))
        if date_obj and thirty_days_ago <= date_obj <= today:
            valid_entries.append({
                'ticker': row['ticker'],
                'date': date_obj.strftime('%Y-%m-%d'),
                'company_name': row.get('company_name', '')
            })

    logger.info(f"Found {len(valid_entries)} earnings in last 30 days (from {thirty_days_ago} to {today})")

    # Get database connection to check which tickers are in watchlist/signals/trades
    conn = get_connection()
    cursor = conn.cursor()

    # Build lookup sets for filter-passed and signal-created
    cursor.execute("SELECT DISTINCT ticker, date FROM watchlist")
    watchlist_set = set((row[0], row[1]) for row in cursor.fetchall())

    cursor.execute("SELECT DISTINCT ticker, DATE(signal_time) FROM signals")
    signals_set = set((row[0], row[1]) for row in cursor.fetchall())

    cursor.execute("SELECT DISTINCT ticker, date FROM hypothetical_trades")
    trades_set = set((row[0], row[1]) for row in cursor.fetchall())

    conn.close()

    # Combine all filter-passed sources
    filter_passed_set = watchlist_set | signals_set | trades_set

    logger.info(f"Found {len(filter_passed_set)} (ticker, date) pairs that passed filter")
    logger.info(f"Found {len(trades_set)} (ticker, date) pairs that created signals")

    print(f"\nProcessing {len(valid_entries)} earnings entries from CSV...\n")

    total_extracted = 0
    total_saved = 0
    filter_passed_count = 0
    signal_count = 0

    for i, entry in enumerate(valid_entries, 1):
        ticker = entry['ticker']
        date = entry['date']

        print(f"[{i}/{len(valid_entries)}] {ticker} on {date}...", end=" ")

        # Check if this ticker-date passed filter or created signal
        ticker_date = (ticker, date)
        passed_filter = ticker_date in filter_passed_set
        created_signal = ticker_date in trades_set

        if passed_filter:
            filter_passed_count += 1
        if created_signal:
            signal_count += 1

        # Extract intraday data
        intraday_data = extract_intraday(ticker, date)

        if intraday_data:
            saved = save_intraday_data(
                ticker, date, intraday_data,
                passed_filter=passed_filter,
                created_signal=created_signal,
                filter_score=100.0 if passed_filter else 0.0
            )

            status_marks = []
            if passed_filter:
                status_marks.append("FILTER")
            if created_signal:
                status_marks.append("SIGNAL")
            status_str = f" [{', '.join(status_marks)}]" if status_marks else ""

            print(f"✓ {saved} points{status_str}")
            total_extracted += 1
            total_saved += saved
        else:
            print("No data")

        # Rate limiting - yfinance has restrictions
        time.sleep(0.5)

    print("\n" + "=" * 80)
    print(f"COMPLETE: Extracted {total_extracted} stocks, saved {total_saved} data points")
    print(f"  - Total earnings in CSV (last 30d): {len(valid_entries)}")
    print(f"  - Passed filter: {filter_passed_count}")
    print(f"  - Created signals: {signal_count}")
    print("=" * 80)

if __name__ == '__main__':
    main()
