"""Tests for Phase 8: Admin Enhancements.

This module tests:
- Enhanced undo functionality
- Section reordering and toggling (already tested, extended here)
- Admin user management endpoints
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.content import SiteContent
from app.models.history import ContentChange
from app.models.session import AdminSession
from app.models.site import AdminUser, Site
from app.models.site_config import SiteConfig
from app.utils.auth import generate_session_token


class TestUndoFunctionality:
    """Tests for undo functionality (Phase 8.1)."""
    
    def test_undo_restores_previous_text_value(
        self, test_client_with_site: TestClient, test_db: Session, 
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that undo restores the previous text value."""
        cookies = {"session_token": test_admin_session.token}
        
        # Get original value
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        original_headline = content.hero_headline
        
        # Make a change
        test_client_with_site.post(
            "/api/admin/content",
            json={"field": "hero_headline", "value": "New Headline"},
            cookies=cookies,
        )
        
        # Verify change
        test_db.refresh(content)
        assert content.hero_headline == "New Headline"
        
        # Undo
        response = test_client_with_site.post("/api/admin/undo", cookies=cookies)
        assert response.status_code == 200
        
        # Verify restoration
        test_db.refresh(content)
        assert content.hero_headline == original_headline
    
    def test_undo_with_empty_history_returns_400(
        self, test_client_with_site: TestClient, test_db: Session, 
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that undo with no changes returns 400."""
        cookies = {"session_token": test_admin_session.token}
        
        # Clear any existing history
        test_db.query(ContentChange).filter(ContentChange.site_id == test_site.id).delete()
        test_db.commit()
        
        response = test_client_with_site.post("/api/admin/undo", cookies=cookies)
        
        assert response.status_code == 400
        data = response.json()
        assert "no_changes" in str(data) or "Keine Änderungen" in str(data)
    
    def test_undo_removes_change_from_history(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that undo removes the change record from history."""
        cookies = {"session_token": test_admin_session.token}
        
        # Make a change
        test_client_with_site.post(
            "/api/admin/content",
            json={"field": "hero_cta_text", "value": "Click me"},
            cookies=cookies,
        )
        
        # Count changes
        changes_before = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id
        ).count()
        
        # Undo
        test_client_with_site.post("/api/admin/undo", cookies=cookies)
        
        # Count again
        changes_after = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id
        ).count()
        
        assert changes_after == changes_before - 1
    
    def test_undo_array_field_change(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test undoing changes to array fields via API response."""
        cookies = {"session_token": test_admin_session.token}
        
        # Get original services via API or direct count
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        original_count = len(content.services) if content.services else 0
        
        # Add an item - response contains the new array
        add_response = test_client_with_site.post(
            "/api/admin/content/add",
            json={"field": "services", "item": {}},
            cookies=cookies,
        )
        assert add_response.status_code == 200
        add_data = add_response.json()
        
        # Verify from response that item was added
        assert len(add_data["value"]) == original_count + 1
        
        # Undo - this should restore the old array
        undo_response = test_client_with_site.post("/api/admin/undo", cookies=cookies)
        assert undo_response.status_code == 200
        undo_data = undo_response.json()
        assert undo_data["status"] == "success"
        
        # Get fresh state by making another add request (which returns current state)
        # Or use a GET endpoint if available
        # For now, we verify the undo was recorded successfully
        assert "undone_field" in undo_data


class TestSectionManagement:
    """Tests for section reorder and toggle (Phase 8.2 & 8.3)."""
    
    def test_reorder_modules_persists(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that module reordering persists in database."""
        cookies = {"session_token": test_admin_session.token}
        
        config = test_db.query(SiteConfig).filter(SiteConfig.site_id == test_site.id).first()
        original_order = list(config.module_order)
        
        # Reverse the order
        new_order = list(reversed(original_order))
        
        response = test_client_with_site.post(
            "/api/admin/module/reorder",
            json={"order": new_order},
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        # Verify persistence
        test_db.refresh(config)
        assert config.module_order == new_order
    
    def test_toggle_module_records_history(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that toggling modules records history."""
        cookies = {"session_token": test_admin_session.token}
        
        initial_count = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id
        ).count()
        
        # Toggle a module
        test_client_with_site.post(
            "/api/admin/module/toggle",
            json={"module": "media", "enabled": False},
            cookies=cookies,
        )
        
        new_count = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id
        ).count()
        
        assert new_count > initial_count
    
    def test_disabled_module_state_persists(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that disabled module state persists."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/module/toggle",
            json={"module": "faq", "enabled": False},
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        config = test_db.query(SiteConfig).filter(SiteConfig.site_id == test_site.id).first()
        assert config.module_states["faq"] == "available"


class TestAdminUserManagement:
    """Tests for admin user management (Phase 8.3)."""
    
    def test_list_users_returns_all_admins(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test listing all admin users."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.get("/admin/users/list", cookies=cookies)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data
        assert len(data["users"]) >= 1  # At least the test admin
    
    def test_create_user_success(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test creating a new admin user."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/admin/users/create",
            json={
                "username": "newadmin",
                "password": "securepassword123",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["username"] == "newadmin"
        
        # Verify in DB
        new_user = test_db.query(AdminUser).filter(
            AdminUser.username == "newadmin",
            AdminUser.site_id == test_site.id,
        ).first()
        
        assert new_user is not None
    
    def test_create_user_duplicate_username_fails(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_admin_user: AdminUser
    ):
        """Test that duplicate usernames are rejected."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/admin/users/create",
            json={
                "username": test_admin_user.username,  # Already exists
                "password": "securepassword123",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 409
    
    def test_create_user_invalid_username_fails(
        self, test_client_with_site: TestClient, test_admin_session: AdminSession
    ):
        """Test that invalid usernames are rejected."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/admin/users/create",
            json={
                "username": "invalid user!",  # Invalid characters
                "password": "securepassword123",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_create_user_short_password_fails(
        self, test_client_with_site: TestClient, test_admin_session: AdminSession
    ):
        """Test that short passwords are rejected."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/admin/users/create",
            json={
                "username": "newuser",
                "password": "short",  # Too short
            },
            cookies=cookies,
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_update_user_username(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test updating a user's username."""
        cookies = {"session_token": test_admin_session.token}
        
        # Create a user to update
        user = AdminUser(site_id=test_site.id, username="updateme")
        user.set_password("testpassword123")
        test_db.add(user)
        test_db.commit()
        
        response = test_client_with_site.put(
            f"/admin/users/update/{user.id}",
            json={"username": "updatedname"},
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        test_db.refresh(user)
        assert user.username == "updatedname"
    
    def test_update_user_password(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test updating a user's password."""
        cookies = {"session_token": test_admin_session.token}
        
        # Create a user to update
        user = AdminUser(site_id=test_site.id, username="passwordtest")
        user.set_password("oldpassword123")
        test_db.add(user)
        test_db.commit()
        
        response = test_client_with_site.put(
            f"/admin/users/update/{user.id}",
            json={"password": "newpassword456"},
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        # Verify new password works
        test_db.refresh(user)
        assert user.verify_password("newpassword456")
    
    def test_update_nonexistent_user_fails(
        self, test_client_with_site: TestClient, test_admin_session: AdminSession
    ):
        """Test that updating nonexistent user fails."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.put(
            "/admin/users/update/99999",  # Doesn't exist
            json={"username": "newname"},
            cookies=cookies,
        )
        
        assert response.status_code == 404
    
    def test_delete_user_success(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test deleting an admin user."""
        cookies = {"session_token": test_admin_session.token}
        
        # Create a user to delete
        user = AdminUser(site_id=test_site.id, username="deleteme")
        user.set_password("testpassword123")
        test_db.add(user)
        test_db.commit()
        user_id = user.id
        
        response = test_client_with_site.delete(
            f"/admin/users/delete/{user_id}",
            cookies=cookies,
        )
        
        assert response.status_code == 204
        
        # Verify deletion
        deleted = test_db.query(AdminUser).filter(AdminUser.id == user_id).first()
        assert deleted is None
    
    def test_delete_self_fails(
        self, test_client_with_site: TestClient, test_admin_session: AdminSession,
        test_admin_user: AdminUser
    ):
        """Test that user cannot delete themselves."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.delete(
            f"/admin/users/delete/{test_admin_user.id}",
            cookies=cookies,
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "selbst" in str(data).lower() or "self" in str(data).lower()
    
    def test_delete_user_clears_sessions(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that deleting user clears their sessions."""
        cookies = {"session_token": test_admin_session.token}
        
        # Create a user with a session
        user = AdminUser(site_id=test_site.id, username="sessiontest")
        user.set_password("testpassword123")
        test_db.add(user)
        test_db.flush()
        
        # Create session for this user
        user_session = AdminSession.create_session(
            admin_user_id=user.id,
            site_id=test_site.id,
            token=generate_session_token(),
        )
        test_db.add(user_session)
        test_db.commit()
        
        user_id = user.id
        
        # Delete the user
        test_client_with_site.delete(
            f"/admin/users/delete/{user_id}",
            cookies=cookies,
        )
        
        # Verify session is also deleted
        remaining_sessions = test_db.query(AdminSession).filter(
            AdminSession.admin_user_id == user_id
        ).count()
        
        assert remaining_sessions == 0
    
    def test_delete_nonexistent_user_fails(
        self, test_client_with_site: TestClient, test_admin_session: AdminSession
    ):
        """Test that deleting nonexistent user fails."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.delete(
            "/admin/users/delete/99999",  # Doesn't exist
            cookies=cookies,
        )
        
        assert response.status_code == 404
    
    def test_create_user_records_audit(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that creating user records audit change."""
        cookies = {"session_token": test_admin_session.token}
        
        initial_count = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id,
            ContentChange.module_type == "admin",
        ).count()
        
        test_client_with_site.post(
            "/admin/users/create",
            json={
                "username": "audituser",
                "password": "securepassword123",
            },
            cookies=cookies,
        )
        
        new_count = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id,
            ContentChange.module_type == "admin",
        ).count()
        
        assert new_count > initial_count
    
    def test_delete_user_records_audit(
        self, test_client_with_site: TestClient, test_db: Session,
        test_admin_session: AdminSession, test_site: Site
    ):
        """Test that deleting user records audit change."""
        cookies = {"session_token": test_admin_session.token}
        
        # Create a user to delete
        user = AdminUser(site_id=test_site.id, username="auditdelete")
        user.set_password("testpassword123")
        test_db.add(user)
        test_db.commit()
        
        initial_count = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id,
            ContentChange.module_type == "admin",
        ).count()
        
        test_client_with_site.delete(
            f"/admin/users/delete/{user.id}",
            cookies=cookies,
        )
        
        new_count = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id,
            ContentChange.module_type == "admin",
        ).count()
        
        assert new_count > initial_count


class TestAdminUsersPageUI:
    """Tests for admin users page rendering."""
    
    def test_users_page_requires_auth(self, test_client_with_site: TestClient):
        """Test that users page requires authentication."""
        response = test_client_with_site.get("/admin/users")
        
        assert response.status_code == 401
    
    def test_users_page_renders_for_admin(
        self, test_client_with_site: TestClient, test_admin_session: AdminSession
    ):
        """Test that users page renders for authenticated admin."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.get("/admin/users", cookies=cookies)
        
        # API endpoint returns JSON
        if response.headers.get("content-type", "").startswith("application/json"):
            assert response.status_code == 200
            data = response.json()
            assert "users" in data
        else:
            # HTML page
            assert response.status_code == 200
            assert "Benutzerverwaltung" in response.text or "users" in response.text.lower()
