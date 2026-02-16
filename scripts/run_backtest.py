#!/usr/bin/env python3
"""
Backtest script for strategy validation.

Usage:
    # Test single ticker
    python scripts/run_backtest.py --ticker VOLV-B.ST --start 2023-01-01 --end 2024-12-31

    # Test multiple tickers
    python scripts/run_backtest.py --tickers VOLV-B.ST ERIC-B.ST HM-B.ST --start 2023-01-01 --end 2024-12-31

    # Test all tickers from watchlist
    python scripts/run_backtest.py --from-watchlist --start 2023-01-01 --end 2024-12-31

    # Quick test (last 6 months)
    python scripts/run_backtest.py --ticker VOLV-B.ST --quick
"""

import sys
import os
import argparse
import logging
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtesting.backtest_engine import BacktestEngine
from src.utils.database import get_watchlist
from src.utils.logger import setup_logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Run strategy backtest on historical data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Ticker selection
    ticker_group = parser.add_mutually_exclusive_group(required=True)
    ticker_group.add_argument(
        '--ticker',
        type=str,
        help='Single ticker to backtest (e.g., VOLV-B.ST)'
    )
    ticker_group.add_argument(
        '--tickers',
        nargs='+',
        help='Multiple tickers to backtest (e.g., VOLV-B.ST ERIC-B.ST)'
    )
    ticker_group.add_argument(
        '--from-watchlist',
        action='store_true',
        help='Use tickers from today\'s watchlist'
    )

    # Date range
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    date_group.add_argument(
        '--quick',
        action='store_true',
        help='Quick test: last 6 months'
    )

    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD), defaults to today'
    )

    # Output options
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )

    return parser.parse_args()


def get_tickers(args) -> list:
    """Get list of tickers based on arguments."""
    if args.ticker:
        return [args.ticker]
    elif args.tickers:
        return args.tickers
    elif args.from_watchlist:
        # Get tickers from today's watchlist
        today = datetime.now().strftime('%Y-%m-%d')
        watchlist = get_watchlist(date=today)
        if not watchlist:
            print(f"⚠️  No watchlist found for {today}")
            print("   Run the screener first: python scripts/run_screener.py")
            sys.exit(1)
        return [stock['ticker'] for stock in watchlist]
    else:
        raise ValueError("No tickers specified")


def get_date_range(args) -> tuple:
    """Get start and end dates based on arguments."""
    if args.quick:
        # Last 6 months
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
    else:
        if not args.start:
            print("Error: --start date is required (or use --quick)")
            sys.exit(1)

        end_date = args.end if args.end else datetime.now().strftime('%Y-%m-%d')
        return args.start, end_date


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    setup_logger(level=args.log_level)

    # Get tickers
    tickers = get_tickers(args)

    # Get date range
    start_date, end_date = get_date_range(args)

    # Print configuration
    if not args.quiet:
        print("\n" + "=" * 80)
        print("BACKTEST CONFIGURATION")
        print("=" * 80)
        print(f"Tickers: {', '.join(tickers)} ({len(tickers)} total)")
        print(f"Period: {start_date} to {end_date}")
        print("=" * 80 + "\n")

    # Run backtest
    engine = BacktestEngine()

    try:
        metrics = engine.run_backtest(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            verbose=not args.quiet
        )

        # Success
        if not args.quiet:
            print("\n✓ Backtest completed successfully\n")

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Backtest interrupted by user\n")
        return 1
    except Exception as e:
        print(f"\n✗ Error running backtest: {e}\n")
        logging.exception("Backtest failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
