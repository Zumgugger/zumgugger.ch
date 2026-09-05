"""Contact value validation and normalization utilities."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Default phone parsing region (Switzerland)
DEFAULT_PHONE_REGION = "CH"


class ContactType(Enum):
    """Type of contact value."""
    EMAIL = "email"
    PHONE = "phone"
    UNKNOWN = "unknown"


@dataclass
class ContactValidationResult:
    """Result of contact value validation."""
    is_valid: bool
    contact_type: ContactType
    normalized_value: str
    original_value: str
    error_message: Optional[str] = None


# Email regex pattern (simplified but practical)
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Phone pattern for basic detection (contains mostly digits)
PHONE_CHARS_PATTERN = re.compile(r'^[\d\s\-\+\(\)\.\/]+$')


def is_email(value: str) -> bool:
    """Check if value looks like an email address.
    
    Args:
        value: The value to check.
        
    Returns:
        True if it matches email pattern.
    """
    return bool(EMAIL_PATTERN.match(value.strip()))


def is_phone_like(value: str) -> bool:
    """Check if value looks like a phone number.
    
    Args:
        value: The value to check.
        
    Returns:
        True if it contains mostly phone-like characters.
    """
    stripped = value.strip()
    if not stripped:
        return False
    
    # Must have at least 6 digits
    digit_count = sum(1 for c in stripped if c.isdigit())
    if digit_count < 6:
        return False
    
    # Should be mostly phone characters
    return bool(PHONE_CHARS_PATTERN.match(stripped))


def normalize_email(email: str) -> str:
    """Normalize an email address.
    
    Args:
        email: Email address to normalize.
        
    Returns:
        Lowercase, stripped email address.
    """
    return email.strip().lower()


def normalize_phone(phone: str, region: str = DEFAULT_PHONE_REGION) -> Tuple[bool, str, Optional[str]]:
    """Normalize a phone number to E.164 format.
    
    Args:
        phone: Phone number string.
        region: Default region for parsing (ISO 3166-1 alpha-2).
        
    Returns:
        Tuple of (success, normalized_number_or_original, error_message).
    """
    try:
        import phonenumbers
        
        # Parse the phone number
        parsed = phonenumbers.parse(phone, region)
        
        # Validate it
        if not phonenumbers.is_valid_number(parsed):
            return False, phone.strip(), "Ungültige Telefonnummer"
        
        # Format to E.164
        e164 = phonenumbers.format_number(
            parsed, 
            phonenumbers.PhoneNumberFormat.E164
        )
        
        return True, e164, None
        
    except ImportError:
        # phonenumbers not installed, return stripped original
        logger.warning("phonenumbers library not installed, skipping phone normalization")
        return True, phone.strip(), None
        
    except Exception as e:
        logger.debug(f"Phone parsing failed: {e}")
        return False, phone.strip(), "Ungültige Telefonnummer"


def validate_contact(
    value: str,
    phone_region: str = DEFAULT_PHONE_REGION,
) -> ContactValidationResult:
    """Validate and normalize a contact value (email or phone).
    
    Args:
        value: The contact value to validate.
        phone_region: Default region for phone parsing.
        
    Returns:
        ContactValidationResult with validation status and normalized value.
    """
    if not value or not value.strip():
        return ContactValidationResult(
            is_valid=False,
            contact_type=ContactType.UNKNOWN,
            normalized_value="",
            original_value=value or "",
            error_message="Kontaktfeld ist erforderlich",
        )
    
    stripped = value.strip()
    
    # Check if it's an email
    if is_email(stripped):
        normalized = normalize_email(stripped)
        return ContactValidationResult(
            is_valid=True,
            contact_type=ContactType.EMAIL,
            normalized_value=normalized,
            original_value=value,
        )
    
    # Check if it looks like a phone number
    if is_phone_like(stripped):
        success, normalized, error = normalize_phone(stripped, phone_region)
        
        if success:
            return ContactValidationResult(
                is_valid=True,
                contact_type=ContactType.PHONE,
                normalized_value=normalized,
                original_value=value,
            )
        else:
            return ContactValidationResult(
                is_valid=False,
                contact_type=ContactType.PHONE,
                normalized_value=stripped,
                original_value=value,
                error_message=error,
            )
    
    # Could be either but doesn't match patterns
    # Try phone parsing as a fallback (some formats might not match our regex)
    success, normalized, error = normalize_phone(stripped, phone_region)
    if success:
        return ContactValidationResult(
            is_valid=True,
            contact_type=ContactType.PHONE,
            normalized_value=normalized,
            original_value=value,
        )
    
    # Invalid format
    return ContactValidationResult(
        is_valid=False,
        contact_type=ContactType.UNKNOWN,
        normalized_value=stripped,
        original_value=value,
        error_message="Bitte geben Sie eine gültige E-Mail-Adresse oder Telefonnummer ein",
    )


def format_phone_for_display(e164_phone: str) -> str:
    """Format an E.164 phone number for display.
    
    Args:
        e164_phone: Phone number in E.164 format.
        
    Returns:
        Human-readable formatted phone number.
    """
    try:
        import phonenumbers
        
        parsed = phonenumbers.parse(e164_phone)
        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        
    except ImportError:
        return e164_phone
    except Exception:
        return e164_phone
