"""Flask web application for Earnings Predictor dashboard."""

from flask import Flask
from datetime import datetime
import logging

from src.utils.config import load_config
from src.utils.logger import setup_logger


def create_app():
    """
    Create and configure Flask application.

    Returns:
        Configured Flask app instance
    """
    # Load configuration
    config = load_config()
    ui_config = config.get('ui', {})

    # Setup logging
    log_config = config.get('logging', {})
    logger = setup_logger(
        name='earnings_predictor',
        log_file=log_config.get('file', 'logs/earnings_predictor.log'),
        level=log_config.get('level', 'INFO')
    )

    # Create Flask app
    app = Flask(__name__)

    # Configure Flask
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    app.config['DEBUG'] = ui_config.get('debug', True)

    # Register routes
    from src.ui.routes import register_routes
    register_routes(app)

    # Add template context processors
    @app.context_processor
    def inject_now():
        """Inject current datetime into all templates."""
        return {'now': datetime.now()}

    logger.info("Flask application created successfully")

    return app
