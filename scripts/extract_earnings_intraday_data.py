#!/usr/bin/env python3
"""
Extract intraday data for earnings days that pass screening criteria.

This script:
1. Scans tickers for earnings days (using backtest system)
2. Filters for days that pass momentum screening
3. Fetches intraday data for those days
4. Normalizes prices to 9:00 = 100%
5. Saves to database for visualization

Usage:
    python scripts/extract_earnings_intraday_data.py --start 2023-01-01 --end 2024-12-31
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import time

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtesting.historical_data import EarningsDayDetector
from src.backtesting.strategy_simulator import StrategySimulator
from src.data.yfinance_provider import YFinanceProvider
from src.utils.logger import setup_logger
from src.utils.database import get_connection

logger = setup_logger(
    name='earnings_extractor',
    log_file='logs/earnings_extraction.log',
    level='INFO',
    console=True
)


def init_earnings_analysis_table():
    """Create table for storing earnings intraday analysis data."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_intraday_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            earnings_date DATE NOT NULL,
            time_of_day TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            price REAL NOT NULL,
            normalized_price REAL NOT NULL,
            base_price REAL NOT NULL,
            filter_score REAL,
            passed_filter BOOLEAN,
            created_signal BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, earnings_date, time_of_day)
        )
    """)

    # Add created_signal column if it doesn't exist (migration)
    try:
        cursor.execute("SELECT created_signal FROM earnings_intraday_analysis LIMIT 1")
    except Exception:
        logger.info("Adding created_signal column to existing table")
        cursor.execute("ALTER TABLE earnings_intraday_analysis ADD COLUMN created_signal BOOLEAN DEFAULT 0")

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_analysis_date
        ON earnings_intraday_analysis(earnings_date)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_earnings_analysis_time
        ON earnings_intraday_analysis(time_of_day)
    """)

    conn.commit()
    conn.close()
    logger.info("✓ Earnings analysis table initialized")


def save_intraday_data(ticker: str, earnings_date: str, intraday_data: list,
                        filter_score: float, passed_filter: bool, created_signal: bool):
    """Save normalized intraday data to database."""
    if not intraday_data:
        return

    # Find 9:00 price as base
    base_price = None
    for data_point in intraday_data:
        time_str = data_point['time']
        if time_str.startswith('09:00') or time_str.startswith('09:01'):
            base_price = data_point['price']
            break

    if base_price is None or base_price == 0:
        logger.warning(f"{ticker} on {earnings_date}: No valid 9:00 price found")
        return

    conn = get_connection()
    cursor = conn.cursor()

    saved_count = 0
    for data_point in intraday_data:
        time_str = data_point['time']  # Format: HH:MM
        timestamp = f"{earnings_date} {time_str}:00"
        normalized_price = (data_point['price'] / base_price) * 100

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO earnings_intraday_analysis
                (ticker, earnings_date, time_of_day, timestamp, price,
                 normalized_price, base_price, filter_score, passed_filter, created_signal)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker, earnings_date, time_str, timestamp, data_point['price'],
                normalized_price, base_price, filter_score, passed_filter, created_signal
            ))
            saved_count += 1
        except Exception as e:
            logger.error(f"Error saving {ticker} {earnings_date} {time_str}: {e}")

    conn.commit()
    conn.close()

    signal_msg = " (created signal)" if created_signal else ""
    logger.info(f"  ✓ Saved {saved_count} intraday points for {ticker} on {earnings_date}{signal_msg}")


def check_if_signal_created(ticker: str, earnings_date: str) -> bool:
    """
    Check if an actual entry signal/trade was created for this ticker on this date.

    Returns True if a hypothetical trade exists for this ticker and date.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check if any trade exists for this ticker on this date (any strategy)
    cursor.execute("""
        SELECT COUNT(*) FROM hypothetical_trades
        WHERE ticker = ? AND date = ?
    """, (ticker, earnings_date))

    count = cursor.fetchone()[0]
    conn.close()

    return count > 0


def extract_intraday_for_earnings_day(ticker: str, earnings_date: str,
                                        data_provider: YFinanceProvider) -> list:
    """
    Fetch and parse intraday data for a specific earnings day.

    Returns list of dicts: [{'time': 'HH:MM', 'price': float}, ...]
    """
    import yfinance as yf

    try:
        # Parse the earnings date
        date_obj = datetime.strptime(earnings_date, '%Y-%m-%d')

        # Set start and end dates for fetching (start = earnings_date, end = next day)
        start_date = date_obj.strftime('%Y-%m-%d')
        end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')

        # Fetch intraday data for the specific date using yfinance directly
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date, interval='1m')

        if df is None or len(df) == 0:
            logger.warning(f"{ticker} {earnings_date}: No intraday data available")
            return []

        # Filter for market hours (09:00 - 17:30)
        try:
            df = df.between_time('09:00', '17:30')
        except Exception:
            # If between_time fails (empty or no time index), skip
            pass

        if len(df) == 0:
            logger.warning(f"{ticker} {earnings_date}: No data in market hours")
            return []

        # Extract time and price
        intraday_points = []
        for timestamp, row in df.iterrows():
            time_str = timestamp.strftime('%H:%M')
            price = row['Close']

            if price > 0:  # Valid price
                intraday_points.append({
                    'time': time_str,
                    'price': float(price)
                })

        return intraday_points

    except Exception as e:
        logger.error(f"Error fetching intraday for {ticker} {earnings_date}: {e}")
        return []


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Extract intraday data for earnings days',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--start',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end',
        type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='End date (YYYY-MM-DD), defaults to today'
    )

    parser.add_argument(
        '--tickers-file',
        type=str,
        default='data/all_tickers.txt',
        help='Path to file with tickers (default: data/all_tickers.txt)'
    )

    parser.add_argument(
        '--max-tickers',
        type=int,
        help='Limit number of tickers to process (for testing)'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    print("\n" + "=" * 80)
    print("EARNINGS INTRADAY DATA EXTRACTION")
    print("=" * 80)
    print(f"Period: {args.start} to {args.end}")
    print("=" * 80 + "\n")

    # Initialize database table
    init_earnings_analysis_table()

    # Load tickers
    tickers_file = Path(args.tickers_file)
    if not tickers_file.exists():
        print(f"Error: {tickers_file} not found")
        sys.exit(1)

    with open(tickers_file, 'r') as f:
        all_tickers = [line.strip() for line in f if line.strip()]

    if args.max_tickers:
        all_tickers = all_tickers[:args.max_tickers]

    print(f"Loaded {len(all_tickers)} tickers from {tickers_file}\n")

    # Initialize components
    data_provider = YFinanceProvider()
    earnings_detector = EarningsDayDetector(data_provider=data_provider)
    strategy_simulator = StrategySimulator(data_provider=data_provider)

    total_earnings_days = 0
    passed_filter = 0
    saved_days = 0

    # Process each ticker
    for i, ticker in enumerate(all_tickers, 1):
        print(f"[{i}/{len(all_tickers)}] Processing {ticker}...")

        try:
            # Find earnings days
            earnings_days = earnings_detector.scan_period(
                ticker=ticker,
                start_date=args.start,
                end_date=args.end
            )

            if not earnings_days:
                continue

            total_earnings_days += len(earnings_days)
            print(f"  → Found {len(earnings_days)} earnings days")

            # Process each earnings day
            for earnings_day in earnings_days:
                date = earnings_day['date']

                # Check if it passes the filter
                trade = strategy_simulator.simulate_trade(ticker, date)

                # Track stats
                if trade.passed_filter:
                    passed_filter += 1

                # Check if an actual signal was created
                created_signal = check_if_signal_created(ticker, date)

                # Log status
                if trade.passed_filter:
                    signal_marker = " ✓ SIGNAL" if created_signal else ""
                    print(f"  → {date} passed filter (score: {trade.filter_score:.1f}){signal_marker}")
                else:
                    print(f"  → {date} (score: {trade.filter_score:.1f})")

                # Fetch intraday data for this day (ALL earnings days, not just filter-passed)
                intraday_data = extract_intraday_for_earnings_day(
                    ticker, date, data_provider
                )

                if intraday_data:
                    # Save to database
                    save_intraday_data(
                        ticker, date, intraday_data,
                        trade.filter_score, trade.passed_filter, created_signal
                    )
                    saved_days += 1

                # Small delay to avoid rate limiting
                time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            continue

    # Print summary
    print("\n" + "=" * 80)
    print("EXTRACTION SUMMARY")
    print("=" * 80)
    print(f"Total earnings days found: {total_earnings_days}")
    print(f"Passed momentum filter: {passed_filter}")
    print(f"Days with intraday data saved: {saved_days}")
    print("=" * 80 + "\n")

    print("✓ Data extraction complete!")
    print("  Run the web app and navigate to /earnings-analysis to visualize\n")


if __name__ == '__main__':
    main()
