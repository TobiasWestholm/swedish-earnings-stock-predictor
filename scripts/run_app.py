#!/usr/bin/env python3
"""
Run the Svea Surveillance web application.

This script starts the Flask web server for the dashboard UI.

Usage:
    python scripts/run_app.py [--host HOST] [--port PORT] [--debug]

Examples:
    python scripts/run_app.py                       # Default: localhost:5000
    python scripts/run_app.py --port 5001           # Run on port 5001
    python scripts/run_app.py --debug               # Enable debug mode
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ui.app import create_app
from src.utils.config import load_config
from src.utils.database import init_database
from src.utils.logger import get_default_logger


def main():
    """Main entry point for web application."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Run Svea Surveillance web app')
    parser.add_argument(
        '--host',
        type=str,
        help='Host to bind to (default: from config)'
    )
    parser.add_argument(
        '--port',
        type=int,
        help='Port to bind to (default: from config)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    args = parser.parse_args()

    # Setup logger
    logger = get_default_logger()

    # Load configuration
    config = load_config()
    ui_config = config.get('ui', {})

    host = args.host or ui_config.get('host', '127.0.0.1')
    port = args.port or ui_config.get('port', 5000)
    debug = args.debug or ui_config.get('debug', False)

    # Ensure database exists
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Create Flask app
    try:
        app = create_app()
        logger.info("Flask application created")
    except Exception as e:
        logger.error(f"Failed to create Flask app: {e}")
        sys.exit(1)

    # Print startup info
    print("\n" + "=" * 80)
    print("SVEA SURVEILLANCE - WEB DASHBOARD")
    print("=" * 80)
    print(f"\n✓ Starting web server...")
    print(f"  - Host: {host}")
    print(f"  - Port: {port}")
    print(f"  - Debug: {debug}")
    print(f"\n✓ Dashboard URL: http://{host}:{port}/")
    print(f"\nAvailable pages:")
    print(f"  - Dashboard:  http://{host}:{port}/")
    print(f"  - Watchlist:  http://{host}:{port}/watchlist")
    print(f"  - Signals:    http://{host}:{port}/signals")
    print(f"  - History:    http://{host}:{port}/history")
    print(f"\n✓ Press Ctrl+C to stop the server")
    print("=" * 80 + "\n")

    # Run the app
    try:
        app.run(
            host=host,
            port=port,
            debug=debug
        )
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped by user")
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error running server: {e}", exc_info=True)
        print(f"\n✗ Error running server: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
