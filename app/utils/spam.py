"""Spam prevention utilities for contact form submissions."""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RateLimitEntry:
    """Track rate limit entries with timestamps."""
    timestamps: list[float] = field(default_factory=list)
    
    def add_timestamp(self, timestamp: float) -> None:
        """Add a timestamp to the entry."""
        self.timestamps.append(timestamp)
    
    def clean_old(self, window_seconds: float, current_time: float) -> None:
        """Remove timestamps older than the window."""
        cutoff = current_time - window_seconds
        self.timestamps = [ts for ts in self.timestamps if ts > cutoff]
    
    def count_in_window(self, window_seconds: float, current_time: float) -> int:
        """Count timestamps within the window."""
        cutoff = current_time - window_seconds
        return sum(1 for ts in self.timestamps if ts > cutoff)


class SpamChecker:
    """Multi-layer spam prevention for contact forms.
    
    Implements:
    - Honeypot field detection
    - Per-IP rate limiting
    - Per-contact rate limiting
    - Duplicate submission detection
    """
    
    # Default rate limits
    IP_RATE_LIMIT = 3  # Max submissions per IP
    IP_RATE_WINDOW = 600  # 10 minutes in seconds
    
    CONTACT_RATE_LIMIT = 2  # Max submissions per contact
    CONTACT_RATE_WINDOW = 600  # 10 minutes in seconds
    
    DUPLICATE_WINDOW = 120  # 2 minutes in seconds
    
    def __init__(
        self,
        ip_rate_limit: int = IP_RATE_LIMIT,
        ip_rate_window: int = IP_RATE_WINDOW,
        contact_rate_limit: int = CONTACT_RATE_LIMIT,
        contact_rate_window: int = CONTACT_RATE_WINDOW,
        duplicate_window: int = DUPLICATE_WINDOW,
    ):
        """Initialize SpamChecker with configurable limits.
        
        Args:
            ip_rate_limit: Max submissions per IP within window.
            ip_rate_window: Time window for IP rate limiting (seconds).
            contact_rate_limit: Max submissions per contact within window.
            contact_rate_window: Time window for contact rate limiting (seconds).
            duplicate_window: Time window for duplicate detection (seconds).
        """
        self.ip_rate_limit = ip_rate_limit
        self.ip_rate_window = ip_rate_window
        self.contact_rate_limit = contact_rate_limit
        self.contact_rate_window = contact_rate_window
        self.duplicate_window = duplicate_window
        
        # In-memory storage with thread safety
        self._ip_entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._contact_entries: dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self._duplicate_hashes: dict[str, float] = {}  # hash -> timestamp
        self._lock = Lock()
    
    def check_honeypot(self, honeypot_value: Optional[str]) -> bool:
        """Check if honeypot field was filled (indicates spam).
        
        Args:
            honeypot_value: Value of the hidden honeypot field.
            
        Returns:
            True if spam detected (honeypot filled), False otherwise.
        """
        if honeypot_value and honeypot_value.strip():
            logger.info("Spam detected: honeypot field filled")
            return True
        return False
    
    def check_rate_limit_ip(self, ip_address: str) -> bool:
        """Check if IP has exceeded rate limit.
        
        Args:
            ip_address: Client IP address.
            
        Returns:
            True if rate limit exceeded (spam), False otherwise.
        """
        if not ip_address:
            return False
        
        current_time = time.time()
        
        with self._lock:
            entry = self._ip_entries[ip_address]
            entry.clean_old(self.ip_rate_window, current_time)
            
            count = entry.count_in_window(self.ip_rate_window, current_time)
            
            if count >= self.ip_rate_limit:
                logger.info(f"Spam detected: IP rate limit exceeded for {ip_address}")
                return True
            
            return False
    
    def record_ip_submission(self, ip_address: str) -> None:
        """Record a submission from an IP address.
        
        Args:
            ip_address: Client IP address.
        """
        if not ip_address:
            return
        
        current_time = time.time()
        
        with self._lock:
            self._ip_entries[ip_address].add_timestamp(current_time)
    
    def check_rate_limit_contact(self, normalized_contact: str) -> bool:
        """Check if contact value has exceeded rate limit.
        
        Args:
            normalized_contact: Normalized contact value (email or E.164 phone).
            
        Returns:
            True if rate limit exceeded (spam), False otherwise.
        """
        if not normalized_contact:
            return False
        
        current_time = time.time()
        
        with self._lock:
            entry = self._contact_entries[normalized_contact]
            entry.clean_old(self.contact_rate_window, current_time)
            
            count = entry.count_in_window(self.contact_rate_window, current_time)
            
            if count >= self.contact_rate_limit:
                logger.info(f"Spam detected: contact rate limit exceeded")
                return True
            
            return False
    
    def record_contact_submission(self, normalized_contact: str) -> None:
        """Record a submission for a contact value.
        
        Args:
            normalized_contact: Normalized contact value.
        """
        if not normalized_contact:
            return
        
        current_time = time.time()
        
        with self._lock:
            self._contact_entries[normalized_contact].add_timestamp(current_time)
    
    def _generate_duplicate_hash(self, normalized_contact: str, message: str) -> str:
        """Generate a hash for duplicate detection.
        
        Args:
            normalized_contact: Normalized contact value.
            message: Message content.
            
        Returns:
            SHA256 hash of the combined values.
        """
        combined = f"{normalized_contact}:{message}".encode('utf-8')
        return hashlib.sha256(combined).hexdigest()
    
    def check_duplicate(self, normalized_contact: str, message: str) -> bool:
        """Check if this is a duplicate submission.
        
        Args:
            normalized_contact: Normalized contact value.
            message: Message content.
            
        Returns:
            True if duplicate detected (spam), False otherwise.
        """
        if not normalized_contact or not message:
            return False
        
        current_time = time.time()
        dup_hash = self._generate_duplicate_hash(normalized_contact, message)
        
        with self._lock:
            # Clean old entries first
            cutoff = current_time - self.duplicate_window
            self._duplicate_hashes = {
                h: ts for h, ts in self._duplicate_hashes.items()
                if ts > cutoff
            }
            
            # Check if this hash exists
            if dup_hash in self._duplicate_hashes:
                logger.info("Spam detected: duplicate submission")
                return True
            
            return False
    
    def record_duplicate_hash(self, normalized_contact: str, message: str) -> None:
        """Record a submission hash for duplicate detection.
        
        Args:
            normalized_contact: Normalized contact value.
            message: Message content.
        """
        if not normalized_contact or not message:
            return
        
        current_time = time.time()
        dup_hash = self._generate_duplicate_hash(normalized_contact, message)
        
        with self._lock:
            self._duplicate_hashes[dup_hash] = current_time
    
    def is_spam(
        self,
        ip_address: str,
        normalized_contact: str,
        message: str,
        honeypot_value: Optional[str] = None,
    ) -> bool:
        """Run all spam checks on a submission.
        
        Args:
            ip_address: Client IP address.
            normalized_contact: Normalized contact value.
            message: Message content.
            honeypot_value: Value of honeypot field (if any).
            
        Returns:
            True if any spam check fails, False if submission is valid.
        """
        # Check honeypot first (cheapest check)
        if self.check_honeypot(honeypot_value):
            return True
        
        # Check rate limits
        if self.check_rate_limit_ip(ip_address):
            return True
        
        if self.check_rate_limit_contact(normalized_contact):
            return True
        
        # Check for duplicates
        if self.check_duplicate(normalized_contact, message):
            return True
        
        return False
    
    def record_submission(
        self,
        ip_address: str,
        normalized_contact: str,
        message: str,
    ) -> None:
        """Record a valid submission for rate limiting.
        
        Call this after a submission passes spam checks and is processed.
        
        Args:
            ip_address: Client IP address.
            normalized_contact: Normalized contact value.
            message: Message content.
        """
        self.record_ip_submission(ip_address)
        self.record_contact_submission(normalized_contact)
        self.record_duplicate_hash(normalized_contact, message)
    
    def clear(self) -> None:
        """Clear all rate limit and duplicate tracking data.
        
        Useful for testing.
        """
        with self._lock:
            self._ip_entries.clear()
            self._contact_entries.clear()
            self._duplicate_hashes.clear()


# Global spam checker instance
_spam_checker: Optional[SpamChecker] = None


def get_spam_checker() -> SpamChecker:
    """Get the global spam checker instance.
    
    Returns:
        SpamChecker instance.
    """
    global _spam_checker
    if _spam_checker is None:
        _spam_checker = SpamChecker()
    return _spam_checker


def reset_spam_checker() -> None:
    """Reset the global spam checker (for testing)."""
    global _spam_checker
    _spam_checker = None
