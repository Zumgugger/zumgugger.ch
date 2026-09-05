"""SMS delivery utilities using Twilio."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SMSClient:
    """Twilio SMS client for sending contact notifications.
    
    Handles Twilio API integration for SMS delivery.
    """
    
    # Maximum SMS length (we'll truncate messages)
    MAX_SMS_LENGTH = 160
    
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        enabled: bool = True,
    ):
        """Initialize SMSClient.
        
        Args:
            account_sid: Twilio Account SID.
            auth_token: Twilio Auth Token.
            from_number: Twilio phone number to send from.
            enabled: Whether SMS is enabled.
        """
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.enabled = enabled
        self._client = None
    
    def _get_client(self):
        """Get or create Twilio client.
        
        Returns:
            Twilio Client instance.
        """
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.error("Twilio library not installed")
                raise
        return self._client
    
    def send_sms(self, to_number: str, message: str) -> bool:
        """Send an SMS message.
        
        Args:
            to_number: Recipient phone number in E.164 format.
            message: Message content (will be truncated if too long).
            
        Returns:
            True if SMS was sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.debug("SMS is disabled, skipping send")
            return False
        
        if not self.account_sid or not self.auth_token or not self.from_number:
            logger.warning("SMS credentials not configured, skipping send")
            return False
        
        try:
            client = self._get_client()
            
            # Truncate message if needed
            if len(message) > self.MAX_SMS_LENGTH:
                message = message[:self.MAX_SMS_LENGTH - 3] + "..."
            
            sms = client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number,
            )
            
            logger.info(f"SMS sent successfully, SID: {sms.sid}")
            return True
            
        except ImportError:
            logger.error("Twilio library not installed")
            return False
            
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return False


def compose_contact_sms(
    site_name: str,
    contact_value: str,
    message: str,
) -> str:
    """Compose a contact form SMS notification.
    
    Args:
        site_name: Name of the website.
        contact_value: Visitor's contact (email or phone).
        message: Visitor's message (will be truncated).
        
    Returns:
        SMS message text.
    """
    # Keep message short for SMS
    max_msg_len = 80
    truncated_msg = message[:max_msg_len]
    if len(message) > max_msg_len:
        truncated_msg += "..."
    
    return f"Neue Anfrage ({site_name}): {contact_value} - {truncated_msg}"


# Global SMS client instance
_sms_client: Optional[SMSClient] = None


def get_sms_client() -> Optional[SMSClient]:
    """Get the global SMS client instance.
    
    Returns:
        SMSClient instance or None if not configured.
    """
    return _sms_client


def configure_sms_client(
    account_sid: str,
    auth_token: str,
    from_number: str,
    enabled: bool = True,
) -> SMSClient:
    """Configure the global SMS client.
    
    Args:
        account_sid: Twilio Account SID.
        auth_token: Twilio Auth Token.
        from_number: Twilio phone number to send from.
        enabled: Whether SMS is enabled.
        
    Returns:
        Configured SMSClient instance.
    """
    global _sms_client
    _sms_client = SMSClient(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
        enabled=enabled,
    )
    return _sms_client


def reset_sms_client() -> None:
    """Reset the global SMS client (for testing)."""
    global _sms_client
    _sms_client = None
