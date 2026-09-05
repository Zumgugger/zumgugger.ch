"""History tracking utilities for content changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.history import ContentChange


class ChangeTracker:
    """Utility class for tracking and recording content changes.
    
    Usage:
        tracker = ChangeTracker(db_session, site_id, admin_user_id)
        tracker.track("hero", "headline", old_value, new_value)
        tracker.save()
    """

    def __init__(
        self,
        db: Session,
        site_id: int,
        admin_user_id: Optional[int] = None,
    ):
        """Initialize the change tracker.
        
        Args:
            db: Database session.
            site_id: ID of the site being modified.
            admin_user_id: ID of the admin making changes (optional).
        """
        self.db = db
        self.site_id = site_id
        self.admin_user_id = admin_user_id
        self._pending_changes: list[ContentChange] = []

    def track(
        self,
        module_type: str,
        field_name: str,
        old_value: Any,
        new_value: Any,
        description: Optional[str] = None,
    ) -> ContentChange:
        """Track a content change.
        
        Args:
            module_type: The module being changed (hero, services, etc.)
            field_name: The field being changed (headline, items, etc.)
            old_value: The value before the change.
            new_value: The value after the change.
            description: Optional description of the change.
            
        Returns:
            The created ContentChange record (not yet saved).
        """
        change = ContentChange(
            site_id=self.site_id,
            admin_user_id=self.admin_user_id,
            timestamp=datetime.now(timezone.utc),
            module_type=module_type,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            description=description,
        )
        self._pending_changes.append(change)
        return change

    def save(self) -> list[ContentChange]:
        """Save all pending changes to the database.
        
        Returns:
            List of saved ContentChange records.
        """
        for change in self._pending_changes:
            self.db.add(change)
        
        self.db.flush()  # Get IDs assigned
        
        saved = self._pending_changes.copy()
        self._pending_changes = []
        
        return saved

    def clear(self) -> None:
        """Clear pending changes without saving."""
        self._pending_changes = []

    @property
    def pending_count(self) -> int:
        """Number of pending (unsaved) changes."""
        return len(self._pending_changes)


def get_recent_changes(
    db: Session,
    site_id: int,
    limit: int = 50,
) -> list[ContentChange]:
    """Get the most recent changes for a site.
    
    Args:
        db: Database session.
        site_id: ID of the site.
        limit: Maximum number of changes to return.
        
    Returns:
        List of ContentChange records, newest first.
    """
    return (
        db.query(ContentChange)
        .filter(ContentChange.site_id == site_id)
        .order_by(ContentChange.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_last_change(
    db: Session,
    site_id: int,
) -> Optional[ContentChange]:
    """Get the most recent change for a site.
    
    Args:
        db: Database session.
        site_id: ID of the site.
        
    Returns:
        The most recent ContentChange, or None if no changes.
    """
    return (
        db.query(ContentChange)
        .filter(ContentChange.site_id == site_id)
        .order_by(ContentChange.timestamp.desc())
        .first()
    )


def delete_old_changes(
    db: Session,
    site_id: int,
    keep_count: int = 50,
) -> int:
    """Delete old changes, keeping only the most recent ones.
    
    Args:
        db: Database session.
        site_id: ID of the site.
        keep_count: Number of recent changes to keep.
        
    Returns:
        Number of changes deleted.
    """
    # Get IDs of changes to keep
    keep_ids = [
        c.id for c in (
            db.query(ContentChange.id)
            .filter(ContentChange.site_id == site_id)
            .order_by(ContentChange.timestamp.desc())
            .limit(keep_count)
            .all()
        )
    ]
    
    if not keep_ids:
        return 0
    
    # Delete changes not in the keep list
    deleted = (
        db.query(ContentChange)
        .filter(ContentChange.site_id == site_id)
        .filter(~ContentChange.id.in_(keep_ids))
        .delete(synchronize_session=False)
    )
    
    return deleted


def record_change(
    db: Session,
    site_id: int,
    admin_user_id: Optional[int],
    module_type: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    description: Optional[str] = None,
) -> ContentChange:
    """Convenience function to record a single change immediately.
    
    Args:
        db: Database session.
        site_id: ID of the site.
        admin_user_id: ID of the admin making the change.
        module_type: The module being changed.
        field_name: The field being changed.
        old_value: The value before the change.
        new_value: The value after the change.
        description: Optional description of the change.
        
    Returns:
        The saved ContentChange record.
    """
    change = ContentChange(
        site_id=site_id,
        admin_user_id=admin_user_id,
        timestamp=datetime.now(timezone.utc),
        module_type=module_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        description=description,
    )
    db.add(change)
    db.flush()
    return change
