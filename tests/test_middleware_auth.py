"""Tests for auth middleware."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import (
    SESSION_COOKIE_NAME,
    cleanup_expired_sessions,
    get_current_admin,
    get_current_session,
    get_optional_admin,
    get_session_token,
    get_site_from_request,
    require_auth,
)
from app.models.session import AdminSession
from app.models.site import AdminUser, Site


def extract_session_token(response) -> str | None:
    """Extract session token from response set-cookie header."""
    set_cookie = response.headers.get("set-cookie", "")
    match = re.search(r'session_token=([^;]+)', set_cookie)
    return match.group(1) if match else None


class TestGetSessionToken:
    """Tests for get_session_token dependency."""

    def test_extracts_token_from_cookie(self):
        """Should extract token from cookie."""
        token = get_session_token(session_token="test-token-123")
        assert token == "test-token-123"

    def test_returns_none_when_no_cookie(self):
        """Should return None when no cookie."""
        token = get_session_token(session_token=None)
        assert token is None


class TestGetCurrentSession:
    """Tests for get_current_session - integration tests via API."""

    def test_returns_none_for_no_token(self, client: TestClient):
        """Should return None (401) when no token provided."""
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_returns_none_for_invalid_token(self, client: TestClient):
        """Should return None (401) for nonexistent token."""
        client.cookies.set(SESSION_COOKIE_NAME, "invalid-token")
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_returns_session_for_valid_token(self, client: TestClient, test_session: Session):
        """Should return session (200) for valid token."""
        # Create test data
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password")
        test_session.add(admin)
        test_session.commit()

        # Login to get valid token
        login_response = client.post(
            "/admin/login",
            json={
                "username": "admin",
                "password": "password",
                "site_domain": "test.example.com",
            },
        )
        assert login_response.status_code == 200
        token = extract_session_token(login_response)
        client.cookies.set(SESSION_COOKIE_NAME, token)

        # Access protected route
        response = client.get("/admin/me")
        assert response.status_code == 200
        assert response.json()["username"] == "admin"

    def test_returns_none_for_expired_token(self, client: TestClient, test_session: Session):
        """Should return None (401) for expired session and clean it up."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password")
        test_session.add(admin)
        test_session.commit()

        # Create expired session directly
        admin_session = AdminSession(
            admin_user_id=admin.id,
            site_id=site.id,
            token="expired-token-test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        test_session.add(admin_session)
        test_session.commit()

        client.cookies.set(SESSION_COOKIE_NAME, "expired-token-test")
        response = client.get("/admin/me")
        assert response.status_code == 401

        # Session should be deleted
        remaining = test_session.query(AdminSession).filter(
            AdminSession.token == "expired-token-test"
        ).first()
        assert remaining is None


class TestRequireAuth:
    """Tests for require_auth dependency."""

    def test_require_auth_rejects_missing_token(self, client: TestClient):
        """Protected route should reject missing token."""
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_require_auth_rejects_invalid_token(self, client: TestClient):
        """Protected route should reject invalid token."""
        client.cookies.set(SESSION_COOKIE_NAME, "invalid-token")
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_require_auth_accepts_valid_token(self, client: TestClient, test_session: Session):
        """Protected route should accept valid token."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password")
        test_session.add(admin)
        test_session.commit()

        # Login to get valid token
        login_response = client.post(
            "/admin/login",
            json={
                "username": "admin",
                "password": "password",
                "site_domain": "test.example.com",
            },
        )
        assert login_response.status_code == 200
        token = extract_session_token(login_response)
        client.cookies.set(SESSION_COOKIE_NAME, token)

        # Access protected route
        response = client.get("/admin/me")
        assert response.status_code == 200

    def test_require_auth_rejects_expired_token(self, client: TestClient, test_session: Session):
        """Protected route should reject expired token."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password")
        test_session.add(admin)
        test_session.commit()

        # Create expired session
        admin_session = AdminSession(
            admin_user_id=admin.id,
            site_id=site.id,
            token="expired-token-123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        test_session.add(admin_session)
        test_session.commit()

        client.cookies.set(SESSION_COOKIE_NAME, "expired-token-123")
        response = client.get("/admin/me")
        assert response.status_code == 401


class TestCleanupExpiredSessions:
    """Tests for cleanup_expired_sessions function."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_sessions(self, test_session: Session):
        """Should delete expired sessions."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password")
        test_session.add(admin)
        test_session.commit()

        # Create expired sessions
        for i in range(3):
            session = AdminSession(
                admin_user_id=admin.id,
                site_id=site.id,
                token=f"expired-{i}",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            test_session.add(session)

        # Create valid session
        valid_session = AdminSession.create_session(
            admin_user_id=admin.id,
            site_id=site.id,
            token="valid-session",
        )
        test_session.add(valid_session)
        test_session.commit()

        # Run cleanup
        count = await cleanup_expired_sessions(test_session)
        assert count == 3

        # Valid session should remain
        remaining = test_session.query(AdminSession).all()
        assert len(remaining) == 1
        assert remaining[0].token == "valid-session"

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero_when_no_expired(self, test_session: Session):
        """Should return 0 when no expired sessions."""
        count = await cleanup_expired_sessions(test_session)
        assert count == 0


class TestGetSiteFromRequest:
    """Tests for get_site_from_request function."""

    def test_gets_site_from_query_param(self, client: TestClient, test_session: Session):
        """Should get site from query parameter."""
        site = Site(domain="query-test.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="admin")
        admin.set_password("password")
        test_session.add(admin)
        test_session.commit()

        # Login using query param
        response = client.post(
            "/admin/login?site=query-test.com",
            json={
                "username": "admin",
                "password": "password",
            },
        )
        assert response.status_code == 200
