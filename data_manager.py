"""
Data persistence layer for console and history data.
Handles loading, saving, and utility functions for data management.
"""

import os
import sys
import json


def data_dir():
    """Get the application data directory, creating it if necessary."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    d = os.path.join(base, "RetroPickerWheel")
    os.makedirs(d, exist_ok=True)
    return d


HISTORY_FILE = os.path.join(data_dir(), "history.json")
CONSOLES_FILE = os.path.join(data_dir(), "consoles.json")


def load_consoles():
    """Load console database from disk, return empty list if not found."""
    if os.path.exists(CONSOLES_FILE):
        try:
            with open(CONSOLES_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_consoles(db):
    """Save console database to disk."""
    with open(CONSOLES_FILE, "w") as f:
        json.dump(db, f, indent=2)


def load_history():
    """Load roll history from disk, return empty list if not found."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(history):
    """Save roll history to disk."""
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def dedupe_keep_order(items):
    """Remove duplicates from list while preserving order."""
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
