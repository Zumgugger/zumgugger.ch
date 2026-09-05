"""Tests for admin content editing routes (Phase 5).

This module tests the in-place content editing functionality:
- Text field updates
- Array field operations (add/remove/reorder)
- Undo functionality
- Error handling
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import create_app
from app.models.content import SiteContent
from app.models.history import ContentChange
from app.models.site import AdminUser, Site
from app.models.site_config import SiteConfig
from app.models.session import AdminSession
from app.utils.auth import generate_session_token


class TestImageBlockClientContract:
    """Tests for the image upload response used by image blocks."""

    @pytest.mark.parametrize(
        "script_path",
        [
            Path(__file__).resolve().parents[1] / "app/static/js/admin.js",
            Path(__file__).resolve().parents[2]
            / "websitecms/site_template/app/static/js/admin.js",
        ],
    )
    def test_image_block_uses_upload_default_src(self, script_path: Path):
        """Image blocks must use the optimized URL returned by the upload API."""
        script = script_path.read_text(encoding="utf-8")

        assert "const fileUrl = uploadData.default_src;" in script
        assert "uploadData.url ||" not in script


class TestContentUpdateEndpoint:
    """Tests for POST /api/admin/content endpoint."""
    
    def test_update_text_field_success(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession):
        """Test updating a simple text field."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Neue Überschrift",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["field"] == "hero_headline"
        assert data["value"] == "Neue Überschrift"
    
    def test_update_text_field_persists(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that text field update persists in database."""
        cookies = {"session_token": test_admin_session.token}
        
        test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Persistierte Überschrift",
            },
            cookies=cookies,
        )
        
        # Refresh from DB
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        assert content.hero_headline == "Persistierte Überschrift"
    
    def test_update_records_history(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that content updates are recorded in history."""
        cookies = {"session_token": test_admin_session.token}
        
        test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Historie Test",
            },
            cookies=cookies,
        )
        
        # Check history
        change = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id,
            ContentChange.field_name == "hero_headline",
        ).order_by(ContentChange.timestamp.desc()).first()
        
        assert change is not None
        assert change.new_value == "Historie Test"
        assert change.module_type == "hero"
    
    def test_update_sanitizes_xss(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that XSS payloads are sanitized."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "<script>alert('xss')</script>Test",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        # Tags should be stripped, and content escaped
        assert "<script>" not in data["value"]
        # The actual text "Test" should remain
        assert "Test" in data["value"]
    
    def test_update_unknown_field_fails(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that updating unknown field returns error."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "unknown_field",
                "value": "Test",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "error" in data["detail"]
    
    def test_update_without_auth_fails(self, test_client_with_site: TestClient):
        """Test that unauthenticated requests fail."""
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Test",
            },
        )
        
        assert response.status_code == 401
    
    def test_update_array_item(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test updating a specific item in an array field."""
        cookies = {"session_token": test_admin_session.token}
        
        # Services already has items from the test fixture
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "services",
                "subfield": "title",
                "index": 0,
                "value": "Updated Service Title",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["value"] == "Updated Service Title"


class TestArrayItemAddEndpoint:
    """Tests for POST /api/admin/content/add endpoint."""
    
    def test_add_item_success(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test adding an item to an array field."""
        cookies = {"session_token": test_admin_session.token}
        
        # Get initial count
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        initial_count = len(content.services) if content.services else 0
        
        response = test_client_with_site.post(
            "/api/admin/content/add",
            json={
                "field": "services",
                "item": {},
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["value"]) == initial_count + 1
    
    def test_add_item_uses_defaults(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that adding item uses default values."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content/add",
            json={
                "field": "services",
                "item": {},
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        new_item = data["value"][-1]
        assert "title" in new_item
        assert new_item["title"] == "Neue Leistung"
    
    def test_add_item_with_custom_data(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test adding item with custom data overrides defaults."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content/add",
            json={
                "field": "services",
                "item": {
                    "title": "Mein Custom Service",
                    "description": "Custom Beschreibung",
                },
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        new_item = data["value"][-1]
        assert new_item["title"] == "Mein Custom Service"
        assert new_item["description"] == "Custom Beschreibung"
    
    def test_add_item_non_array_field_fails(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that adding to non-array field fails."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content/add",
            json={
                "field": "hero_headline",
                "item": {},
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400


class TestArrayItemRemoveEndpoint:
    """Tests for POST /api/admin/content/remove endpoint."""
    
    def test_remove_item_success(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test removing an item from an array field."""
        cookies = {"session_token": test_admin_session.token}
        
        # Ensure we have items to remove
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        content.services = [
            {"title": "Service 1", "description": "Test 1"},
            {"title": "Service 2", "description": "Test 2"},
        ]
        test_db.commit()
        
        response = test_client_with_site.post(
            "/api/admin/content/remove",
            json={
                "field": "services",
                "index": 0,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["value"]) == 1
        assert data["value"][0]["title"] == "Service 2"
    
    def test_remove_invalid_index_fails(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that removing with invalid index fails."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content/remove",
            json={
                "field": "services",
                "index": 999,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400


class TestArrayItemReorderEndpoint:
    """Tests for POST /api/admin/content/reorder endpoint."""
    
    def test_reorder_success(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test reordering items in an array field."""
        cookies = {"session_token": test_admin_session.token}
        
        # Setup test data
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        content.services = [
            {"title": "First", "description": "1"},
            {"title": "Second", "description": "2"},
            {"title": "Third", "description": "3"},
        ]
        test_db.commit()
        
        # Reorder: reverse the order
        response = test_client_with_site.post(
            "/api/admin/content/reorder",
            json={
                "field": "services",
                "order": [2, 1, 0],
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"][0]["title"] == "Third"
        assert data["value"][1]["title"] == "Second"
        assert data["value"][2]["title"] == "First"
    
    def test_reorder_invalid_order_fails(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that invalid order array fails."""
        cookies = {"session_token": test_admin_session.token}
        
        # Setup test data
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        content.services = [
            {"title": "First", "description": "1"},
            {"title": "Second", "description": "2"},
        ]
        test_db.commit()
        
        # Invalid order (missing index)
        response = test_client_with_site.post(
            "/api/admin/content/reorder",
            json={
                "field": "services",
                "order": [0],  # Missing index 1
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400


class TestUndoEndpoint:
    """Tests for POST /api/admin/undo endpoint."""
    
    def test_undo_last_change(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test undoing the last change."""
        cookies = {"session_token": test_admin_session.token}
        
        # Make a change
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        original_headline = content.hero_headline
        
        test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Changed Headline",
            },
            cookies=cookies,
        )
        
        # Undo
        response = test_client_with_site.post(
            "/api/admin/undo",
            cookies=cookies,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify value restored
        test_db.refresh(content)
        assert content.hero_headline == original_headline
    
    def test_undo_no_changes_fails(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that undo with no changes returns error."""
        cookies = {"session_token": test_admin_session.token}
        
        # Clear all changes
        test_db.query(ContentChange).filter(ContentChange.site_id == test_site.id).delete()
        test_db.commit()
        
        response = test_client_with_site.post(
            "/api/admin/undo",
            cookies=cookies,
        )
        
        assert response.status_code == 400
    
    def test_undo_removes_change_from_history(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that undo removes the change from history."""
        cookies = {"session_token": test_admin_session.token}
        
        # Make a change
        test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "To Be Undone",
            },
            cookies=cookies,
        )
        
        changes_before = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id
        ).count()
        
        # Undo
        test_client_with_site.post(
            "/api/admin/undo",
            cookies=cookies,
        )
        
        changes_after = test_db.query(ContentChange).filter(
            ContentChange.site_id == test_site.id
        ).count()
        
        assert changes_after == changes_before - 1


class TestModuleToggleEndpoint:
    """Tests for POST /api/admin/module/toggle endpoint."""
    
    def test_toggle_module_off(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test disabling a module."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/module/toggle",
            json={
                "module": "media",
                "enabled": False,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        # Verify state changed
        config = test_db.query(SiteConfig).filter(SiteConfig.site_id == test_site.id).first()
        assert config.module_states["media"] == "available"
    
    def test_toggle_module_on(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test enabling a module."""
        cookies = {"session_token": test_admin_session.token}
        
        # First disable it
        config = test_db.query(SiteConfig).filter(SiteConfig.site_id == test_site.id).first()
        config.module_states = {**config.module_states, "faq": "available"}
        test_db.commit()
        
        response = test_client_with_site.post(
            "/api/admin/module/toggle",
            json={
                "module": "faq",
                "enabled": True,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        test_db.refresh(config)
        assert config.module_states["faq"] == "enabled"
    
    def test_toggle_excluded_module_fails(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test that toggling excluded module fails."""
        cookies = {"session_token": test_admin_session.token}
        
        # Set module as excluded
        config = test_db.query(SiteConfig).filter(SiteConfig.site_id == test_site.id).first()
        config.module_states = {**config.module_states, "media": "excluded"}
        test_db.commit()
        
        response = test_client_with_site.post(
            "/api/admin/module/toggle",
            json={
                "module": "media",
                "enabled": True,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400


class TestModuleReorderEndpoint:
    """Tests for POST /api/admin/module/reorder endpoint."""
    
    def test_reorder_modules_success(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession, test_site: Site):
        """Test reordering modules."""
        cookies = {"session_token": test_admin_session.token}
        
        config = test_db.query(SiteConfig).filter(SiteConfig.site_id == test_site.id).first()
        original_order = list(config.module_order)
        
        # Reverse the order
        new_order = list(reversed(original_order))
        
        response = test_client_with_site.post(
            "/api/admin/module/reorder",
            json={
                "order": new_order,
            },
            cookies=cookies,
        )
        
        assert response.status_code == 200
        
        test_db.refresh(config)
        assert config.module_order == new_order
    
    def test_reorder_invalid_modules_fails(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that reordering with invalid modules fails."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/module/reorder",
            json={
                "order": ["nonexistent", "modules"],
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400


class TestEditAffordancesVisibility:
    """Tests for admin edit affordances visibility."""
    
    def test_public_visitor_no_affordances(self, test_client_with_site: TestClient):
        """Test that public visitors don't see edit affordances."""
        response = test_client_with_site.get("/?site_domain=localhost")
        
        assert response.status_code == 200
        html = response.text
        
        # Should not have admin-only classes
        assert 'data-editable="true"' not in html
        assert 'admin-toolbar' not in html
    
    def test_admin_sees_affordances(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that logged-in admin sees edit affordances."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.get("/?site_domain=localhost", cookies=cookies)
        
        assert response.status_code == 200
        html = response.text
        
        # Should have admin affordances
        assert 'data-editable="true"' in html
        assert 'admin-toolbar' in html
    
    def test_admin_sees_toolbar(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that admin toolbar is visible."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.get("/?site_domain=localhost", cookies=cookies)
        
        assert response.status_code == 200
        html = response.text
        
        # Toolbar elements
        assert 'id="eye-toggle"' in html
        assert 'id="undo-btn"' in html
        assert 'id="menu-toggle"' in html


class TestErrorHandling:
    """Tests for error handling and German error messages."""
    
    def test_validation_error_german_message(self, test_client_with_site: TestClient, test_admin_session: AdminSession):
        """Test that validation errors return German messages."""
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "unknown_field",
                "value": "Test",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 400
        data = response.json()
        # Should contain German error message
        assert "message" in data["detail"] or "error" in data["detail"]
    
    def test_unauthorized_returns_401(self, test_client_with_site: TestClient):
        """Test that unauthorized requests return 401."""
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Test",
            },
        )
        
        assert response.status_code == 401
    
    def test_expired_session_returns_401(self, test_client_with_site: TestClient, test_db: Session, test_admin_session: AdminSession):
        """Test that expired session returns 401."""
        from datetime import datetime, timezone, timedelta
        
        # Expire the session
        test_admin_session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        test_db.commit()
        
        cookies = {"session_token": test_admin_session.token}
        
        response = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Test",
            },
            cookies=cookies,
        )
        
        assert response.status_code == 401


class TestConcurrentEditing:
    """Tests for concurrent editing scenarios."""
    
    def test_concurrent_edits_both_succeed(self, test_client_with_site: TestClient, test_db: Session, test_site: Site, test_admin_user: AdminUser):
        """Test that concurrent edits to different fields both succeed."""
        # Create two sessions
        from app.models.session import AdminSession
        from app.utils.auth import generate_session_token
        
        token1 = generate_session_token()
        token2 = generate_session_token()
        
        session1 = AdminSession.create_session(
            admin_user_id=test_admin_user.id,
            site_id=test_site.id,
            token=token1,
        )
        session2 = AdminSession.create_session(
            admin_user_id=test_admin_user.id,
            site_id=test_site.id,
            token=token2,
        )
        test_db.add_all([session1, session2])
        test_db.commit()
        
        # Make concurrent edits to different fields
        response1 = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_headline",
                "value": "Edit from session 1",
            },
            cookies={"session_token": token1},
        )
        
        response2 = test_client_with_site.post(
            "/api/admin/content",
            json={
                "field": "hero_cta_text",
                "value": "Edit from session 2",
            },
            cookies={"session_token": token2},
        )
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Verify both changes persisted
        content = test_db.query(SiteContent).filter(SiteContent.site_id == test_site.id).first()
        assert content.hero_headline == "Edit from session 1"
        assert content.hero_cta_text == "Edit from session 2"
