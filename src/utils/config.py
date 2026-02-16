"""Configuration management for Svea Surveillance."""

import yaml
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

_config_cache = None


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Optional path to config file. Defaults to config/config.yaml

    Returns:
        Configuration dictionary
    """
    global _config_cache

    # Return cached config if available
    if _config_cache is not None:
        return _config_cache

    # Default config path
    if config_path is None:
        config_path = "config/config.yaml"

    # Convert to absolute path
    if not os.path.isabs(config_path):
        # Assuming we're running from project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / config_path

    # Load YAML
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Override with environment variables if present
    if os.getenv('ACCOUNT_VALUE'):
        config['risk']['account_value'] = float(os.getenv('ACCOUNT_VALUE'))

    if os.getenv('RISK_PER_TRADE'):
        config['risk']['risk_per_trade'] = float(os.getenv('RISK_PER_TRADE'))

    # Cache the config
    _config_cache = config

    return config


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Get a configuration value using dot notation.

    Args:
        key_path: Dot-separated path to config value (e.g., 'risk.account_value')
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    config = load_config()
    keys = key_path.split('.')

    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def reload_config():
    """Force reload of configuration from file."""
    global _config_cache
    _config_cache = None
    return load_config()
