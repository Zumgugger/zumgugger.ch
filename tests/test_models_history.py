"""Tests for ContentChange model and history utilities (Phase 2.3)."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Site, AdminUser, ContentChange
from app.utils.history import (
    ChangeTracker,
    get_recent_changes,
    get_last_change,
    delete_old_changes,
    record_change,
)


@pytest.fixture
def db_session(temp_db_path):
    """Create a test database session with all models."""
    engine = create_engine(
        f"sqlite:///{temp_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def site(db_session: Session) -> Site:
    """Create a test site."""
    site = Site(domain="history-test.com", site_type="band", name="History Test")
    db_session.add(site)
    db_session.commit()
    return site


@pytest.fixture
def admin_user(db_session: Session, site: Site) -> AdminUser:
    """Create a test admin user."""
    admin = AdminUser(site_id=site.id, username="admin", password_hash="hash")
    db_session.add(admin)
    db_session.commit()
    return admin


class TestContentChangeModel:
    """Tests for the ContentChange model."""

    def test_create_content_change(self, db_session: Session, site: Site, admin_user: AdminUser):
        """Test creating a ContentChange."""
        change = ContentChange(
            site_id=site.id,
            admin_user_id=admin_user.id,
            module_type="hero",
            field_name="headline",
            old_value="Old Title",
            new_value="New Title",
        )
        db_session.add(change)
        db_session.commit()
        
        assert change.id is not None
        assert change.site_id == site.id
        assert change.admin_user_id == admin_user.id
        assert change.module_type == "hero"
        assert change.field_name == "headline"
        assert change.old_value == "Old Title"
        assert change.new_value == "New Title"
        assert change.timestamp is not None

    def test_content_change_json_values(self, db_session: Session, site: Site):
        """Test ContentChange with JSON values (for array fields)."""
        old_services = [{"title": "Old", "description": "Old desc"}]
        new_services = [
            {"title": "Old", "description": "Old desc"},
            {"title": "New", "description": "New desc"},
        ]
        
        change = ContentChange(
            site_id=site.id,
            module_type="services",
            field_name="items",
            old_value=old_services,
            new_value=new_services,
        )
        db_session.add(change)
        db_session.commit()
        
        db_session.refresh(change)
        
        assert change.old_value == old_services
        assert change.new_value == new_services

    def test_describe_default(self, db_session: Session, site: Site):
        """Test describe() method with default description."""
        change = ContentChange(
            site_id=site.id,
            module_type="hero",
            field_name="headline",
            old_value="Old",
            new_value="New",
        )
        
        description = change.describe()
        assert "Hero" in description
        assert "Überschrift" in description

    def test_describe_custom(self, db_session: Session, site: Site):
        """Test describe() method with custom description."""
        change = ContentChange(
            site_id=site.id,
            module_type="hero",
            field_name="headline",
            old_value="Old",
            new_value="New",
            description="Custom change description",
        )
        
        assert change.describe() == "Custom change description"

    def test_content_change_relationships(self, db_session: Session, site: Site, admin_user: AdminUser):
        """Test ContentChange relationships."""
        change = ContentChange(
            site_id=site.id,
            admin_user_id=admin_user.id,
            module_type="hero",
            field_name="headline",
            old_value="Old",
            new_value="New",
        )
        db_session.add(change)
        db_session.commit()
        
        db_session.refresh(change)
        
        assert change.site == site
        assert change.admin_user == admin_user
        assert change in site.changes
        assert change in admin_user.changes

    def test_cascade_delete_site(self, db_session: Session, site: Site):
        """Test that deleting site cascades to changes."""
        change = ContentChange(
            site_id=site.id,
            module_type="hero",
            field_name="headline",
            old_value="Old",
            new_value="New",
        )
        db_session.add(change)
        db_session.commit()
        
        change_id = change.id
        
        db_session.delete(site)
        db_session.commit()
        
        deleted_change = db_session.get(ContentChange, change_id)
        assert deleted_change is None

    def test_admin_user_set_null_on_delete(self, db_session: Session, site: Site, admin_user: AdminUser):
        """Test that deleting admin user sets admin_user_id to NULL."""
        change = ContentChange(
            site_id=site.id,
            admin_user_id=admin_user.id,
            module_type="hero",
            field_name="headline",
            old_value="Old",
            new_value="New",
        )
        db_session.add(change)
        db_session.commit()
        
        change_id = change.id
        
        db_session.delete(admin_user)
        db_session.commit()
        
        # Change should still exist, but with NULL admin_user_id
        existing_change = db_session.get(ContentChange, change_id)
        assert existing_change is not None
        assert existing_change.admin_user_id is None


class TestChangeTracker:
    """Tests for the ChangeTracker utility class."""

    def test_track_change(self, db_session: Session, site: Site, admin_user: AdminUser):
        """Test tracking a change."""
        tracker = ChangeTracker(db_session, site.id, admin_user.id)
        
        change = tracker.track("hero", "headline", "Old", "New")
        
        assert change.module_type == "hero"
        assert change.field_name == "headline"
        assert tracker.pending_count == 1

    def test_track_multiple_changes(self, db_session: Session, site: Site):
        """Test tracking multiple changes."""
        tracker = ChangeTracker(db_session, site.id)
        
        tracker.track("hero", "headline", "Old1", "New1")
        tracker.track("hero", "cta_text", "Old2", "New2")
        tracker.track("services", "items", [], [{"title": "New"}])
        
        assert tracker.pending_count == 3

    def test_save_changes(self, db_session: Session, site: Site, admin_user: AdminUser):
        """Test saving tracked changes."""
        tracker = ChangeTracker(db_session, site.id, admin_user.id)
        
        tracker.track("hero", "headline", "Old", "New")
        tracker.track("services", "items", [], [{"title": "New"}])
        
        saved = tracker.save()
        db_session.commit()
        
        assert len(saved) == 2
        assert tracker.pending_count == 0
        
        # Verify saved in database
        changes = db_session.query(ContentChange).filter_by(site_id=site.id).all()
        assert len(changes) == 2

    def test_clear_changes(self, db_session: Session, site: Site):
        """Test clearing pending changes."""
        tracker = ChangeTracker(db_session, site.id)
        
        tracker.track("hero", "headline", "Old", "New")
        assert tracker.pending_count == 1
        
        tracker.clear()
        assert tracker.pending_count == 0


class TestHistoryUtilities:
    """Tests for history utility functions."""

    def test_get_recent_changes(self, db_session: Session, site: Site):
        """Test get_recent_changes function."""
        # Create several changes
        for i in range(5):
            change = ContentChange(
                site_id=site.id,
                module_type="hero",
                field_name="headline",
                old_value=f"Value {i}",
                new_value=f"Value {i+1}",
            )
            db_session.add(change)
        db_session.commit()
        
        recent = get_recent_changes(db_session, site.id, limit=3)
        
        assert len(recent) == 3
        # Should be newest first
        assert recent[0].new_value == "Value 5"

    def test_get_last_change(self, db_session: Session, site: Site):
        """Test get_last_change function."""
        change1 = ContentChange(
            site_id=site.id,
            module_type="hero",
            field_name="headline",
            old_value="First",
            new_value="Second",
        )
        db_session.add(change1)
        db_session.commit()
        
        change2 = ContentChange(
            site_id=site.id,
            module_type="hero",
            field_name="cta_text",
            old_value="Old CTA",
            new_value="New CTA",
        )
        db_session.add(change2)
        db_session.commit()
        
        last = get_last_change(db_session, site.id)
        
        assert last is not None
        assert last.field_name == "cta_text"

    def test_get_last_change_empty(self, db_session: Session, site: Site):
        """Test get_last_change with no changes."""
        last = get_last_change(db_session, site.id)
        assert last is None

    def test_delete_old_changes(self, db_session: Session, site: Site):
        """Test delete_old_changes function."""
        # Create 10 changes
        for i in range(10):
            change = ContentChange(
                site_id=site.id,
                module_type="hero",
                field_name="headline",
                old_value=f"Value {i}",
                new_value=f"Value {i+1}",
            )
            db_session.add(change)
        db_session.commit()
        
        # Keep only 3
        deleted_count = delete_old_changes(db_session, site.id, keep_count=3)
        db_session.commit()
        
        assert deleted_count == 7
        
        remaining = db_session.query(ContentChange).filter_by(site_id=site.id).count()
        assert remaining == 3

    def test_record_change(self, db_session: Session, site: Site, admin_user: AdminUser):
        """Test record_change convenience function."""
        change = record_change(
            db_session,
            site.id,
            admin_user.id,
            "hero",
            "headline",
            "Old Headline",
            "New Headline",
            description="Test change",
        )
        db_session.commit()
        
        assert change.id is not None
        assert change.description == "Test change"
        
        # Verify in database
        db_change = db_session.get(ContentChange, change.id)
        assert db_change is not None
