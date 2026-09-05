"""Authentication middleware for WebsiteCMS."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.session import AdminSession
from app.models.site import AdminUser, Site

logger = logging.getLogger(__name__)

# Cookie name for session token
SESSION_COOKIE_NAME = "session_token"


def get_session_token(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)
) -> Optional[str]:
    """Extract session token from cookie.
    
    Args:
        session_token: Session token from cookie.
        
    Returns:
        Session token string or None.
    """
    return session_token


def get_current_session(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(get_session_token),
) -> Optional[AdminSession]:
    """Get the current admin session if valid.
    
    Args:
        db: Database session.
        token: Session token from cookie.
        
    Returns:
        AdminSession if valid, None otherwise.
    """
    if not token:
        return None
    
    session = db.query(AdminSession).filter(AdminSession.token == token).first()
    
    if not session:
        return None
    
    if session.is_expired():
        # Clean up expired session
        db.delete(session)
        db.commit()
        return None
    
    return session


def get_optional_admin(
    db: Session = Depends(get_db),
    session: Optional[AdminSession] = Depends(get_current_session),
) -> Optional[AdminUser]:
    """Get the current admin user if logged in (optional).
    
    Use this for routes that work both with and without authentication.
    
    Args:
        db: Database session.
        session: Current admin session (if any).
        
    Returns:
        AdminUser if logged in, None otherwise.
    """
    if not session:
        return None
    
    return db.query(AdminUser).filter(AdminUser.id == session.admin_user_id).first()


def get_current_admin(
    db: Session = Depends(get_db),
    session: Optional[AdminSession] = Depends(get_current_session),
) -> AdminUser:
    """Get the current admin user (required).
    
    Raises 401 if not authenticated.
    
    Args:
        db: Database session.
        session: Current admin session.
        
    Returns:
        AdminUser for the current session.
        
    Raises:
        HTTPException: 401 if not authenticated.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Not authenticated"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin = db.query(AdminUser).filter(AdminUser.id == session.admin_user_id).first()
    
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid session"},
        )
    
    return admin


def require_auth(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    """Dependency that requires authentication.
    
    Use this to protect admin-only routes.
    
    Args:
        admin: Current admin user.
        
    Returns:
        AdminUser for the current session.
    """
    return admin


def get_site_from_request(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[Site]:
    """Extract site from request (via host header or query param).
    
    Args:
        request: FastAPI request.
        db: Database session.
        
    Returns:
        Site if found, None otherwise.
    """
    # First try query parameter (for testing)
    site_domain = request.query_params.get("site")
    
    # Then try host header
    if not site_domain:
        host = request.headers.get("host", "")
        # Remove port if present
        site_domain = host.split(":")[0]
    
    if not site_domain:
        return None
    
    return db.query(Site).filter(Site.domain == site_domain).first()


async def cleanup_expired_sessions(db: Session) -> int:
    """Delete all expired sessions from the database.
    
    Args:
        db: Database session.
        
    Returns:
        Number of sessions deleted.
    """
    now = datetime.now(timezone.utc)
    result = db.query(AdminSession).filter(AdminSession.expires_at < now).delete()
    db.commit()
    logger.info(f"Cleaned up {result} expired sessions")
    return result
