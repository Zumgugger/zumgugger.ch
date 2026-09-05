"""Contact form submission routes."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.site import Site
from app.routes.public import get_site_from_request
from app.utils.contact import validate_contact, ContactType
from app.utils.spam import get_spam_checker
from app.utils.email import get_email_client, compose_contact_email
from app.utils.sms import get_sms_client, compose_contact_sms
from app.utils.captcha import get_captcha_verifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/contact", tags=["contact"])


class ContactSubmitResponse(BaseModel):
    """Response model for contact form submission."""
    status: str
    message: Optional[str] = None


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request.
    
    Handles X-Forwarded-For header for proxied requests.
    
    Args:
        request: The incoming request.
        
    Returns:
        Client IP address string.
    """
    # Check X-Forwarded-For header first (set by reverse proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Get the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"


async def add_spam_delay():
    """Add a small delay for spam submissions to deter bots."""
    delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(delay)


@router.post("/submit", response_model=ContactSubmitResponse)
async def submit_contact_form(
    request: Request,
    contact: str = Form(..., description="Email or phone number"),
    message: str = Form(..., description="Contact message"),
    website: str = Form("", description="Honeypot field"),
    cf_turnstile_response: str = Form("", alias="cf-turnstile-response", description="Turnstile CAPTCHA token"),
    db: Session = Depends(get_db),
):
    """Handle contact form submission.
    
    This endpoint:
    1. Validates the contact value (email or phone)
    2. Runs spam checks (honeypot, rate limiting, duplicates)
    3. Verifies CAPTCHA if enabled
    4. Sends email notification
    5. Sends SMS notification if enabled
    
    Always returns success (200) to avoid giving feedback to spammers.
    
    Args:
        request: The incoming request.
        contact: Visitor's contact information (email or phone).
        message: Visitor's message.
        website: Hidden honeypot field (should be empty).
        cf_turnstile_response: Cloudflare Turnstile CAPTCHA token.
        db: Database session.
        
    Returns:
        JSON response with status "submitted".
    """
    # Get site context
    site = get_site_from_request(request, db)
    if not site:
        # Still return success to not leak information
        logger.warning("Contact submission for unknown site")
        await add_spam_delay()
        return ContactSubmitResponse(status="submitted")
    
    # Get client IP
    ip_address = get_client_ip(request)
    
    # Validate contact value
    validation = validate_contact(contact)
    if not validation.is_valid:
        # Return generic success but log the validation failure
        logger.info(f"Invalid contact value submitted: {validation.error_message}")
        await add_spam_delay()
        return ContactSubmitResponse(status="submitted")
    
    normalized_contact = validation.normalized_value
    contact_type = validation.contact_type.value
    
    # Get spam checker
    spam_checker = get_spam_checker()
    
    # Run spam checks
    is_spam = spam_checker.is_spam(
        ip_address=ip_address,
        normalized_contact=normalized_contact,
        message=message,
        honeypot_value=website,
    )
    
    if is_spam:
        logger.info(f"Spam submission blocked from IP {ip_address}")
        await add_spam_delay()
        return ContactSubmitResponse(status="submitted")
    
    # Check CAPTCHA if enabled
    captcha_verifier = get_captcha_verifier()
    if captcha_verifier and captcha_verifier.enabled:
        captcha_valid = captcha_verifier.verify(cf_turnstile_response, ip_address)
        if not captcha_valid:
            logger.info(f"CAPTCHA verification failed from IP {ip_address}")
            # Return 400 for CAPTCHA failures (per spec)
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "CAPTCHA-Überprüfung fehlgeschlagen"}
            )
    
    # Record the submission for rate limiting
    spam_checker.record_submission(ip_address, normalized_contact, message)
    
    # Send email notification
    email_sent = False
    email_client = get_email_client()
    if email_client:
        try:
            from app.config import get_settings
            settings = get_settings()
            
            recipient = getattr(settings, 'contact_to_email', None)
            if recipient:
                subject, body_text, body_html = compose_contact_email(
                    site_name=site.name,
                    contact_value=normalized_contact,
                    contact_type=contact_type,
                    message=message,
                    ip_address=ip_address,
                )
                
                # Set reply-to if contact is email
                reply_to = normalized_contact if contact_type == "email" else None
                
                email_sent = email_client.send_email(
                    to=recipient,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                    reply_to=reply_to,
                )
                
                if email_sent:
                    logger.info(f"Contact email sent for site {site.name}")
                else:
                    logger.error(f"Failed to send contact email for site {site.name}")
            else:
                logger.warning("No contact recipient email configured")
        except Exception as e:
            logger.error(f"Error sending contact email: {e}")
    
    # Send SMS notification if enabled
    sms_sent = False
    sms_client = get_sms_client()
    if sms_client and sms_client.enabled:
        try:
            from app.config import get_settings
            settings = get_settings()
            
            recipient_number = getattr(settings, 'sms_recipient_number', None)
            if recipient_number:
                sms_body = compose_contact_sms(
                    site_name=site.name,
                    contact_value=normalized_contact,
                    message=message,
                )
                
                sms_sent = sms_client.send_sms(
                    to_number=recipient_number,
                    message=sms_body,
                )
                
                if sms_sent:
                    logger.info(f"Contact SMS sent for site {site.name}")
                else:
                    logger.error(f"Failed to send contact SMS for site {site.name}")
            else:
                logger.warning("No SMS recipient number configured")
        except Exception as e:
            logger.error(f"Error sending contact SMS: {e}")
    
    # Log the submission (for debugging, not stored)
    logger.info(
        f"Contact submission processed: site={site.name}, "
        f"contact_type={contact_type}, email_sent={email_sent}, sms_sent={sms_sent}"
    )
    
    return ContactSubmitResponse(status="submitted")


@router.get("/config")
async def get_contact_config(request: Request, db: Session = Depends(get_db)):
    """Get contact form configuration for the frontend.
    
    Returns whether CAPTCHA is enabled and the site key if so.
    
    Args:
        request: The incoming request.
        db: Database session.
        
    Returns:
        JSON with CAPTCHA configuration.
    """
    captcha_verifier = get_captcha_verifier()
    
    return {
        "captcha_enabled": captcha_verifier.enabled if captcha_verifier else False,
        "captcha_site_key": captcha_verifier.site_key if captcha_verifier and captcha_verifier.enabled else None,
    }
