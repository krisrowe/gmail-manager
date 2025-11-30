#!/usr/bin/env python3
"""
Application configuration paths.
Follows XDG Base Directory standard with environment variable override.
"""

import os
from pathlib import Path

# Application name
APP_NAME = "gmail-manager"

# Configuration directory
# Can be overridden with GMAIL_MANAGER_CONFIG_DIR environment variable
# Default: ~/.config/gmail-manager
GMAIL_MANAGER_CONFIG_DIR = os.environ.get(
    "GMAIL_MANAGER_CONFIG_DIR",
    os.path.expanduser(f"~/.config/{APP_NAME}")
)

# State/data directory (for rules_usage.json, processed_*.json, etc.)
# Can be overridden with GMAIL_MANAGER_DATA_DIR environment variable
# Default: ~/.local/share/gmail-manager
GMAIL_MANAGER_DATA_DIR = os.environ.get(
    "GMAIL_MANAGER_DATA_DIR",
    os.path.expanduser(f"~/.local/share/{APP_NAME}")
)

# Ensure directories exist
Path(GMAIL_MANAGER_CONFIG_DIR).mkdir(parents=True, exist_ok=True)
Path(GMAIL_MANAGER_DATA_DIR).mkdir(parents=True, exist_ok=True)
