#!/usr/bin/env python3
"""
Run live intraday monitoring.

This script starts the live monitoring process that polls watchlist stocks
every 60 seconds during market hours (09:00-17:30 CET).

Usage:
    python scripts/run_monitor.py [--duration MINUTES]

Examples:
    python scripts/run_monitor.py                # Run until stopped
    python scripts/run_monitor.py --duration 90  # Run for 90 minutes
"""

import sys
import argparse
from pathlib import Path
from datetime import date

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.monitoring.live_monitor import LiveMonitor
from src.utils.logger import get_default_logger
from src.utils.database import init_database, get_watchlist

logger = get_default_logger()


def main():
    """Main entry point for live monitoring."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Run live intraday monitoring')
    parser.add_argument(
        '--duration',
        type=int,
        help='Run for specified minutes (default: run until stopped)'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Date to load watchlist for (YYYY-MM-DD, default: today)'
    )
    args = parser.parse_args()

    # Ensure database exists
    try:
        init_database()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Check if there's a watchlist
    try:
        if args.date:
            target_date = args.date
        else:
            target_date = date.today().strftime('%Y-%m-%d')

        watchlist = get_watchlist(target_date)

        if not watchlist:
            print(f"\n✗ No watchlist found for {target_date}")
            print("\nPlease run the screener first:")
            print(f"  python scripts/run_screener.py --date {target_date}")
            print("\nOr specify a different date:")
            print("  python scripts/run_monitor.py --date YYYY-MM-DD")
            sys.exit(1)

        print("\n" + "=" * 80)
        print("SVEA SURVEILLANCE - LIVE MONITORING")
        print("=" * 80)
        print(f"\n✓ Watchlist for {target_date}: {len(watchlist)} stocks")
        print("\nStocks to monitor:")
        for i, stock in enumerate(watchlist, 1):
            print(f"  {i}. {stock['ticker']:12} - {stock['name']}")

        print(f"\n✓ Market hours: 09:00 - 17:30 CET")
        print(f"✓ Poll interval: 60 seconds")
        print(f"✓ VWAP calculation: Enabled")

        if args.duration:
            print(f"✓ Duration: {args.duration} minutes")
        else:
            print(f"✓ Duration: Until stopped (Ctrl+C)")

        print("\n✓ Starting monitoring...")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error checking watchlist: {e}")
        sys.exit(1)

    # Create and run monitor
    try:
        monitor = LiveMonitor()

        # Load watchlist for the target date
        if args.date:
            from datetime import datetime
            target_date_obj = datetime.strptime(args.date, '%Y-%m-%d').date()
            monitor.load_watchlist(target_date_obj)
        else:
            monitor.load_watchlist()

        # Run monitoring
        monitor.run(duration_minutes=args.duration)

        print("\n" + "=" * 80)
        print("✓ Monitoring stopped")
        print("=" * 80 + "\n")

    except KeyboardInterrupt:
        print("\n\n✓ Monitoring stopped by user")
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Error running monitor: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
