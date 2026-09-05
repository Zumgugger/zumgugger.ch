"""CAPTCHA verification utilities using Cloudflare Turnstile."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Cloudflare Turnstile verification URL
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class CaptchaVerifier:
    """Cloudflare Turnstile CAPTCHA verifier.
    
    Verifies CAPTCHA tokens with Cloudflare's API.
    """
    
    def __init__(
        self,
        secret_key: str,
        site_key: str,
        enabled: bool = False,
        timeout: float = 10.0,
    ):
        """Initialize CaptchaVerifier.
        
        Args:
            secret_key: Turnstile secret key (server-side).
            site_key: Turnstile site key (client-side, for reference).
            enabled: Whether CAPTCHA verification is enabled.
            timeout: HTTP request timeout in seconds.
        """
        self.secret_key = secret_key
        self.site_key = site_key
        self.enabled = enabled
        self.timeout = timeout
    
    async def verify_async(
        self,
        token: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Verify a CAPTCHA token asynchronously.
        
        Args:
            token: The CAPTCHA token from the client.
            ip_address: Optional client IP address.
            
        Returns:
            True if verification succeeded, False otherwise.
        """
        if not self.enabled:
            return True
        
        if not token:
            logger.warning("CAPTCHA token missing")
            return False
        
        if not self.secret_key:
            logger.warning("CAPTCHA secret key not configured")
            return True  # Fail open if not configured
        
        try:
            data = {
                "secret": self.secret_key,
                "response": token,
            }
            
            if ip_address:
                data["remoteip"] = ip_address
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(TURNSTILE_VERIFY_URL, data=data)
                response.raise_for_status()
                result = response.json()
            
            success = result.get("success", False)
            
            if not success:
                error_codes = result.get("error-codes", [])
                logger.info(f"CAPTCHA verification failed: {error_codes}")
            
            return success
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during CAPTCHA verification: {e}")
            return True  # Fail open on network errors
            
        except Exception as e:
            logger.error(f"Unexpected error during CAPTCHA verification: {e}")
            return True  # Fail open on unexpected errors
    
    def verify(
        self,
        token: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Verify a CAPTCHA token synchronously.
        
        Args:
            token: The CAPTCHA token from the client.
            ip_address: Optional client IP address.
            
        Returns:
            True if verification succeeded, False otherwise.
        """
        if not self.enabled:
            return True
        
        if not token:
            logger.warning("CAPTCHA token missing")
            return False
        
        if not self.secret_key:
            logger.warning("CAPTCHA secret key not configured")
            return True  # Fail open if not configured
        
        try:
            data = {
                "secret": self.secret_key,
                "response": token,
            }
            
            if ip_address:
                data["remoteip"] = ip_address
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(TURNSTILE_VERIFY_URL, data=data)
                response.raise_for_status()
                result = response.json()
            
            success = result.get("success", False)
            
            if not success:
                error_codes = result.get("error-codes", [])
                logger.info(f"CAPTCHA verification failed: {error_codes}")
            
            return success
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during CAPTCHA verification: {e}")
            return True  # Fail open on network errors
            
        except Exception as e:
            logger.error(f"Unexpected error during CAPTCHA verification: {e}")
            return True  # Fail open on unexpected errors


# Global CAPTCHA verifier instance
_captcha_verifier: Optional[CaptchaVerifier] = None


def get_captcha_verifier() -> Optional[CaptchaVerifier]:
    """Get the global CAPTCHA verifier instance.
    
    Returns:
        CaptchaVerifier instance or None if not configured.
    """
    return _captcha_verifier


def configure_captcha_verifier(
    secret_key: str,
    site_key: str,
    enabled: bool = False,
) -> CaptchaVerifier:
    """Configure the global CAPTCHA verifier.
    
    Args:
        secret_key: Turnstile secret key (server-side).
        site_key: Turnstile site key (client-side).
        enabled: Whether CAPTCHA verification is enabled.
        
    Returns:
        Configured CaptchaVerifier instance.
    """
    global _captcha_verifier
    _captcha_verifier = CaptchaVerifier(
        secret_key=secret_key,
        site_key=site_key,
        enabled=enabled,
    )
    return _captcha_verifier


def reset_captcha_verifier() -> None:
    """Reset the global CAPTCHA verifier (for testing)."""
    global _captcha_verifier
    _captcha_verifier = None
