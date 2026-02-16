#!/usr/bin/env python3
"""
Run the daily stock screener.

This script:
1. Loads today's earnings calendar
2. Applies momentum filter (3M + 1Y + SMA200)
3. Saves results to database
4. Displays watchlist in terminal

Usage:
    python scripts/run_screener.py [--date YYYY-MM-DD]

Examples:
    python scripts/run_screener.py                    # Screen for today
    python scripts/run_screener.py --date 2026-02-13  # Screen for specific date
"""

import sys
import argparse
from datetime import date, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.screening.screener import Screener
from src.utils.logger import get_default_logger
from src.utils.database import init_database


def main():
    """Main entry point for screener script."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Run stock screener')
    parser.add_argument(
        '--date',
        type=str,
        help='Target date (YYYY-MM-DD). Defaults to today.'
    )
    args = parser.parse_args()

    # Setup logger
    logger = get_default_logger()

    # Ensure database exists
    try:
        init_database()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Parse target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = date.today()

    logger.info(f"Starting screener for {target_date}")

    # Run screener
    try:
        screener = Screener()
        watchlist = screener.run_and_save(target_date)

        # Display results
        print("\n" + "=" * 95)
        print(f"SVEA SURVEILLANCE - STOCK SCREENER")
        print(f"Date: {target_date}")
        print("=" * 95)

        if watchlist:
            print(f"\n✓ Found {len(watchlist)} stocks passing momentum filter:\n")

            # Print table header
            print(f"{'Rank':<6} {'Ticker':<12} {'Company':<20} {'Score':<8} {'Current':<10} {'Yest.':<10} {'3M':<10} {'1Y':<10}")
            print("-" * 95)

            # Print each stock
            for i, stock in enumerate(watchlist, 1):
                ticker = stock['ticker']
                name = stock['name'][:18] + '..' if len(stock['name']) > 20 else stock['name']
                score = f"{stock['trend_score']:.0f}"
                current = f"{stock['current_price']:.2f}" if stock.get('current_price') else 'N/A'
                yesterday = f"{stock['yesterday_close']:.2f}" if stock.get('yesterday_close') else 'N/A'
                ret_3m = f"{stock['return_3m']*100:+.1f}%" if stock['return_3m'] else 'N/A'
                ret_1y = f"{stock['return_1y']*100:+.1f}%" if stock['return_1y'] else 'N/A'

                print(f"{i:<6} {ticker:<12} {name:<20} {score:<8} {current:<10} {yesterday:<10} {ret_3m:<10} {ret_1y:<10}")

            # Print summary
            summary = screener.get_summary(watchlist)
            print("\n" + "-" * 95)
            print(f"Summary:")
            print(f"  - Average Score: {summary['avg_score']:.1f}")
            print(f"  - Average 3M Return: {summary['avg_return_3m']*100:+.1f}%")
            print(f"  - Average 1Y Return: {summary['avg_return_1y']*100:+.1f}%")
            print(f"  - Score Range: {summary['score_range']}")

            print("\n" + "=" * 95)
            print("✓ Results saved to database")
            print(f"✓ View in web UI: http://localhost:5000/watchlist")
            print("=" * 95 + "\n")

        else:
            print(f"\n✗ No stocks found for {target_date}")
            print("\nPossible reasons:")
            print("  1. No earnings reports in data/earnings_calendar.csv for this date")
            print("  2. All stocks failed momentum filter (3M + 1Y + SMA200)")
            print("\nNext steps:")
            print("  - Check data/earnings_calendar.csv has entries for today")
            print("  - Verify ticker symbols are correct (e.g., VOLV-B.ST for Swedish stocks)")
            print("=" * 95 + "\n")

        logger.info("Screener completed successfully")

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"\n✗ Error: {e}")
        print("\nMake sure data/earnings_calendar.csv exists and has entries.")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Error running screener: {e}", exc_info=True)
        print(f"\n✗ Error running screener: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
