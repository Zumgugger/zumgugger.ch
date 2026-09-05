"""Tests for application configuration."""

import os
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings


class TestSettings:
    """Tests for Settings configuration class."""

    def test_default_settings(self, monkeypatch, tmp_path):
        """Settings should have sensible defaults when no env vars or .env file."""
        # Change to temp directory to avoid loading .env file
        monkeypatch.chdir(tmp_path)
        
        # Clear any existing env vars that might interfere
        for key in ["DATABASE_URL", "PORT", "DEBUG", "LOG_LEVEL", "SECRET_KEY"]:
            monkeypatch.delenv(key, raising=False)
        
        settings = Settings(_env_file=None)  # Explicitly skip .env file
        
        assert settings.database_url == "sqlite:///data/site.db"
        assert settings.port == 8002
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.session_timeout_seconds == 86400

    def test_port_validation_valid(self):
        """Valid ports should be accepted."""
        settings = Settings(port=8080)
        assert settings.port == 8080
        
        settings = Settings(port=1)
        assert settings.port == 1
        
        settings = Settings(port=65535)
        assert settings.port == 65535

    def test_port_validation_invalid_low(self):
        """Port below 1 should be rejected."""
        with pytest.raises(ValidationError):
            Settings(port=0)

    def test_port_validation_invalid_high(self):
        """Port above 65535 should be rejected."""
        with pytest.raises(ValidationError):
            Settings(port=65536)

    def test_log_level_validation(self):
        """Only valid log levels should be accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            settings = Settings(log_level=level)
            assert settings.log_level == level

    def test_log_level_invalid(self):
        """Invalid log level should be rejected."""
        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")

    def test_secret_key_auto_generation(self):
        """Secret key should be auto-generated if not provided."""
        env_backup = os.environ.pop("SECRET_KEY", None)
        
        try:
            settings = Settings()
            assert settings.secret_key is not None
            assert len(settings.secret_key) > 0
        finally:
            if env_backup:
                os.environ["SECRET_KEY"] = env_backup

    def test_settings_from_env(self, monkeypatch):
        """Settings should load from environment variables."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        # Create new settings instance (don't use cached)
        settings = Settings()
        
        assert settings.database_url == "sqlite:///custom.db"
        assert settings.port == 9000
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

    def test_bcrypt_rounds_default(self):
        """Bcrypt rounds should have a secure default."""
        settings = Settings()
        assert settings.bcrypt_rounds >= 10  # Minimum secure value

    def test_bcrypt_rounds_validation(self):
        """Bcrypt rounds should be within valid range."""
        with pytest.raises(ValidationError):
            Settings(bcrypt_rounds=3)  # Too low
        
        with pytest.raises(ValidationError):
            Settings(bcrypt_rounds=32)  # Too high
