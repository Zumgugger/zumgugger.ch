"""Tests for Phase 10: Optional Features (Analytics & CAPTCHA).

This module tests:
- Plausible analytics integration
- CAPTCHA integration in contact form
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.models.site import Site
from app.models.content import SiteContent
from app.models.site_config import SiteConfig

# Set test environment
os.environ["DATABASE_URL"] = "sqlite:///test_site.db"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key"


@pytest.fixture
def site_with_content(test_session: Session) -> Site:
    """Create a test site with content and config."""
    # Create site
    site = Site(
        domain="test-analytics.example.com",
        site_type="band",
        name="Test Analytics Site",
    )
    test_session.add(site)
    test_session.flush()
    
    # Create content
    content = SiteContent(
        site_id=site.id,
        hero_headline="Welcome to Test Site",
        hero_cta_text="Contact Us",
        hero_cta_target="contact",
    )
    test_session.add(content)
    
    # Create config with contact module enabled
    config = SiteConfig(
        site_id=site.id,
        theme_name="clean",
        module_states={
            "hero": "enabled",
            "contact": "enabled",
            "footer": "enabled",
        },
        module_order=["hero", "contact", "footer"],
        css_variables={},
        nav_labels={},
    )
    test_session.add(config)
    
    test_session.commit()
    test_session.refresh(site)
    
    return site


class TestAnalyticsConfig:
    """Test analytics configuration settings."""
    
    def test_analytics_disabled_by_default(self):
        """Test that analytics is disabled by default."""
        # Clear cache to get fresh settings
        from app.config import get_settings
        get_settings.cache_clear()
        
        # Ensure env vars are not set
        with patch.dict(os.environ, {}, clear=False):
            # Remove analytics-specific env vars if present
            for key in ['ANALYTICS_ENABLED', 'PLAUSIBLE_DOMAIN', 'PLAUSIBLE_SCRIPT_SRC']:
                os.environ.pop(key, None)
            
            get_settings.cache_clear()
            settings = get_settings()
            
            assert settings.analytics_enabled is False
            assert settings.plausible_domain == ""
            assert settings.plausible_script_src == "https://plausible.io/js/script.js"
    
    def test_analytics_enabled_with_domain(self):
        """Test that analytics can be enabled with domain."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {
            'ANALYTICS_ENABLED': 'true',
            'PLAUSIBLE_DOMAIN': 'example.com',
        }):
            get_settings.cache_clear()
            settings = get_settings()
            
            assert settings.analytics_enabled is True
            assert settings.plausible_domain == "example.com"
    
    def test_custom_plausible_script_src(self):
        """Test that custom Plausible script src can be set."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {
            'ANALYTICS_ENABLED': 'true',
            'PLAUSIBLE_DOMAIN': 'example.com',
            'PLAUSIBLE_SCRIPT_SRC': 'https://my-plausible.example.com/js/script.js',
        }):
            get_settings.cache_clear()
            settings = get_settings()
            
            assert settings.plausible_script_src == "https://my-plausible.example.com/js/script.js"


class TestAnalyticsInTemplate:
    """Test analytics script injection in template."""
    
    def test_analytics_script_included_when_enabled(self, client, site_with_content):
        """Test that Plausible script is included when analytics is enabled."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {
            'ANALYTICS_ENABLED': 'true',
            'PLAUSIBLE_DOMAIN': 'testsite.com',
        }):
            get_settings.cache_clear()
            
            response = client.get("/", params={"site_domain": site_with_content.domain})
            assert response.status_code == 200
            
            html = response.text
            # Check for Plausible script tag
            assert 'data-domain="testsite.com"' in html
            assert 'plausible.io/js/script.js' in html
    
    def test_analytics_script_not_included_when_disabled(self, client, site_with_content):
        """Test that Plausible script is NOT included when analytics is disabled."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {
            'ANALYTICS_ENABLED': 'false',
            'PLAUSIBLE_DOMAIN': 'testsite.com',
        }):
            get_settings.cache_clear()
            
            response = client.get("/", params={"site_domain": site_with_content.domain})
            assert response.status_code == 200
            
            html = response.text
            # Check that Plausible script is not present
            assert 'data-domain=' not in html
            assert 'plausible.io' not in html
    
    def test_analytics_script_not_included_without_domain(self, client, site_with_content):
        """Test that Plausible script is NOT included when domain is empty."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {
            'ANALYTICS_ENABLED': 'true',
            'PLAUSIBLE_DOMAIN': '',
        }):
            get_settings.cache_clear()
            
            response = client.get("/", params={"site_domain": site_with_content.domain})
            assert response.status_code == 200
            
            html = response.text
            # Check that Plausible script is not present when domain is empty
            assert 'data-domain=""' not in html or 'plausible.io' not in html
    
    def test_custom_script_src_used(self, client, site_with_content):
        """Test that custom Plausible script URL is used."""
        from app.config import get_settings
        
        custom_src = "https://stats.mysite.com/js/script.js"
        
        with patch.dict(os.environ, {
            'ANALYTICS_ENABLED': 'true',
            'PLAUSIBLE_DOMAIN': 'testsite.com',
            'PLAUSIBLE_SCRIPT_SRC': custom_src,
        }):
            get_settings.cache_clear()
            
            response = client.get("/", params={"site_domain": site_with_content.domain})
            assert response.status_code == 200
            
            html = response.text
            # Check for custom script source
            assert custom_src in html


class TestCaptchaConfig:
    """Test CAPTCHA configuration settings."""
    
    def test_captcha_disabled_by_default(self):
        """Test that CAPTCHA is disabled by default."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {}, clear=False):
            # Remove captcha-specific env vars if present
            for key in ['CAPTCHA_ENABLED', 'TURNSTILE_SITE_KEY', 'TURNSTILE_SECRET_KEY']:
                os.environ.pop(key, None)
            
            get_settings.cache_clear()
            settings = get_settings()
            
            assert settings.captcha_enabled is False
            assert settings.turnstile_site_key == ""
            assert settings.turnstile_secret_key == ""
    
    def test_captcha_enabled_with_keys(self):
        """Test that CAPTCHA can be enabled with proper keys."""
        from app.config import get_settings
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'true',
            'TURNSTILE_SITE_KEY': 'test-site-key',
            'TURNSTILE_SECRET_KEY': 'test-secret-key',
        }):
            get_settings.cache_clear()
            settings = get_settings()
            
            assert settings.captcha_enabled is True
            assert settings.turnstile_site_key == "test-site-key"
            assert settings.turnstile_secret_key == "test-secret-key"


class TestCaptchaConfigEndpoint:
    """Test CAPTCHA configuration endpoint."""
    
    def test_captcha_config_when_disabled(self, client):
        """Test /api/contact/config returns disabled when CAPTCHA is off."""
        from app.config import get_settings
        from app.utils.captcha import reset_captcha_verifier, configure_captcha_verifier
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'false',
        }):
            get_settings.cache_clear()
            reset_captcha_verifier()
            configure_captcha_verifier("", "", enabled=False)
            
            response = client.get("/api/contact/config")
            assert response.status_code == 200
            
            data = response.json()
            assert data["captcha_enabled"] is False
            assert data.get("captcha_site_key") is None
    
    def test_captcha_config_when_enabled(self, client):
        """Test /api/contact/config returns site key when CAPTCHA is enabled."""
        from app.config import get_settings
        from app.utils.captcha import reset_captcha_verifier, configure_captcha_verifier
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'true',
            'TURNSTILE_SITE_KEY': 'my-site-key',
            'TURNSTILE_SECRET_KEY': 'my-secret-key',
        }):
            get_settings.cache_clear()
            reset_captcha_verifier()
            configure_captcha_verifier("my-secret-key", "my-site-key", enabled=True)
            
            response = client.get("/api/contact/config")
            assert response.status_code == 200
            
            data = response.json()
            assert data["captcha_enabled"] is True
            assert data["captcha_site_key"] == "my-site-key"


class TestCaptchaVerification:
    """Test CAPTCHA verification in contact form submission."""
    
    def test_form_submits_without_captcha_when_disabled(self, client, site_with_content):
        """Test form submits successfully when CAPTCHA is disabled."""
        from app.config import get_settings
        from app.utils.captcha import reset_captcha_verifier, configure_captcha_verifier
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'false',
        }):
            get_settings.cache_clear()
            reset_captcha_verifier()
            configure_captcha_verifier("", "", enabled=False)
            
            response = client.post(
                "/api/contact/submit",
                params={"site_domain": site_with_content.domain},
                data={
                    "contact": "test@example.com",
                    "message": "Test message",
                    "website": "",  # honeypot
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "submitted"
    
    @patch('app.utils.captcha.httpx.Client')
    def test_form_validates_captcha_when_enabled(self, mock_httpx, client, site_with_content):
        """Test form validates CAPTCHA when enabled."""
        from app.config import get_settings
        from app.utils.captcha import reset_captcha_verifier, configure_captcha_verifier
        
        # Mock successful CAPTCHA verification
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx.return_value.__enter__.return_value = mock_client_instance
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'true',
            'TURNSTILE_SITE_KEY': 'test-site-key',
            'TURNSTILE_SECRET_KEY': 'test-secret-key',
        }):
            get_settings.cache_clear()
            reset_captcha_verifier()
            configure_captcha_verifier("test-secret-key", "test-site-key", enabled=True)
            
            response = client.post(
                "/api/contact/submit",
                params={"site_domain": site_with_content.domain},
                data={
                    "contact": "test@example.com",
                    "message": "Test message with CAPTCHA",
                    "website": "",
                    "cf-turnstile-response": "valid-token",
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "submitted"
    
    def test_form_rejects_missing_captcha_when_enabled(self, client, site_with_content):
        """Test form rejects submission when CAPTCHA is enabled but token missing."""
        from app.config import get_settings
        from app.utils.captcha import reset_captcha_verifier, configure_captcha_verifier
        from app.utils.spam import reset_spam_checker
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'true',
            'TURNSTILE_SITE_KEY': 'test-site-key',
            'TURNSTILE_SECRET_KEY': 'test-secret-key',
        }):
            get_settings.cache_clear()
            reset_captcha_verifier()
            reset_spam_checker()  # Reset spam checker to avoid rate limit issues
            configure_captcha_verifier("test-secret-key", "test-site-key", enabled=True)
            
            response = client.post(
                "/api/contact/submit",
                params={"site_domain": site_with_content.domain},
                data={
                    "contact": "nocaptcha@example.com",
                    "message": "Test message without CAPTCHA unique " + str(hash(site_with_content.domain)),
                    "website": "",
                    # No cf-turnstile-response
                },
            )
            
            # Should return 400 for CAPTCHA failure
            assert response.status_code == 400
            data = response.json()
            assert "CAPTCHA" in data.get("message", "")
    
    @patch('app.utils.captcha.httpx.Client')
    def test_form_rejects_invalid_captcha_token(self, mock_httpx, client, site_with_content):
        """Test form rejects submission with invalid CAPTCHA token."""
        from app.config import get_settings
        from app.utils.captcha import reset_captcha_verifier, configure_captcha_verifier
        from app.utils.spam import reset_spam_checker
        
        # Mock failed CAPTCHA verification
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": False, "error-codes": ["invalid-input-response"]}
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_httpx.return_value.__enter__.return_value = mock_client_instance
        
        with patch.dict(os.environ, {
            'CAPTCHA_ENABLED': 'true',
            'TURNSTILE_SITE_KEY': 'test-site-key',
            'TURNSTILE_SECRET_KEY': 'test-secret-key',
        }):
            get_settings.cache_clear()
            reset_captcha_verifier()
            reset_spam_checker()  # Reset spam checker to avoid rate limit issues
            configure_captcha_verifier("test-secret-key", "test-site-key", enabled=True)
            
            response = client.post(
                "/api/contact/submit",
                params={"site_domain": site_with_content.domain},
                data={
                    "contact": "invalidcaptcha@example.com",
                    "message": "Test message with invalid CAPTCHA unique " + str(hash(site_with_content.domain)),
                    "website": "",
                    "cf-turnstile-response": "invalid-token",
                },
            )
            
            # Should return 400 for CAPTCHA failure
            assert response.status_code == 400
            data = response.json()
            assert "CAPTCHA" in data.get("message", "")


class TestCaptchaInContactTemplate:
    """Test CAPTCHA rendering in contact form template."""
    
    def test_contact_form_has_captcha_container(self, client, site_with_content):
        """Test that contact form has a CAPTCHA container element."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        assert response.status_code == 200
        
        html = response.text
        # Check for captcha container
        assert 'id="captcha-container"' in html
    
    def test_contact_form_has_honeypot(self, client, site_with_content):
        """Test that contact form has honeypot field."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        assert response.status_code == 200
        
        html = response.text
        # Check for honeypot field
        assert 'name="website"' in html
        assert 'hp-field' in html


class TestEnvExampleComplete:
    """Test that .env.example contains all required settings."""
    
    def test_env_example_has_analytics_settings(self):
        """Test that .env.example includes analytics settings."""
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".env.example"
        )
        
        with open(env_path, "r") as f:
            content = f.read()
        
        assert "ANALYTICS_ENABLED" in content
        assert "PLAUSIBLE_DOMAIN" in content
        assert "PLAUSIBLE_SCRIPT_SRC" in content
    
    def test_env_example_has_captcha_settings(self):
        """Test that .env.example includes CAPTCHA settings."""
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".env.example"
        )
        
        with open(env_path, "r") as f:
            content = f.read()
        
        assert "CAPTCHA_ENABLED" in content
        assert "TURNSTILE_SITE_KEY" in content
        assert "TURNSTILE_SECRET_KEY" in content
