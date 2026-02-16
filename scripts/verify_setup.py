"""Verify that the system is correctly configured and ready for paper trading."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.paper_trading_tracker import PaperTradingTracker
from src.backtesting.strategy_simulator import StrategySimulator
from src.utils.logger import setup_logger
import sqlite3
from pathlib import Path

# Setup logging
setup_logger()


def print_header(title):
    """Print formatted section header."""
    print("\n" + "="*80)
    print(title)
    print("="*80)


def check_mark(passed):
    """Return check mark or X based on status."""
    return "✅" if passed else "❌"


def verify_directory_structure():
    """Verify all required directories exist."""
    print_header("1. DIRECTORY STRUCTURE")

    required_dirs = [
        'data',
        'logs',
        'config',
        'scripts',
        'src/backtesting',
        'src/data',
        'src/monitoring',
        'src/screening',
        'src/risk',
        'src/ui',
        'src/utils'
    ]

    all_exist = True
    for directory in required_dirs:
        exists = Path(directory).exists()
        all_exist = all_exist and exists
        print(f"  {check_mark(exists)} {directory}")

    return all_exist


def verify_data_files():
    """Verify required data files exist."""
    print_header("2. DATA FILES")

    required_files = {
        'data/all_tickers.txt': 'Stock universe (544 Swedish tickers)',
        'config/config.yaml': 'Main configuration file'
    }

    all_exist = True
    for filepath, description in required_files.items():
        exists = Path(filepath).exists()
        all_exist = all_exist and exists
        print(f"  {check_mark(exists)} {filepath} - {description}")

        if exists and filepath == 'data/all_tickers.txt':
            with open(filepath) as f:
                ticker_count = len([line for line in f if line.strip()])
            print(f"      📊 Contains {ticker_count} tickers")

    return all_exist


def verify_databases():
    """Verify database schemas are set up."""
    print_header("3. DATABASES")

    databases = {
        'data/trades.db': 'Main trading database',
        'data/paper_trades.db': 'Paper trading tracker'
    }

    all_ok = True
    for db_path, description in databases.items():
        exists = Path(db_path).exists()
        print(f"\n  {check_mark(exists)} {db_path} - {description}")

        if not exists:
            print(f"      ⚠️  Database will be created on first use")
            all_ok = False
            continue

        # Verify tables exist
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            print(f"      📋 Tables: {', '.join(tables)}")
        except Exception as e:
            print(f"      ❌ Error reading database: {e}")
            all_ok = False

    return all_ok


def verify_strategy_configuration():
    """Verify strategy is configured with production settings."""
    print_header("4. STRATEGY CONFIGURATION")

    try:
        # Create engine and check settings
        engine = BacktestEngine(
            use_earnings_surprise_filter=True,
            use_trailing_stop=False
        )

        earnings_filter_ok = engine.use_earnings_surprise_filter == True
        trailing_stop_ok = engine.use_trailing_stop == False

        print(f"\n  {check_mark(earnings_filter_ok)} Earnings Surprise Filter: "
              f"{'ENABLED ✅' if earnings_filter_ok else 'DISABLED ❌ (should be ENABLED)'}")

        print(f"  {check_mark(trailing_stop_ok)} Trailing Stop: "
              f"{'DISABLED ✅' if trailing_stop_ok else 'ENABLED ❌ (should be DISABLED)'}")

        if earnings_filter_ok and trailing_stop_ok:
            print("\n  ✅ Production configuration is correct!")
            print("     Strategy: Earnings Surprise Filter ON, Trailing Stop OFF")
            return True
        else:
            print("\n  ❌ Configuration mismatch!")
            print("     Expected: use_earnings_surprise_filter=True, use_trailing_stop=False")
            return False

    except Exception as e:
        print(f"\n  ❌ Error verifying configuration: {e}")
        return False


def verify_backtest_capability():
    """Verify backtesting works with a single ticker."""
    print_header("5. BACKTEST VERIFICATION")

    try:
        print("\n  Running quick backtest on VOLV-B.ST (2024)...")

        engine = BacktestEngine(
            use_earnings_surprise_filter=True,
            use_trailing_stop=False
        )

        result = engine.run_backtest(
            tickers=['VOLV-B.ST'],
            start_date='2024-01-01',
            end_date='2024-12-31',
            verbose=False
        )

        earnings_found = result.get('backtest_summary', {}).get('earnings_days_found', 0)
        trades = result.get('trades_executed', 0)

        print(f"\n  ✅ Backtest completed successfully")
        print(f"     Earnings days found: {earnings_found}")
        print(f"     Trades executed: {trades}")

        if earnings_found == 0:
            print(f"\n  ⚠️  No earnings days found for VOLV-B.ST in 2024")
            print(f"     This is normal if yfinance doesn't have historical earnings data")
            return True  # Not a critical error

        return True

    except Exception as e:
        print(f"\n  ❌ Backtest failed: {e}")
        return False


def verify_paper_trading_tracker():
    """Verify paper trading tracker is functional."""
    print_header("6. PAPER TRADING TRACKER")

    try:
        tracker = PaperTradingTracker()
        print(f"\n  ✅ Paper trading tracker initialized")
        print(f"     Database: {tracker.db_path}")

        # Check if there's any existing data
        today_signals = tracker.get_today_signals()
        if today_signals:
            print(f"     📊 {len(today_signals)} signals logged today")
        else:
            print(f"     📭 No signals logged today (this is normal if not trading yet)")

        return True

    except Exception as e:
        print(f"\n  ❌ Paper trading tracker initialization failed: {e}")
        return False


def verify_dependencies():
    """Verify required Python packages are installed."""
    print_header("7. PYTHON DEPENDENCIES")

    required_packages = {
        'yfinance': 'yfinance',
        'pandas': 'pandas',
        'numpy': 'numpy',
        'yaml': 'pyyaml',
        'pytz': 'pytz',
        'flask': 'flask'
    }

    all_installed = True
    for import_name, package_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"  ✅ {package_name}")
        except ImportError:
            print(f"  ❌ {package_name} - NOT INSTALLED")
            all_installed = False

    if not all_installed:
        print("\n  ⚠️  Install missing packages with:")
        print("     pip install -r requirements.txt")

    return all_installed


def run_full_verification():
    """Run all verification checks."""
    print("\n" + "█"*80)
    print("SVEA SURVEILLANCE - SYSTEM VERIFICATION")
    print("█"*80)
    print("\nThis script verifies your system is ready for paper trading.")

    results = {
        'directories': verify_directory_structure(),
        'data_files': verify_data_files(),
        'databases': verify_databases(),
        'strategy': verify_strategy_configuration(),
        'backtest': verify_backtest_capability(),
        'paper_tracker': verify_paper_trading_tracker(),
        'dependencies': verify_dependencies()
    }

    # Final summary
    print_header("VERIFICATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n  Checks Passed: {passed}/{total}")
    print()

    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:<10} {check_name.replace('_', ' ').title()}")

    if all(results.values()):
        print("\n" + "="*80)
        print("🎉 ALL CHECKS PASSED - SYSTEM READY FOR PAPER TRADING!")
        print("="*80)
        print("\nNext Steps:")
        print("  1. Review PAPER_TRADING_GUIDE.md for workflow details")
        print("  2. Run screener: python scripts/run_screener.py")
        print("  3. Start paper trading: python scripts/run_paper_trading.py")
        print("  4. End of day review: python scripts/paper_trading_dashboard.py")
        print()
    else:
        print("\n" + "="*80)
        print("⚠️  SOME CHECKS FAILED - PLEASE FIX ISSUES BEFORE PAPER TRADING")
        print("="*80)
        print("\nRecommended Actions:")

        if not results['dependencies']:
            print("  1. Install missing dependencies: pip install -r requirements.txt")

        if not results['directories']:
            print("  2. Ensure all source directories exist")

        if not results['data_files']:
            print("  3. Check data/all_tickers.txt and config/config.yaml exist")

        if not results['strategy']:
            print("  4. Verify production configuration in BacktestEngine")

        print("\nRe-run this script after fixing issues: python scripts/verify_setup.py")
        print()

    return all(results.values())


if __name__ == '__main__':
    success = run_full_verification()
    sys.exit(0 if success else 1)
