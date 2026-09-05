"""Maintenance mode middleware for WebsiteCMS."""

from __future__ import annotations

import logging
from typing import Optional, Callable

from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.database import get_db_context

logger = logging.getLogger(__name__)


def is_admin_session(request: Request) -> bool:
    """Check if the request has a valid admin session.
    
    Args:
        request: The incoming request.
        
    Returns:
        True if the request has a valid admin session, False otherwise.
    """
    session_token = request.cookies.get("session")
    if not session_token:
        return False
    
    try:
        from app.models.session import AdminSession
        
        with get_db_context() as db:
            session = db.query(AdminSession).filter(AdminSession.token == session_token).first()
            if session and not session.is_expired():
                return True
            return False
    except Exception as e:
        logger.warning(f"Error checking admin session: {e}")
        return False


def render_maintenance_page(request: Request) -> HTMLResponse:
    """Render the maintenance page.
    
    Args:
        request: The incoming request.
        
    Returns:
        HTMLResponse with maintenance page content.
    """
    from app.main import templates
    from app.routes.public import get_site_from_request
    
    # Try to get site context for theming
    site = None
    content = None
    config = None
    
    try:
        with get_db_context() as db:
            site = get_site_from_request(request, db)
            if site:
                content = site.content
                config = site.config
    except Exception as e:
        logger.warning(f"Error getting site for maintenance page: {e}")
    
    context = {
        "request": request,
        "site": {
            "name": site.name if site else "Website",
            "domain": site.domain if site else "localhost",
            "type": site.site_type if site else "business",
        },
        "theme": config.theme_name if config else "clean",
        "css_variables": config.css_variables if config else {},
        "config": config,
        "contact_email": getattr(content, "contact_email", None) if content else None,
        "contact_phone": getattr(content, "contact_phone", None) if content else None,
    }
    
    return templates.TemplateResponse(
        request,
        "maintenance.html",
        context,
        status_code=503,
    )


class MaintenanceMiddleware(BaseHTTPMiddleware):
    """Middleware to show maintenance page when maintenance mode is active.
    
    Public visitors see the maintenance page, while logged-in admins bypass it.
    """
    
    # Paths that should always bypass maintenance mode
    BYPASS_PATHS = (
        "/admin/login",
        "/admin/logout",
        "/health",
        "/static/",
        "/favicon.ico",
    )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check maintenance mode and route accordingly.
        
        Args:
            request: The incoming request.
            call_next: The next middleware/route handler.
            
        Returns:
            Response from the next handler or maintenance page.
        """
        settings = get_settings()
        
        # Only check if maintenance mode is enabled
        if not settings.maintenance_mode:
            return await call_next(request)
        
        # Allow bypass paths
        path = request.url.path
        for bypass_path in self.BYPASS_PATHS:
            if path.startswith(bypass_path):
                return await call_next(request)
        
        # Allow admin paths for admin login/management
        if path.startswith("/admin"):
            return await call_next(request)
        
        # Allow API paths for admin operations
        if path.startswith("/api/admin"):
            return await call_next(request)
        
        # Check if user is admin - admins bypass maintenance mode
        if is_admin_session(request):
            return await call_next(request)
        
        # Show maintenance page for public visitors
        logger.debug(f"Showing maintenance page for path: {path}")
        return render_maintenance_page(request)
