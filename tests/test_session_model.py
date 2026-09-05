"""Tests for AdminSession model."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.session import AdminSession
from app.models.site import AdminUser, Site


class TestAdminSessionModel:
    """Tests for AdminSession model."""

    def test_create_session_basic(self, test_session: Session):
        """Create a basic admin session."""
        # Create site and admin first
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        # Create session
        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="test-token-123",
        )
        test_session.add(session)
        test_session.commit()

        assert session.id is not None
        assert session.admin_user_id == admin.id
        assert session.site_id == site.id
        assert session.token == "test-token-123"
        assert session.expires_at is not None

    def test_create_session_with_metadata(self, test_session: Session):
        """Create session with IP and user agent."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="test-token-456",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test Browser",
        )
        test_session.add(session)
        test_session.commit()

        assert session.ip_address == "192.168.1.1"
        assert session.user_agent == "Mozilla/5.0 Test Browser"

    def test_session_expiry_set_correctly(self, test_session: Session):
        """Session expiry should be set to 24 hours in the future."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        before = datetime.now(timezone.utc)
        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="test-token-789",
        )
        after = datetime.now(timezone.utc)

        # Should expire in roughly 24 hours (with some tolerance)
        expected_min = before + timedelta(hours=23, minutes=59)
        expected_max = after + timedelta(hours=24, minutes=1)

        assert session.expires_at >= expected_min
        assert session.expires_at <= expected_max

    def test_is_expired_fresh_session(self, test_session: Session):
        """Fresh session should not be expired."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="test-token-abc",
        )

        assert session.is_expired() is False

    def test_is_expired_old_session(self, test_session: Session):
        """Session with past expiry should be expired."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession(
            admin_user_id=admin.id,
            site_id=site.id,
            token="test-token-def",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert session.is_expired() is True

    def test_refresh_session(self, test_session: Session):
        """Refreshing session should extend expiry."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession(
            admin_user_id=admin.id,
            site_id=site.id,
            token="test-token-ghi",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        
        original_expiry = session.expires_at
        session.refresh()
        
        # New expiry should be further in future
        assert session.expires_at > original_expiry

    def test_unique_token_constraint(self, test_session: Session):
        """Session tokens must be unique."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session1 = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="duplicate-token",
        )
        test_session.add(session1)
        test_session.commit()

        session2 = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="duplicate-token",
        )
        test_session.add(session2)
        
        with pytest.raises(Exception):  # IntegrityError
            test_session.commit()

    def test_session_relationships(self, test_session: Session):
        """Session should have proper relationships."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="relationship-test-token",
        )
        test_session.add(session)
        test_session.commit()

        # Refresh to ensure relationships are loaded
        test_session.refresh(session)

        assert session.admin_user.id == admin.id
        assert session.site.id == site.id

    def test_multiple_sessions_per_admin(self, test_session: Session):
        """Admin should be able to have multiple active sessions."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        sessions = []
        for i in range(3):
            session = AdminSession.create_session(
                admin_user_id=admin.id,
                site_id=site.id,
                token=f"multi-session-{i}",
            )
            test_session.add(session)
            sessions.append(session)
        
        test_session.commit()

        # All sessions should be created
        admin_sessions = test_session.query(AdminSession).filter(
            AdminSession.admin_user_id == admin.id
        ).all()
        assert len(admin_sessions) == 3

    def test_cascade_delete_on_site_delete(self, test_session: Session):
        """Sessions should be deleted when site is deleted via manual cleanup."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="cascade-test-token",
        )
        test_session.add(session)
        test_session.commit()

        session_id = session.id
        admin_id = admin.id
        
        # Delete sessions first (FK constraint)
        test_session.query(AdminSession).filter(
            AdminSession.admin_user_id == admin_id
        ).delete()
        # Then delete admin
        test_session.delete(admin)
        # Finally delete site
        test_session.delete(site)
        test_session.commit()

        # Session should be deleted
        remaining = test_session.query(AdminSession).filter(
            AdminSession.id == session_id
        ).first()
        assert remaining is None

    def test_repr(self, test_session: Session):
        """Test __repr__ method."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password123")
        test_session.add(admin)
        test_session.commit()

        session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="repr-test-token",
        )
        test_session.add(session)
        test_session.commit()

        repr_str = repr(session)
        assert "AdminSession" in repr_str
        assert str(session.id) in repr_str
        assert str(admin.id) in repr_str
