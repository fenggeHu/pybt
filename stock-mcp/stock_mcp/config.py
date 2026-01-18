"""
Configuration settings for the Stock MCP server.
"""

from pathlib import Path
import os

# Base directory
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database path
DB_PATH = str(DATA_DIR / "cache.db")

# Cache settings
CACHE_DAYS = 1  # Cache freshness threshold in days

# Data fetching settings
DEFAULT_START_DATE_OFFSET = 90  # Default: fetch last 90 days
MAX_RETRIES = 3
REQUEST_DELAY = 1  # Seconds between requests to be polite

# Screening defaults
DEFAULT_VOLUME_THRESHOLD = 50.0  # Volume growth rate threshold (%)
DEFAULT_AMOUNT_THRESHOLD = 50.0  # Amount growth rate threshold (%)
DEFAULT_RECENT_DAYS = 3  # Recent days to analyze
DEFAULT_COMPARE_PERIOD = 20  # Comparison period (days)
