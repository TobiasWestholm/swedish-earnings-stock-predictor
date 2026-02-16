#!/usr/bin/env python3
"""
Run the web application with automatic daily scheduler.

This script:
1. Starts the daily scheduler (08:30 screener, 17:30 cleanup)
2. Starts the Flask web application
3. Keeps both running until stopped

Usage:
    python scripts/run_with_scheduler.py

    or for production:

    python scripts/run_with_scheduler.py --host 0.0.0.0 --port 5000
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logger
from src.utils.scheduler import start_scheduler
from src.ui.app import create_app
from src.utils.database import init_database

import logging

logger = setup_logger()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run web app with scheduler')
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )
    parser.add_argument(
        '--no-scheduler',
        action='store_true',
        help='Disable automatic scheduler (manual mode only)'
    )
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("SVEA SURVEILLANCE - STARTING WITH SCHEDULER")
    logger.info("=" * 80)

    # Initialize database
    try:
        init_database()
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Start scheduler (unless disabled)
    scheduler = None
    if not args.no_scheduler:
        try:
            logger.info("Starting daily scheduler...")
            scheduler = start_scheduler()
            logger.info("✓ Scheduler started")
            logger.info("  - 08:30 CET: Morning screener (automatic)")
            logger.info("  - 17:30 CET: End of day cleanup (automatic)")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            logger.warning("Continuing without scheduler...")
    else:
        logger.info("Scheduler disabled (--no-scheduler flag)")

    # Create and run Flask app
    try:
        logger.info(f"Starting web application on {args.host}:{args.port}...")
        app = create_app()

        logger.info("=" * 80)
        logger.info("✓ SYSTEM READY")
        logger.info("=" * 80)
        logger.info(f"\nWeb UI:  http://{args.host}:{args.port}")
        logger.info("\nPages:")
        logger.info(f"  - Dashboard:  http://{args.host}:{args.port}/")
        logger.info(f"  - Watchlist:  http://{args.host}:{args.port}/watchlist")
        logger.info(f"  - Signals:    http://{args.host}:{args.port}/signals")

        if scheduler:
            logger.info("\nAutomatic Tasks:")
            logger.info("  - 08:30: Morning screener runs automatically")
            logger.info("  - 09:00: Live monitor starts automatically (runs until 10:30)")
            logger.info("  - 17:00: Hypothetical trades closed automatically")
            logger.info("  - 17:30: Old data cleared automatically")

        logger.info("\nPress Ctrl+C to stop")
        logger.info("=" * 80 + "\n")

        # Run Flask (blocking)
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False  # Disable reloader to prevent scheduler duplication
        )

    except KeyboardInterrupt:
        logger.info("\n\nShutting down gracefully...")
        if scheduler:
            scheduler.stop()
            logger.info("✓ Scheduler stopped")
        logger.info("✓ Web application stopped")
        logger.info("Goodbye!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Error running application: {e}", exc_info=True)
        if scheduler:
            scheduler.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()
