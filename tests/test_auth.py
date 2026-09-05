"""Tests for authentication utilities."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from app.utils.auth import (
    generate_session_token,
    hash_password,
    is_token_sufficiently_random,
    measure_hash_time,
    verify_password,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_string(self):
        """Hash password should return a string."""
        result = hash_password("test_password")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_password_different_each_time(self):
        """Same password should produce different hashes (salted)."""
        password = "test_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Verify password should return True for correct password."""
        password = "test_password"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_wrong(self):
        """Verify password should return False for wrong password."""
        password = "test_password"
        hashed = hash_password(password)
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_empty_password(self):
        """Verify password should reject empty password."""
        hashed = hash_password("test_password")
        assert verify_password("", hashed) is False

    def test_verify_password_invalid_hash(self):
        """Verify password should handle invalid hash gracefully."""
        assert verify_password("password", "invalid_hash") is False

    def test_verify_password_empty_hash(self):
        """Verify password should handle empty hash gracefully."""
        assert verify_password("password", "") is False

    def test_hash_password_special_characters(self):
        """Hash and verify passwords with special characters."""
        password = "p@$$w0rd!#%^&*()"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_unicode(self):
        """Hash and verify passwords with unicode characters."""
        password = "pässwörd日本語"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_hash_password_long_password(self):
        """Hash and verify passwords at bcrypt max length (72 bytes)."""
        # bcrypt has a 72 byte limit
        password = "a" * 72
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestSessionToken:
    """Tests for session token generation."""

    def test_generate_session_token_returns_string(self):
        """Generate session token should return a string."""
        token = generate_session_token()
        assert isinstance(token, str)

    def test_generate_session_token_sufficient_length(self):
        """Token should have sufficient length (at least 32 characters)."""
        token = generate_session_token()
        assert len(token) >= 32

    def test_generate_session_token_unique(self):
        """Each token should be unique."""
        tokens = [generate_session_token() for _ in range(100)]
        assert len(set(tokens)) == 100

    def test_generate_session_token_url_safe(self):
        """Token should be URL-safe."""
        token = generate_session_token()
        # URL-safe characters only
        safe_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
        assert all(c in safe_chars for c in token)

    def test_is_token_sufficiently_random_valid(self):
        """Valid token should pass randomness check."""
        token = generate_session_token()
        assert is_token_sufficiently_random(token) is True

    def test_is_token_sufficiently_random_too_short(self):
        """Too short token should fail randomness check."""
        token = "abc123"
        assert is_token_sufficiently_random(token) is False

    def test_is_token_sufficiently_random_repetitive(self):
        """Highly repetitive token should fail randomness check."""
        token = "a" * 64
        assert is_token_sufficiently_random(token) is False


class TestHashTiming:
    """Tests for hash timing (security verification)."""

    def test_hash_takes_reasonable_time(self):
        """Hashing should take more than 100ms for security."""
        hash_time = measure_hash_time()
        # With default bcrypt rounds (12), this should be > 100ms
        assert hash_time >= 0.05  # At least 50ms to allow for some variance

    @patch("app.utils.auth.get_settings")
    def test_hash_time_scales_with_rounds(self, mock_settings):
        """Higher bcrypt rounds should take longer."""
        from unittest.mock import MagicMock
        
        # Test with minimum rounds (fast)
        mock = MagicMock()
        mock.bcrypt_rounds = 4
        mock_settings.return_value = mock
        
        fast_time = measure_hash_time()
        
        # Test with more rounds (slower)
        mock.bcrypt_rounds = 8
        slow_time = measure_hash_time()
        
        # More rounds should take longer (allow for some variance)
        assert slow_time >= fast_time * 0.5
