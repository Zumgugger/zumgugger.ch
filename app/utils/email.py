"""Email delivery utilities using SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class EmailClient:
    """SMTP email client for sending contact form notifications.
    
    Handles SMTP connection, authentication, and email composition.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_address: str = "",
        use_tls: bool = True,
        use_starttls: bool = False,
        timeout: int = 30,
    ):
        """Initialize EmailClient.
        
        Args:
            host: SMTP server hostname.
            port: SMTP server port.
            username: SMTP authentication username.
            password: SMTP authentication password.
            from_address: Default sender address.
            use_tls: Use TLS connection (port 465).
            use_starttls: Use STARTTLS (port 587).
            timeout: Connection timeout in seconds.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_address = from_address
        self.use_tls = use_tls
        self.use_starttls = use_starttls
        self.timeout = timeout
    
    def _create_message(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> MIMEMultipart:
        """Create an email message.
        
        Args:
            to: Recipient email address.
            subject: Email subject.
            body_text: Plain text body.
            body_html: Optional HTML body.
            reply_to: Optional Reply-To address.
            
        Returns:
            MIMEMultipart message object.
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.from_address
        msg['To'] = to
        
        if reply_to:
            msg['Reply-To'] = reply_to
        
        # Add plain text part
        text_part = MIMEText(body_text, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Add HTML part if provided
        if body_html:
            html_part = MIMEText(body_html, 'html', 'utf-8')
            msg.attach(html_part)
        
        return msg
    
    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """Send an email.
        
        Args:
            to: Recipient email address.
            subject: Email subject.
            body_text: Plain text body.
            body_html: Optional HTML body.
            reply_to: Optional Reply-To address.
            
        Returns:
            True if email was sent successfully, False otherwise.
        """
        if not self.host:
            logger.warning("SMTP host not configured, skipping email send")
            return False
        
        try:
            msg = self._create_message(to, subject, body_text, body_html, reply_to)
            
            # Connect to SMTP server
            if self.use_tls and not self.use_starttls:
                # Direct TLS connection (port 465)
                server = smtplib.SMTP_SSL(
                    self.host, 
                    self.port, 
                    timeout=self.timeout
                )
            else:
                # Plain or STARTTLS connection
                server = smtplib.SMTP(
                    self.host, 
                    self.port, 
                    timeout=self.timeout
                )
                
                if self.use_starttls:
                    server.starttls()
            
            try:
                # Authenticate if credentials provided
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                # Send the email
                server.sendmail(
                    self.from_address,
                    [to],
                    msg.as_string()
                )
                
                logger.info(f"Email sent successfully to {to}")
                return True
                
            finally:
                server.quit()
                
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
            
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False


def compose_contact_email(
    site_name: str,
    contact_value: str,
    contact_type: str,
    message: str,
    ip_address: str,
) -> tuple[str, str, str]:
    """Compose a contact form notification email.
    
    Args:
        site_name: Name of the website.
        contact_value: Visitor's contact (email or phone).
        contact_type: Type of contact ("email" or "phone").
        message: Visitor's message.
        ip_address: Visitor's IP address.
        
    Returns:
        Tuple of (subject, body_text, body_html).
    """
    subject = f"Neue Kontaktanfrage - {site_name}"
    
    contact_label = "E-Mail" if contact_type == "email" else "Telefon"
    
    body_text = f"""Neue Kontaktanfrage über {site_name}

{contact_label}: {contact_value}

Nachricht:
{message}

---
IP-Adresse: {ip_address}
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; font-size: 24px; margin-bottom: 20px; }}
        .field {{ margin-bottom: 15px; }}
        .field-label {{ font-weight: bold; color: #555; }}
        .field-value {{ margin-top: 5px; }}
        .message-box {{ background: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee; font-size: 12px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Neue Kontaktanfrage</h1>
        
        <div class="field">
            <div class="field-label">{contact_label}:</div>
            <div class="field-value">
                {'<a href="mailto:' + contact_value + '">' + contact_value + '</a>' if contact_type == 'email' else '<a href="tel:' + contact_value + '">' + contact_value + '</a>'}
            </div>
        </div>
        
        <div class="field">
            <div class="field-label">Nachricht:</div>
            <div class="message-box">{message.replace(chr(10), '<br>')}</div>
        </div>
        
        <div class="footer">
            IP-Adresse: {ip_address}<br>
            Gesendet über {site_name}
        </div>
    </div>
</body>
</html>"""
    
    return subject, body_text, body_html


# Global email client instance
_email_client: Optional[EmailClient] = None


def get_email_client() -> Optional[EmailClient]:
    """Get the global email client instance.
    
    Returns:
        EmailClient instance or None if not configured.
    """
    return _email_client


def configure_email_client(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    from_address: str = "",
    use_tls: bool = True,
    use_starttls: bool = False,
) -> EmailClient:
    """Configure the global email client.
    
    Args:
        host: SMTP server hostname.
        port: SMTP server port.
        username: SMTP authentication username.
        password: SMTP authentication password.
        from_address: Default sender address.
        use_tls: Use TLS connection.
        use_starttls: Use STARTTLS.
        
    Returns:
        Configured EmailClient instance.
    """
    global _email_client
    _email_client = EmailClient(
        host=host,
        port=port,
        username=username,
        password=password,
        from_address=from_address,
        use_tls=use_tls,
        use_starttls=use_starttls,
    )
    return _email_client


def reset_email_client() -> None:
    """Reset the global email client (for testing)."""
    global _email_client
    _email_client = None
