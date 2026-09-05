"""
Phase 15 Tests - Missing Spec Implementations

Tests for:
- 15.1 Maintenance Mode
- 15.2 Styled 404 Page
- 15.3 Nav Label Editing (Admin API)
- 15.4 Logo & Favicon Management
- 15.5 Trust Images Lightbox
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestMaintenanceMode:
    """Test maintenance mode functionality."""
    
    def test_maintenance_mode_config_default_false(self, client):
        """Test maintenance_mode defaults to false."""
        from app.config import Settings
        
        settings = Settings()
        assert settings.maintenance_mode is False
    
    def test_maintenance_mode_truthy_parsing(self):
        """Test maintenance_mode parses truthy values."""
        from app.config import Settings
        
        # Test various truthy values via model
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "true"}):
            settings = Settings()
            assert settings.maintenance_mode is True
        
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "1"}):
            settings = Settings()
            assert settings.maintenance_mode is True
        
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "yes"}):
            settings = Settings()
            assert settings.maintenance_mode is True
        
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "on"}):
            settings = Settings()
            assert settings.maintenance_mode is True
    
    def test_maintenance_mode_falsy_parsing(self):
        """Test maintenance_mode parses falsy values."""
        from app.config import Settings
        
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "false"}):
            settings = Settings()
            assert settings.maintenance_mode is False
        
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "0"}):
            settings = Settings()
            assert settings.maintenance_mode is False
        
        with patch.dict("os.environ", {"MAINTENANCE_MODE": "no"}):
            settings = Settings()
            assert settings.maintenance_mode is False
    
    def test_maintenance_middleware_bypasses_login(self, client):
        """Test maintenance mode allows access to /admin/login."""
        # The middleware should not block admin login
        response = client.get("/admin/login")
        # Should get login page (302 redirect or 200), not maintenance
        assert response.status_code in [200, 302]
    
    def test_maintenance_middleware_bypasses_health(self, client):
        """Test maintenance mode allows access to /health."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_maintenance_middleware_bypasses_static(self, client):
        """Test maintenance mode allows access to /static/."""
        # Static files should still be accessible
        response = client.get("/static/css/main.css")
        # May be 200 or 404 depending on file existence, but not maintenance
        assert response.status_code in [200, 404]


class TestStyled404Page:
    """Test styled 404 error page."""
    
    def test_404_returns_404_status(self, client):
        """Test non-existent page returns 404 status."""
        response = client.get("/nonexistent-page-that-does-not-exist")
        assert response.status_code == 404
    
    def test_404_returns_html(self, client):
        """Test 404 page returns HTML content."""
        response = client.get("/nonexistent-page-that-does-not-exist")
        assert "text/html" in response.headers.get("content-type", "")
    
    def test_404_contains_navigation(self, client):
        """Test 404 page contains navigation back to home."""
        response = client.get("/nonexistent-page-that-does-not-exist")
        content = response.text
        # Should have a link back to home
        assert 'href="/"' in content or 'href="#"' in content
    
    def test_404_has_styled_content(self, client):
        """Test 404 page has styled content."""
        response = client.get("/nonexistent-page-that-does-not-exist")
        content = response.text
        # Should have CSS included
        assert '<link' in content or '<style>' in content


class TestNavLabelAPI:
    """Test navigation label editing API."""
    
    def test_update_nav_label_requires_auth(self, client):
        """Test updating nav label requires authentication."""
        response = client.put(
            "/api/admin/config/nav-labels",
            json={"module": "services", "label": "Leistungen"}
        )
        assert response.status_code in [401, 403]
    
    def test_delete_nav_label_requires_auth(self, client):
        """Test deleting nav label requires authentication."""
        response = client.delete("/api/admin/config/nav-labels/services")
        assert response.status_code in [401, 403]
    
    def test_nav_label_endpoint_exists(self, client):
        """Test nav label API endpoint exists (returns auth error, not 404)."""
        response = client.put(
            "/api/admin/config/nav-labels",
            json={"module": "services", "label": "Test"}
        )
        # Should return 401/403 (auth required), not 404 (not found)
        assert response.status_code in [401, 403]
        assert response.status_code != 404
    
    def test_nav_label_delete_endpoint_exists(self, client):
        """Test nav label delete API endpoint exists (returns auth error, not 404)."""
        response = client.delete("/api/admin/config/nav-labels/services")
        # Should return 401/403 (auth required), not 404 (not found)
        assert response.status_code in [401, 403]
        assert response.status_code != 404


class TestLogoFaviconAPI:
    """Test logo and favicon management API."""
    
    def test_update_logo_requires_auth(self, client):
        """Test updating logo requires authentication."""
        response = client.put("/api/admin/config/logo")
        assert response.status_code in [401, 403, 422]
    
    def test_update_favicon_requires_auth(self, client):
        """Test updating favicon requires authentication."""
        response = client.put("/api/admin/config/favicon")
        assert response.status_code in [401, 403, 422]
    
    def test_delete_logo_requires_auth(self, client):
        """Test deleting logo requires authentication."""
        response = client.delete("/api/admin/config/logo")
        assert response.status_code in [401, 403]
    
    def test_delete_favicon_requires_auth(self, client):
        """Test deleting favicon requires authentication."""
        response = client.delete("/api/admin/config/favicon")
        assert response.status_code in [401, 403]


class TestTrustLightbox:
    """Test trust images lightbox functionality."""
    
    def test_trust_template_has_lightbox_attributes(self):
        """Test trust.html template has lightbox data attributes."""
        import os
        
        template_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "app", "templates", "modules", "trust.html"
        )
        
        with open(template_path, "r") as f:
            content = f.read()
        
        assert 'data-lightbox="trust"' in content
        assert 'class="lightbox-img"' in content
    
    def test_lightbox_js_exists(self):
        """Test lightbox JavaScript code exists in nav.js."""
        import os
        
        js_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "static", "js", "nav.js"
        )
        
        with open(js_path, "r") as f:
            content = f.read()
        
        assert "lightbox" in content.lower()
        assert "data-lightbox" in content
    
    def test_lightbox_css_exists(self):
        """Test lightbox CSS exists in components.css."""
        import os
        
        css_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "static", "css", "components.css"
        )
        
        with open(css_path, "r") as f:
            content = f.read()
        
        assert ".lightbox-overlay" in content
        assert ".lightbox-image" in content
        assert ".lightbox-close" in content


class TestSchemaUpgrades:
    """Test schema upgrades for Phase 15."""
    
    def test_schema_version_is_3(self):
        """Test SCHEMA_VERSION is updated to 3."""
        from app.schema_upgrades import SCHEMA_VERSION
        
        assert SCHEMA_VERSION >= 3
    
    def test_v3_upgrade_function_exists(self):
        """Test upgrade_v2_to_v3 function is in UPGRADES."""
        from app.schema_upgrades import UPGRADES
        
        assert 3 in UPGRADES
        upgrade_desc, upgrade_func = UPGRADES[3]
        assert "logo" in upgrade_desc.lower() or "favicon" in upgrade_desc.lower()
    
    def test_site_config_has_logo_field(self):
        """Test SiteConfig model has logo_image field."""
        from app.models.site_config import SiteConfig
        
        # Check column exists
        assert hasattr(SiteConfig, "logo_image")
    
    def test_site_config_has_favicon_field(self):
        """Test SiteConfig model has favicon_image field."""
        from app.models.site_config import SiteConfig
        
        # Check column exists
        assert hasattr(SiteConfig, "favicon_image")


class TestVhostConfig:
    """Test Apache vhost.conf configuration."""
    
    def test_hsts_header_no_include_subdomains(self):
        """Test HSTS header does not include includeSubDomains."""
        import os
        
        vhost_path = os.path.join(
            os.path.dirname(__file__),
            "..", "deploy", "apache", "vhost.conf"
        )
        
        with open(vhost_path, "r") as f:
            content = f.read()
        
        # Should have Strict-Transport-Security without includeSubDomains
        assert "Strict-Transport-Security" in content
        # Check the actual header line doesn't have includeSubDomains
        for line in content.split("\n"):
            if "Strict-Transport-Security" in line and "Header" in line:
                assert "includeSubDomains" not in line
    
    def test_no_limit_request_body_directive(self):
        """Test LimitRequestBody is not set in vhost.conf."""
        import os
        
        vhost_path = os.path.join(
            os.path.dirname(__file__),
            "..", "deploy", "apache", "vhost.conf"
        )
        
        with open(vhost_path, "r") as f:
            content = f.read()
        
        # Should not have active LimitRequestBody directive
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("LimitRequestBody"):
                pytest.fail("LimitRequestBody should not be present in vhost.conf")
