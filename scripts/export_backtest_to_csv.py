#!/usr/bin/env python3
"""
Export backtest results to CSV for macro analysis.

This script runs a backtest and exports detailed trade data to CSV format
for further analysis in Excel, Pandas, or other tools.

Usage:
    # Export all tickers from watchlist for 2023-2024
    python scripts/export_backtest_to_csv.py --from-watchlist --start 2023-01-01 --end 2024-12-31

    # Export specific tickers
    python scripts/export_backtest_to_csv.py --tickers VOLV-B.ST ERIC-B.ST --start 2023-01-01 --end 2024-12-31

    # Export with custom output file
    python scripts/export_backtest_to_csv.py --ticker VOLV-B.ST --start 2023-01-01 --end 2024-12-31 --output my_results.csv
"""

import sys
import os
import argparse
import csv
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backtesting.backtest_engine import BacktestEngine
from src.utils.database import get_watchlist
from src.utils.logger import setup_logger


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Export backtest results to CSV for analysis',
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
        help='Multiple tickers to backtest'
    )
    ticker_group.add_argument(
        '--from-watchlist',
        action='store_true',
        help='Use all tickers from data/all_tickers.txt'
    )

    # Date range
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

    # Output options
    parser.add_argument(
        '--output',
        type=str,
        default='backtest_results.csv',
        help='Output CSV filename (default: backtest_results.csv)'
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
        # Read from all_tickers.txt
        tickers_file = Path(__file__).parent.parent / 'data' / 'all_tickers.txt'
        if tickers_file.exists():
            with open(tickers_file, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        else:
            print(f"Error: {tickers_file} not found")
            sys.exit(1)
    return []


def export_trades_to_csv(trades: list, output_file: str):
    """
    Export trade data to CSV file.

    Args:
        trades: List of Trade objects
        output_file: Output CSV filename
    """
    if not trades:
        print("No trades to export")
        return

    # Define CSV columns
    fieldnames = [
        'ticker',
        'date',
        'passed_filter',
        'filter_score',
        'signal_detected',
        'entry_price',
        'entry_time',
        'exit_price',
        'exit_time',
        'exit_reason',
        'pnl',
        'pnl_pct',
        'open_price',
        'vwap',
        'yesterday_close',
        'data_quality',
        'notes'
    ]

    # Write to CSV
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
            trade_dict = trade.to_dict()

            # Extract only the fields we want
            row = {field: trade_dict.get(field) for field in fieldnames}

            writer.writerow(row)

    print(f"\n✓ Exported {len(trades)} trades to {output_file}")


def main():
    """Main entry point."""
    args = parse_args()

    # Setup logging
    logger = setup_logger(
        name='backtest_export',
        log_file='logs/backtest_export.log',
        level=args.log_level,
        console=True
    )

    print("\n" + "=" * 80)
    print("BACKTEST DATA EXPORT TO CSV")
    print("=" * 80)

    # Get tickers
    tickers = get_tickers(args)
    print(f"Tickers: {', '.join(tickers[:10])}{' ...' if len(tickers) > 10 else ''} ({len(tickers)} total)")
    print(f"Period: {args.start} to {args.end}")
    print(f"Output: {args.output}")
    print("=" * 80 + "\n")

    # Initialize backtest engine
    engine = BacktestEngine()

    # Run backtest
    results = engine.run_backtest(
        tickers=tickers,
        start_date=args.start,
        end_date=args.end,
        verbose=True
    )

    # Export to CSV
    trades = results.get('trades', [])
    export_trades_to_csv(trades, args.output)

    # Print summary
    print("\n" + "=" * 80)
    print("EXPORT SUMMARY")
    print("=" * 80)
    print(f"Total trades exported: {len(trades)}")
    print(f"Trades with signals: {len([t for t in trades if t.signal_detected])}")
    print(f"Winning trades: {len([t for t in trades if t.pnl and t.pnl > 0])}")
    print(f"Losing trades: {len([t for t in trades if t.pnl and t.pnl < 0])}")
    print(f"\nData saved to: {args.output}")
    print("=" * 80 + "\n")

    # Print usage examples
    print("NEXT STEPS:")
    print(f"  1. Open {args.output} in Excel or your favorite spreadsheet tool")
    print("  2. Use Python/Pandas for analysis:")
    print(f"     import pandas as pd")
    print(f"     df = pd.read_csv('{args.output}')")
    print(f"     df.describe()")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    main()
