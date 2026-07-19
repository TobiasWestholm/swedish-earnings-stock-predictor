#!/usr/bin/env python3
"""
Unified wrapper script to fetch all fundamental metrics for earnings dates.

This script coordinates fetching of all 5 fundamental metric types:
  1. 52-week position
  2. Valuation metrics
  3. Market cap & liquidity
  4. Momentum
  5. Volatility

Called automatically by the scheduler at EOD, or manually for specific dates.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.utils.database import get_connection
import subprocess
import argparse
from datetime import date, datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_earnings_for_date(target_date):
    """Get all (ticker, earnings_date) pairs for a specific date."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ticker, earnings_date
        FROM earnings_intraday_analysis
        WHERE earnings_date = ?
        ORDER BY ticker
    """, (target_date,))

    results = cursor.fetchall()
    conn.close()

    return results


def run_fetch_script(script_name, date_arg, tickers_arg=None, timeout=600):
    """
    Run a single fetch script with the given date and optional tickers arguments.

    Args:
        script_name: Name of the script to run
        date_arg: Date string (YYYY-MM-DD)
        tickers_arg: Optional comma-separated ticker string
        timeout: Timeout in seconds

    Returns:
        (success: bool, stdout: str, stderr: str)
    """
    script_path = os.path.join(os.path.dirname(__file__), script_name)

    # Build command arguments
    cmd = [sys.executable, script_path, '--date', date_arg]
    if tickers_arg:
        cmd.extend(['--tickers', tickers_arg])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        success = result.returncode == 0
        return success, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        error_msg = f"Script {script_name} timed out after {timeout} seconds"
        logger.error(error_msg)
        return False, "", error_msg
    except Exception as e:
        error_msg = f"Error running {script_name}: {str(e)}"
        logger.error(error_msg)
        return False, "", error_msg


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description='Fetch all fundamental metrics for earnings on a specific date'
    )
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Target date (YYYY-MM-DD). Defaults to today.'
    )
    parser.add_argument(
        '--tickers',
        type=str,
        default=None,
        help='Comma-separated list of specific tickers to fetch (optional)'
    )

    args = parser.parse_args()

    # Parse target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Invalid date format: {args.date}. Expected YYYY-MM-DD")
            return 1
    else:
        target_date = date.today()

    date_str = target_date.strftime('%Y-%m-%d')

    print("=" * 80)
    print("UNIFIED FUNDAMENTAL DATA FETCH")
    print("=" * 80)
    print()
    print(f"Target date: {date_str}")

    # Get earnings for this date
    earnings_data = get_earnings_for_date(date_str)

    if not earnings_data:
        print(f"No earnings found for {date_str}")
        print("Nothing to fetch.")
        print("=" * 80)
        return 0

    # Filter by tickers if specified
    if args.tickers:
        ticker_list = [t.strip().upper() for t in args.tickers.split(',')]
        earnings_data = [(ticker, ed) for ticker, ed in earnings_data if ticker in ticker_list]
        print(f"Filtered to tickers: {', '.join(ticker_list)}")

    tickers = [t for t, _ in earnings_data]
    print(f"Found {len(tickers)} stocks with earnings: {', '.join(tickers)}")
    print()

    # Define the 5 fetch scripts to run
    fetch_scripts = [
        ('fetch_52week_position.py', '52-Week Position'),
        ('fetch_valuation_metrics.py', 'Valuation Metrics'),
        ('fetch_market_cap_liquidity.py', 'Market Cap & Liquidity'),
        ('fetch_earnings_volatility.py', 'Volatility')
    ]

    results = {}
    overall_success = True

    # Run each fetch script sequentially
    for idx, (script_name, display_name) in enumerate(fetch_scripts, 1):
        print(f"[{idx}/{len(fetch_scripts)}] Running {display_name}...")
        print("-" * 80)

        # Pass tickers argument if specified
        success, stdout, stderr = run_fetch_script(
            script_name,
            date_str,
            tickers_arg=args.tickers,
            timeout=600
        )

        results[display_name] = {
            'success': success,
            'stdout': stdout,
            'stderr': stderr
        }

        # Print script output
        if stdout:
            print(stdout)

        if not success:
            overall_success = False
            print(f"ERROR in {display_name}:")
            if stderr:
                print(stderr)
            print()

        print()

    # Summary
    print("=" * 80)
    print("FETCH SUMMARY")
    print("=" * 80)
    print(f"Target date: {date_str}")
    print(f"Stocks processed: {len(tickers)}")
    print()

    success_count = sum(1 for r in results.values() if r['success'])
    failure_count = len(results) - success_count

    print("Script Results:")
    for display_name, result in results.items():
        status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
        print(f"  {status:12s} - {display_name}")

    print()
    print(f"Overall: {success_count}/{len(fetch_scripts)} scripts succeeded")

    if overall_success:
        print("All fundamental data fetched successfully!")
    else:
        print(f"WARNING: {failure_count} script(s) failed. Check logs above.")

    print("=" * 80)

    return 0 if overall_success else 1


if __name__ == '__main__':
    sys.exit(main())
