"""Logging setup for Svea Surveillance."""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logger(
    name: str = None,
    log_file: str = None,
    level: str = "INFO",
    console: bool = True
) -> logging.Logger:
    """
    Set up logging with file and console handlers.

    Args:
        name: Logger name (defaults to root logger)
        log_file: Path to log file (optional)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console: Whether to also log to console

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_default_logger() -> logging.Logger:
    """
    Get the default application logger with settings from config.

    Returns:
        Configured logger instance
    """
    try:
        from src.utils.config import load_config
        config = load_config()
        log_config = config.get('logging', {})

        return setup_logger(
            name='svea_surveillance',
            log_file=log_config.get('file', 'logs/svea_surveillance.log'),
            level=log_config.get('level', 'INFO'),
            console=True
        )
    except Exception as e:
        # Fallback if config can't be loaded
        print(f"Warning: Could not load logging config: {e}")
        return setup_logger(
            name='svea_surveillance',
            log_file='logs/svea_surveillance.log',
            level='INFO',
            console=True
        )
