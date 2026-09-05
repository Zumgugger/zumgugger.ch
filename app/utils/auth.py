"""Authentication utilities for WebsiteCMS."""

from __future__ import annotations

import secrets
import time
from typing import Optional

import bcrypt

from app.config import get_settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.
    
    Args:
        password: Plain text password to hash.
        
    Returns:
        Bcrypt hash string.
    """
    settings = get_settings()
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash.
    
    Args:
        password: Plain text password to verify.
        password_hash: Bcrypt hash to check against.
        
    Returns:
        True if password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8")
        )
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure session token.
    
    Returns:
        Random URL-safe token string (64 characters).
    """
    return secrets.token_urlsafe(48)


def is_token_sufficiently_random(token: str, min_length: int = 32) -> bool:
    """Check if a token meets basic randomness requirements.
    
    Args:
        token: The token to check.
        min_length: Minimum required length.
        
    Returns:
        True if token meets requirements.
    """
    if len(token) < min_length:
        return False
    
    # Check for some variety in characters
    unique_chars = len(set(token))
    return unique_chars >= min_length // 2


def measure_hash_time(password: str = "test_password") -> float:
    """Measure time to hash a password (for security verification).
    
    Args:
        password: Password to hash for timing.
        
    Returns:
        Time in seconds to hash the password.
    """
    start = time.time()
    hash_password(password)
    return time.time() - start
