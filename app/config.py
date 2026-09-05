"""Application configuration using pydantic-settings."""

from __future__ import annotations

import secrets
import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///data/site.db",
        description="Database connection URL",
    )

    # Server
    port: int = Field(
        default=8002,
        ge=1,
        le=65535,
        description="Server port (1-65535)",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )

    # Security
    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Secret key for session signing",
    )

    # Session
    session_timeout_seconds: int = Field(
        default=86400,
        ge=60,
        description="Session timeout in seconds (default: 24 hours)",
    )

    # Bcrypt
    bcrypt_rounds: int = Field(
        default=12,
        ge=4,
        le=31,
        description="Bcrypt hashing rounds",
    )

    # SMTP Email Configuration
    smtp_host: str = Field(
        default="",
        description="SMTP server hostname",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port",
    )
    smtp_username: str = Field(
        default="",
        description="SMTP authentication username",
    )
    smtp_password: str = Field(
        default="",
        description="SMTP authentication password",
    )
    smtp_from: str = Field(
        default="",
        description="Sender email address",
    )
    smtp_starttls: bool = Field(
        default=True,
        description="Use STARTTLS for SMTP connection",
    )
    smtp_tls: bool = Field(
        default=False,
        description="Use direct TLS for SMTP connection (port 465)",
    )
    contact_to_email: str = Field(
        default="",
        description="Recipient email for contact form submissions",
    )

    # SMS Configuration (Twilio)
    sms_enabled: bool = Field(
        default=False,
        description="Enable SMS notifications",
    )
    twilio_account_sid: str = Field(
        default="",
        description="Twilio Account SID",
    )
    twilio_auth_token: str = Field(
        default="",
        description="Twilio Auth Token",
    )
    twilio_from_number: str = Field(
        default="",
        description="Twilio phone number to send from",
    )
    sms_recipient_number: str = Field(
        default="",
        description="Recipient phone number for SMS notifications",
    )

    # CAPTCHA Configuration (Cloudflare Turnstile)
    captcha_enabled: bool = Field(
        default=False,
        description="Enable CAPTCHA verification",
    )
    turnstile_site_key: str = Field(
        default="",
        description="Cloudflare Turnstile site key (public)",
    )
    turnstile_secret_key: str = Field(
        default="",
        description="Cloudflare Turnstile secret key (server-side)",
    )

    # Analytics Configuration (Plausible)
    analytics_enabled: bool = Field(
        default=False,
        description="Enable Plausible analytics",
    )
    plausible_domain: str = Field(
        default="",
        description="Domain to track in Plausible (e.g., example.com)",
    )
    plausible_script_src: str = Field(
        default="https://plausible.io/js/script.js",
        description="Plausible script source URL (for self-hosted instances)",
    )

    # Maintenance Mode
    maintenance_mode: bool = Field(
        default=False,
        description="Enable maintenance mode to show maintenance page to public visitors",
    )

    @field_validator("maintenance_mode", mode="before")
    @classmethod
    def parse_maintenance_mode(cls, v) -> bool:
        """Parse truthy/falsy values for maintenance mode.
        
        Accepts: 1/0, true/false, on/off, yes/no (case-insensitive).
        Default: OFF when unset/invalid.
        """
        if isinstance(v, bool):
            return v
        if isinstance(v, int):
            return v == 1
        if isinstance(v, str):
            truthy = ("1", "true", "on", "yes")
            return v.lower() in truthy
        return False

    @field_validator("port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    def configure_logging(self) -> None:
        """Configure application logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        
        # Warn if using default secret key in non-debug mode
        if not self.debug and self.secret_key == "change-me-in-production":
            logging.warning(
                "Using default SECRET_KEY in non-debug mode! "
                "Set a secure SECRET_KEY environment variable."
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
