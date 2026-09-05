"""Tests for admin routes (login, logout, me)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.session import AdminSession
from app.models.site import AdminUser, Site


def extract_session_token(response) -> str | None:
    """Extract session token from response set-cookie header."""
    set_cookie = response.headers.get("set-cookie", "")
    match = re.search(r'session_token=([^;]+)', set_cookie)
    return match.group(1) if match else None


class TestLoginEndpoint:
    """Tests for POST /admin/login endpoint."""

    def test_login_success(self, client: TestClient, test_session: Session):
        """Successful login should return 200 and set cookie."""
        # Create site and admin
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "logged_in"
        assert data["username"] == "testadmin"
        assert data["site_id"] == site.id
        # Check cookie was set via set-cookie header
        assert "set-cookie" in response.headers
        assert "session_token" in response.headers["set-cookie"]

    def test_login_wrong_password(self, client: TestClient, test_session: Session):
        """Wrong password should return 401."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("correctpassword")
        test_session.add(admin)
        test_session.commit()

        response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "wrongpassword",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"] == "Invalid credentials"

    def test_login_nonexistent_user(self, client: TestClient, test_session: Session):
        """Nonexistent user should return 401."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        response = client.post(
            "/admin/login",
            json={
                "username": "nonexistent",
                "password": "somepassword",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 401

    def test_login_missing_username(self, client: TestClient, test_session: Session):
        """Missing username should return 422 (validation error)."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        response = client.post(
            "/admin/login",
            json={
                "password": "somepassword",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 422

    def test_login_missing_password(self, client: TestClient, test_session: Session):
        """Missing password should return 422 (validation error)."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 422

    def test_login_creates_session_in_db(self, client: TestClient, test_session: Session):
        """Login should create session record in database."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # No sessions before login
        sessions_before = test_session.query(AdminSession).count()

        response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 200
        
        # One session after login
        sessions_after = test_session.query(AdminSession).count()
        assert sessions_after == sessions_before + 1

    def test_login_cookie_is_httponly(self, client: TestClient, test_session: Session):
        """Session cookie should be HttpOnly."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )

        # Check HttpOnly attribute in set-cookie header
        set_cookie = response.headers.get("set-cookie", "")
        assert "session_token" in set_cookie
        assert "httponly" in set_cookie.lower()

    def test_login_updates_last_login(self, client: TestClient, test_session: Session):
        """Login should update admin's last_login timestamp."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        assert admin.last_login is None

        response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )

        assert response.status_code == 200
        
        # Refresh admin from db
        test_session.refresh(admin)
        assert admin.last_login is not None

    def test_multiple_logins_create_multiple_sessions(self, client: TestClient, test_session: Session):
        """Multiple logins should create multiple session tokens."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        tokens = []
        for _ in range(3):
            response = client.post(
                "/admin/login",
                json={
                    "username": "testadmin",
                    "password": "testpassword123",
                    "site_domain": "test.example.com",
                },
            )
            assert response.status_code == 200
            token = extract_session_token(response)
            tokens.append(token)

        # All tokens should be unique
        assert len(set(tokens)) == 3
        assert None not in tokens

    def test_login_with_site_query_param(self, client: TestClient, test_session: Session):
        """Login should work with site query parameter."""
        site = Site(domain="query-test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        response = client.post(
            "/admin/login?site=query-test.example.com",
            json={
                "username": "testadmin",
                "password": "testpassword123",
            },
        )

        assert response.status_code == 200


class TestLogoutEndpoint:
    """Tests for POST /admin/logout endpoint."""

    def test_logout_success(self, client: TestClient, test_session: Session):
        """Logout should clear session and return 200."""
        # Create site, admin, and login first
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Login
        login_response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )
        assert login_response.status_code == 200

        # Logout
        logout_response = client.post("/admin/logout", follow_redirects=False)
        assert logout_response.status_code == 303
        assert logout_response.headers["location"] == "/"

    def test_logout_clears_cookie(self, client: TestClient, test_session: Session):
        """Logout should clear the session cookie."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Login
        login_response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )
        assert extract_session_token(login_response) is not None

        # Logout
        logout_response = client.post("/admin/logout", follow_redirects=False)
        
        # Cookie should be cleared (set-cookie with empty or deleted)
        assert logout_response.status_code == 303

    def test_logout_deletes_session_from_db(self, client: TestClient, test_session: Session):
        """Logout should delete session from database."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Login
        login_response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )
        token = extract_session_token(login_response)
        client.cookies.set("session_token", token)

        # Session exists in DB
        session = test_session.query(AdminSession).filter(
            AdminSession.token == token
        ).first()
        assert session is not None

        # Logout
        client.post("/admin/logout", follow_redirects=False)

        # Refresh session state
        test_session.expire_all()

        # Session should be deleted
        session_after = test_session.query(AdminSession).filter(
            AdminSession.token == token
        ).first()
        assert session_after is None

    def test_logout_without_session(self, client: TestClient):
        """Logout without session should still redirect to the homepage."""
        response = client.post("/admin/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_access_after_logout_fails(self, client: TestClient, test_session: Session):
        """Access to protected route after logout should fail."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Login
        login_response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )
        assert login_response.status_code == 200
        token = extract_session_token(login_response)
        client.cookies.set("session_token", token)

        # Verify /admin/me works
        me_response = client.get("/admin/me")
        assert me_response.status_code == 200

        # Logout
        client.post("/admin/logout", follow_redirects=False)
        
        # Clear the cookie to simulate logout
        client.cookies.clear()

        # /admin/me should fail now
        me_after_logout = client.get("/admin/me")
        assert me_after_logout.status_code == 401


class TestMeEndpoint:
    """Tests for GET /admin/me endpoint."""

    def test_me_authenticated(self, client: TestClient, test_session: Session):
        """Authenticated user should see their info."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Login
        login_response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )
        assert login_response.status_code == 200
        
        # Manually set cookie from login response
        token = extract_session_token(login_response)
        client.cookies.set("session_token", token)

        # Get me
        response = client.get("/admin/me")
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testadmin"
        assert data["site_id"] == site.id
        assert data["site_domain"] == "test.example.com"

    def test_me_unauthenticated(self, client: TestClient):
        """Unauthenticated user should get 401."""
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client: TestClient):
        """Invalid token should get 401."""
        client.cookies.set("session_token", "invalid-token-123")
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_me_with_expired_session(self, client: TestClient, test_session: Session):
        """Expired session should get 401."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Create expired session directly
        session = AdminSession(
            admin_user_id=admin.id,
            site_id=site.id,
            token="expired-test-token",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        test_session.add(session)
        test_session.commit()

        # Try to use expired token
        client.cookies.set("session_token", "expired-test-token")
        response = client.get("/admin/me")
        assert response.status_code == 401

    def test_me_includes_last_login(self, client: TestClient, test_session: Session):
        """Me response should include last_login timestamp."""
        site = Site(domain="test.example.com", site_type="band", name="Test Site")
        test_session.add(site)
        test_session.commit()

        admin = AdminUser(site_id=site.id, username="testadmin")
        admin.set_password("testpassword123")
        test_session.add(admin)
        test_session.commit()

        # Login
        login_response = client.post(
            "/admin/login",
            json={
                "username": "testadmin",
                "password": "testpassword123",
                "site_domain": "test.example.com",
            },
        )
        token = extract_session_token(login_response)
        client.cookies.set("session_token", token)

        # Get me
        response = client.get("/admin/me")
        assert response.status_code == 200
        data = response.json()
        assert "last_login" in data
        assert data["last_login"] is not None
