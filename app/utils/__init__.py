"""Utility functions for WebsiteCMS."""

from app.utils.history import (
    ChangeTracker,
    get_recent_changes,
    get_last_change,
    delete_old_changes,
    record_change,
)

__all__ = [
    "ChangeTracker",
    "get_recent_changes",
    "get_last_change",
    "delete_old_changes",
    "record_change",
]
