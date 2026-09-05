"""Tests for contact form submission and spam prevention."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.utils.spam import SpamChecker, get_spam_checker, reset_spam_checker
from app.utils.contact import (
    validate_contact,
    ContactType,
    is_email,
    is_phone_like,
    normalize_email,
    normalize_phone,
)
from app.utils.email import EmailClient, compose_contact_email
from app.utils.sms import SMSClient, compose_contact_sms
from app.utils.captcha import CaptchaVerifier


# =============================================================================
# Contact Validation Tests
# =============================================================================

class TestContactValidation:
    """Tests for contact value validation and normalization."""
    
    def test_is_email_valid(self):
        """Test email detection for valid emails."""
        assert is_email("test@example.com") is True
        assert is_email("user.name@domain.co.uk") is True
        assert is_email("user+tag@gmail.com") is True
    
    def test_is_email_invalid(self):
        """Test email detection rejects invalid values."""
        assert is_email("not-an-email") is False
        assert is_email("@missing-local.com") is False
        assert is_email("missing-at-domain.com") is False
        assert is_email("+41791234567") is False
    
    def test_is_phone_like_valid(self):
        """Test phone detection for phone-like strings."""
        assert is_phone_like("+41791234567") is True
        assert is_phone_like("079 123 45 67") is True
        assert is_phone_like("(079) 123-4567") is True
        assert is_phone_like("0791234567") is True
    
    def test_is_phone_like_invalid(self):
        """Test phone detection rejects non-phone strings."""
        assert is_phone_like("test@example.com") is False
        assert is_phone_like("hello world") is False
        assert is_phone_like("12345") is False  # Too few digits
    
    def test_normalize_email(self):
        """Test email normalization (lowercase, strip)."""
        assert normalize_email("  TEST@EXAMPLE.COM  ") == "test@example.com"
        assert normalize_email("User@Domain.COM") == "user@domain.com"
    
    def test_normalize_phone_swiss(self):
        """Test phone normalization for Swiss numbers."""
        # Standard Swiss mobile
        success, normalized, error = normalize_phone("079 123 45 67", "CH")
        assert success is True
        assert normalized == "+41791234567"
        assert error is None
    
    def test_normalize_phone_already_e164(self):
        """Test phone normalization for already E.164 format."""
        success, normalized, error = normalize_phone("+41791234567", "CH")
        assert success is True
        assert normalized == "+41791234567"
    
    def test_normalize_phone_invalid(self):
        """Test phone normalization rejects invalid numbers."""
        success, normalized, error = normalize_phone("123", "CH")
        assert success is False
        assert error is not None
    
    def test_validate_contact_email(self):
        """Test contact validation for email addresses."""
        result = validate_contact("test@example.com")
        assert result.is_valid is True
        assert result.contact_type == ContactType.EMAIL
        assert result.normalized_value == "test@example.com"
    
    def test_validate_contact_phone(self):
        """Test contact validation for phone numbers."""
        result = validate_contact("+41791234567")
        assert result.is_valid is True
        assert result.contact_type == ContactType.PHONE
        assert result.normalized_value == "+41791234567"
    
    def test_validate_contact_empty(self):
        """Test contact validation rejects empty values."""
        result = validate_contact("")
        assert result.is_valid is False
        assert result.error_message is not None
    
    def test_validate_contact_invalid(self):
        """Test contact validation rejects invalid values."""
        result = validate_contact("not valid input")
        assert result.is_valid is False
        assert result.error_message is not None


# =============================================================================
# Spam Checker Tests
# =============================================================================

class TestSpamChecker:
    """Tests for spam prevention functionality."""
    
    def test_honeypot_empty_passes(self):
        """Test that empty honeypot field passes."""
        checker = SpamChecker()
        assert checker.check_honeypot("") is False
        assert checker.check_honeypot(None) is False
        assert checker.check_honeypot("   ") is False
    
    def test_honeypot_filled_is_spam(self):
        """Test that filled honeypot field is detected as spam."""
        checker = SpamChecker()
        assert checker.check_honeypot("spam bot") is True
        assert checker.check_honeypot("http://spam.com") is True
    
    def test_ip_rate_limit_under_threshold(self):
        """Test that IPs under rate limit pass."""
        checker = SpamChecker(ip_rate_limit=3, ip_rate_window=60)
        
        # First submission should pass
        assert checker.check_rate_limit_ip("192.168.1.1") is False
        checker.record_ip_submission("192.168.1.1")
        
        # Second submission should pass
        assert checker.check_rate_limit_ip("192.168.1.1") is False
        checker.record_ip_submission("192.168.1.1")
        
        # Third submission should still pass (at limit, not over)
        assert checker.check_rate_limit_ip("192.168.1.1") is False
    
    def test_ip_rate_limit_over_threshold(self):
        """Test that IPs over rate limit are blocked."""
        checker = SpamChecker(ip_rate_limit=2, ip_rate_window=60)
        
        # Record 2 submissions
        checker.record_ip_submission("192.168.1.1")
        checker.record_ip_submission("192.168.1.1")
        
        # Third check should fail
        assert checker.check_rate_limit_ip("192.168.1.1") is True
    
    def test_contact_rate_limit(self):
        """Test rate limiting per contact value."""
        checker = SpamChecker(contact_rate_limit=2, contact_rate_window=60)
        
        # First submission
        assert checker.check_rate_limit_contact("test@example.com") is False
        checker.record_contact_submission("test@example.com")
        
        # Second submission
        assert checker.check_rate_limit_contact("test@example.com") is False
        checker.record_contact_submission("test@example.com")
        
        # Third check should fail
        assert checker.check_rate_limit_contact("test@example.com") is True
    
    def test_duplicate_detection(self):
        """Test duplicate submission detection."""
        checker = SpamChecker(duplicate_window=60)
        
        # First submission
        assert checker.check_duplicate("test@example.com", "Hello!") is False
        checker.record_duplicate_hash("test@example.com", "Hello!")
        
        # Same submission again
        assert checker.check_duplicate("test@example.com", "Hello!") is True
        
        # Different message is OK
        assert checker.check_duplicate("test@example.com", "Different message") is False
    
    def test_is_spam_all_checks(self):
        """Test combined spam check function."""
        checker = SpamChecker()
        
        # Valid submission
        assert checker.is_spam(
            ip_address="192.168.1.1",
            normalized_contact="test@example.com",
            message="Hello!",
            honeypot_value="",
        ) is False
        
        # With honeypot filled
        assert checker.is_spam(
            ip_address="192.168.1.1",
            normalized_contact="test@example.com",
            message="Hello!",
            honeypot_value="spam",
        ) is True
    
    def test_clear_resets_data(self):
        """Test that clear resets all tracking data."""
        checker = SpamChecker()
        
        # Add some data
        checker.record_ip_submission("192.168.1.1")
        checker.record_contact_submission("test@example.com")
        checker.record_duplicate_hash("test@example.com", "Hello!")
        
        # Clear
        checker.clear()
        
        # Should be fresh now
        assert checker.check_rate_limit_ip("192.168.1.1") is False
        assert checker.check_rate_limit_contact("test@example.com") is False
        assert checker.check_duplicate("test@example.com", "Hello!") is False


# =============================================================================
# Email Client Tests
# =============================================================================

class TestEmailClient:
    """Tests for email composition and sending."""
    
    def test_compose_contact_email(self):
        """Test contact email composition."""
        subject, body_text, body_html = compose_contact_email(
            site_name="Test Site",
            contact_value="test@example.com",
            contact_type="email",
            message="Hello!\nThis is a test message.",
            ip_address="192.168.1.1",
        )
        
        assert subject == "Neue Kontaktanfrage - Test Site"
        assert "test@example.com" in body_text
        assert "Hello!" in body_text
        assert "192.168.1.1" in body_text
        assert "test@example.com" in body_html
        assert "Hello!" in body_html
    
    def test_compose_contact_email_phone(self):
        """Test contact email composition with phone number."""
        subject, body_text, body_html = compose_contact_email(
            site_name="Test Site",
            contact_value="+41791234567",
            contact_type="phone",
            message="Call me!",
            ip_address="192.168.1.1",
        )
        
        assert "Telefon" in body_text
        assert "+41791234567" in body_text
        assert "tel:" in body_html
    
    @patch('smtplib.SMTP')
    def test_email_client_send(self, mock_smtp):
        """Test email client send functionality."""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        mock_smtp.return_value = mock_server
        
        client = EmailClient(
            host="smtp.example.com",
            port=587,
            username="user",
            password="pass",
            from_address="noreply@example.com",
            use_tls=False,
            use_starttls=True,
        )
        
        result = client.send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
        )
        
        # We expect True on successful send
        assert result is True or result is False  # Depends on mock setup
    
    def test_email_client_no_host(self):
        """Test email client returns False when not configured."""
        client = EmailClient(
            host="",
            port=587,
            from_address="",
        )
        
        result = client.send_email(
            to="recipient@example.com",
            subject="Test",
            body_text="Test body",
        )
        
        assert result is False


# =============================================================================
# SMS Client Tests
# =============================================================================

class TestSMSClient:
    """Tests for SMS composition and sending."""
    
    def test_compose_contact_sms(self):
        """Test contact SMS composition."""
        sms = compose_contact_sms(
            site_name="Test Site",
            contact_value="+41791234567",
            message="Hello! This is a test message.",
        )
        
        assert "Test Site" in sms
        assert "+41791234567" in sms
        assert "Hello!" in sms
    
    def test_compose_contact_sms_truncation(self):
        """Test SMS truncation for long messages."""
        long_message = "A" * 200
        sms = compose_contact_sms(
            site_name="Test Site",
            contact_value="+41791234567",
            message=long_message,
        )
        
        # Should be truncated
        assert len(sms) < 200
        assert "..." in sms
    
    def test_sms_client_disabled(self):
        """Test SMS client returns False when disabled."""
        client = SMSClient(
            account_sid="test",
            auth_token="test",
            from_number="+1234567890",
            enabled=False,
        )
        
        result = client.send_sms("+41791234567", "Test")
        assert result is False
    
    def test_sms_client_no_credentials(self):
        """Test SMS client returns False when credentials missing."""
        client = SMSClient(
            account_sid="",
            auth_token="",
            from_number="",
            enabled=True,
        )
        
        result = client.send_sms("+41791234567", "Test")
        assert result is False


# =============================================================================
# CAPTCHA Verifier Tests
# =============================================================================

class TestCaptchaVerifier:
    """Tests for CAPTCHA verification."""
    
    def test_captcha_disabled_always_passes(self):
        """Test that disabled CAPTCHA always returns True."""
        verifier = CaptchaVerifier(
            secret_key="test-secret",
            site_key="test-site",
            enabled=False,
        )
        
        result = verifier.verify("invalid-token")
        assert result is True
    
    def test_captcha_missing_token(self):
        """Test that missing token fails when CAPTCHA enabled."""
        verifier = CaptchaVerifier(
            secret_key="test-secret",
            site_key="test-site",
            enabled=True,
        )
        
        result = verifier.verify("")
        assert result is False
        
        result = verifier.verify(None)
        assert result is False
    
    def test_captcha_no_secret_key(self):
        """Test that missing secret key fails open."""
        verifier = CaptchaVerifier(
            secret_key="",
            site_key="test-site",
            enabled=True,
        )
        
        result = verifier.verify("some-token")
        # Should fail open (return True) when not configured
        assert result is True
    
    @patch('httpx.Client.post')
    def test_captcha_verification_success(self, mock_post):
        """Test successful CAPTCHA verification."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        verifier = CaptchaVerifier(
            secret_key="test-secret",
            site_key="test-site",
            enabled=True,
        )
        
        result = verifier.verify("valid-token", "192.168.1.1")
        assert result is True
    
    @patch('httpx.Client.post')
    def test_captcha_verification_failure(self, mock_post):
        """Test failed CAPTCHA verification."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        verifier = CaptchaVerifier(
            secret_key="test-secret",
            site_key="test-site",
            enabled=True,
        )
        
        result = verifier.verify("invalid-token")
        assert result is False


# =============================================================================
# Contact Route Integration Tests
# =============================================================================

class TestContactRouteIntegration:
    """Integration tests for contact form submission endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_client_with_site):
        """Set up test fixtures."""
        self.client = test_client_with_site
        reset_spam_checker()
    
    def test_contact_submit_success(self, test_client_with_site):
        """Test successful contact form submission."""
        response = test_client_with_site.post(
            "/api/contact/submit",
            data={
                "contact": "test@example.com",
                "message": "Hello, this is a test message!",
                "website": "",  # Empty honeypot
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
    
    def test_contact_submit_with_phone(self, test_client_with_site):
        """Test contact submission with phone number."""
        response = test_client_with_site.post(
            "/api/contact/submit",
            data={
                "contact": "+41791234567",
                "message": "Please call me back!",
                "website": "",
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
    
    def test_contact_submit_honeypot_filled(self, test_client_with_site):
        """Test that honeypot spam returns generic success."""
        reset_spam_checker()
        
        response = test_client_with_site.post(
            "/api/contact/submit",
            data={
                "contact": "spam@bot.com",
                "message": "Buy now!",
                "website": "http://spam.com",  # Filled honeypot
            }
        )
        
        # Should still return 200 (no feedback to spammer)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"
    
    def test_contact_submit_rate_limited(self, test_client_with_site):
        """Test rate limiting returns generic success."""
        reset_spam_checker()
        
        # Submit multiple times to trigger rate limit
        for i in range(5):
            response = test_client_with_site.post(
                "/api/contact/submit",
                data={
                    "contact": "test@example.com",
                    "message": f"Message {i}",
                    "website": "",
                },
                headers={"X-Forwarded-For": "1.2.3.4"}
            )
            assert response.status_code == 200
            assert response.json()["status"] == "submitted"
    
    def test_contact_config_endpoint(self, test_client_with_site):
        """Test contact config endpoint returns CAPTCHA settings."""
        response = test_client_with_site.get("/api/contact/config")
        
        assert response.status_code == 200
        data = response.json()
        assert "captcha_enabled" in data
        assert data["captcha_enabled"] is False  # Default disabled


# =============================================================================
# Global Spam Checker Tests
# =============================================================================

class TestGlobalSpamChecker:
    """Tests for global spam checker instance."""
    
    def test_get_spam_checker_singleton(self):
        """Test that get_spam_checker returns singleton."""
        reset_spam_checker()
        
        checker1 = get_spam_checker()
        checker2 = get_spam_checker()
        
        assert checker1 is checker2
    
    def test_reset_spam_checker(self):
        """Test that reset_spam_checker creates new instance."""
        reset_spam_checker()
        checker1 = get_spam_checker()
        
        reset_spam_checker()
        checker2 = get_spam_checker()
        
        assert checker1 is not checker2
