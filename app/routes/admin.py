"""Admin authentication routes for WebsiteCMS."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import (
    SESSION_COOKIE_NAME,
    get_current_admin,
    get_current_session,
    require_auth,
    get_site_from_request,
)
from app.models.session import AdminSession
from app.models.site import AdminUser, Site
from app.utils.auth import generate_session_token
from app.utils.history import record_change, delete_old_changes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


class LoginRequest(BaseModel):
    """Request body for admin login."""
    
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    site_domain: Optional[str] = Field(None, description="Site domain (for testing)")


class LoginResponse(BaseModel):
    """Response body for successful login."""
    
    status: str = "logged_in"
    admin_id: int
    username: str
    site_id: int


class LogoutResponse(BaseModel):
    """Response body for logout."""
    
    status: str = "logged_out"


class AdminMeResponse(BaseModel):
    """Response body for /admin/me endpoint."""
    
    id: int
    username: str
    site_id: int
    site_domain: str
    last_login: Optional[str]


class ErrorResponse(BaseModel):
    """Error response body."""
    
    error: str


@router.get("/login")
async def login_page(request: Request):
    """Render the admin login page.
    
    Args:
        request: FastAPI request.
        
    Returns:
        HTML login page.
    """
    from fastapi.responses import HTMLResponse
    from fastapi.templating import Jinja2Templates
    
    templates = Jinja2Templates(directory="app/templates")
    return templates.TemplateResponse(request, "login.html", {"request": request})


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        400: {"model": ErrorResponse, "description": "Missing required fields or site not found"},
    },
)
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate an admin user and create a session.
    
    Args:
        request: FastAPI request.
        response: FastAPI response.
        credentials: Login credentials.
        db: Database session.
        
    Returns:
        Login response with session info.
        
    Raises:
        HTTPException: 401 if credentials are invalid, 400 if site not found.
    """
    # Get site from request or credentials
    site = None
    
    if credentials.site_domain:
        site = db.query(Site).filter(Site.domain == credentials.site_domain).first()
    else:
        site = get_site_from_request(request, db)
    
    if not site:
        # If still no site, try to find user by username and get their site
        admin = db.query(AdminUser).filter(AdminUser.username == credentials.username).first()
        if admin:
            site = admin.site
    
    if not site:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Site not found. Provide site_domain or use site query parameter."},
        )
    
    # Find admin user
    admin = db.query(AdminUser).filter(
        AdminUser.site_id == site.id,
        AdminUser.username == credentials.username,
    ).first()
    
    if not admin:
        logger.warning(f"Login failed: user '{credentials.username}' not found for site {site.domain}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid credentials"},
        )
    
    # Verify password
    if not admin.verify_password(credentials.password):
        logger.warning(f"Login failed: wrong password for user '{credentials.username}' on site {site.domain}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Invalid credentials"},
        )
    
    # Create session
    token = generate_session_token()
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    session = AdminSession.create_session(
        admin_user_id=admin.id,
        site_id=site.id,
        token=token,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    
    # Update last login
    admin.update_last_login()
    
    db.commit()
    
    logger.info(f"Admin '{admin.username}' logged in for site '{site.domain}'")
    
    # Set session cookie (HttpOnly, Secure when appropriate)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=session.expires_at.timestamp() - datetime.now(timezone.utc).timestamp(),
    )
    
    return LoginResponse(
        status="logged_in",
        admin_id=admin.id,
        username=admin.username,
        site_id=site.id,
    )


@router.post("/logout")
async def logout(
    db: Session = Depends(get_db),
    session: Optional[AdminSession] = Depends(get_current_session),
) -> RedirectResponse:
    """Log out the current admin user and redirect to the public homepage.
    
    Args:
        db: Database session.
        session: Current admin session.
        
    Returns:
        Redirect to the public homepage root.
    """
    if session:
        db.delete(session)
        db.commit()
        logger.info(f"Admin session {session.id} logged out")
    
    # Redirect to the root of the public homepage after logout
    redirect = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
    )
    return redirect


@router.get(
    "/me",
    response_model=AdminMeResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_current_user(
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> AdminMeResponse:
    """Get information about the currently logged-in admin.
    
    Args:
        admin: Current admin user (from auth).
        db: Database session.
        
    Returns:
        Admin user information.
    """
    # Ensure site is loaded
    site = db.query(Site).filter(Site.id == admin.site_id).first()
    
    return AdminMeResponse(
        id=admin.id,
        username=admin.username,
        site_id=admin.site_id,
        site_domain=site.domain if site else "unknown",
        last_login=admin.last_login.isoformat() if admin.last_login else None,
    )


@router.get("/users")
async def users_page(
    request: Request,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Render the admin users management page.
    
    Args:
        request: FastAPI request.
        admin: Current admin user (from auth).
        db: Database session.
        
    Returns:
        HTML admin users page.
    """
    from fastapi.templating import Jinja2Templates
    
    templates = Jinja2Templates(directory="app/templates")
    
    # Get site and users
    site = db.query(Site).filter(Site.id == admin.site_id).first()
    users = db.query(AdminUser).filter(AdminUser.site_id == admin.site_id).all()
    
    # Format users for template
    users_list = [
        {
            "id": user.id,
            "username": user.username,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }
        for user in users
    ]
    
    return templates.TemplateResponse(
        request,
        "admin_users.html",
        {
            "site": site,
            "users": users_list,
            "current_user": {"id": admin.id, "username": admin.username},
        },
    )


# ============================================
# Admin User Management API Endpoints
# ============================================

class AdminUserResponse(BaseModel):
    """Response for a single admin user."""
    
    id: int
    username: str
    created_at: str
    last_login: Optional[str] = None


class AdminUserListResponse(BaseModel):
    """Response for listing admin users."""
    
    users: List[AdminUserResponse]


class CreateAdminRequest(BaseModel):
    """Request to create a new admin user."""
    
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format (alphanumeric + underscore)."""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Benutzername darf nur Buchstaben, Zahlen und Unterstriche enthalten")
        return v


class UpdateAdminRequest(BaseModel):
    """Request to update an admin user."""
    
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username format if provided."""
        if v is not None and not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Benutzername darf nur Buchstaben, Zahlen und Unterstriche enthalten")
        return v


@router.get(
    "/users/list",
    response_model=AdminUserListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def list_admin_users(
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    """List all admin users for the current site.
    
    Args:
        admin: Current admin user (from auth).
        db: Database session.
        
    Returns:
        List of admin users.
    """
    users = db.query(AdminUser).filter(AdminUser.site_id == admin.site_id).all()
    
    return AdminUserListResponse(
        users=[
            AdminUserResponse(
                id=user.id,
                username=user.username,
                created_at=user.created_at.isoformat() if user.created_at else "",
                last_login=user.last_login.isoformat() if user.last_login else None,
            )
            for user in users
        ]
    )


@router.post(
    "/users/create",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        409: {"model": ErrorResponse, "description": "Username already exists"},
    },
)
async def create_admin_user(
    request: CreateAdminRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    """Create a new admin user for the current site.
    
    Args:
        request: Create user request.
        admin: Current admin user (from auth).
        db: Database session.
        
    Returns:
        The created admin user.
    """
    # Check if username already exists for this site
    existing = db.query(AdminUser).filter(
        AdminUser.site_id == admin.site_id,
        AdminUser.username == request.username,
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "message": "Benutzername existiert bereits"},
        )
    
    # Create new user
    new_user = AdminUser(
        site_id=admin.site_id,
        username=request.username,
    )
    new_user.set_password(request.password)
    
    db.add(new_user)
    
    # Record the change
    record_change(
        db=db,
        site_id=admin.site_id,
        admin_user_id=admin.id,
        module_type="admin",
        field_name="users",
        old_value=None,
        new_value={"username": request.username},
        description=f"Benutzer '{request.username}' erstellt",
    )
    
    delete_old_changes(db, admin.site_id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin '{admin.username}' created new admin '{new_user.username}' for site {admin.site_id}")
    
    return AdminUserResponse(
        id=new_user.id,
        username=new_user.username,
        created_at=new_user.created_at.isoformat() if new_user.created_at else "",
        last_login=None,
    )


@router.put(
    "/users/update/{user_id}",
    response_model=AdminUserResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "User not found"},
        409: {"model": ErrorResponse, "description": "Username already exists"},
    },
)
async def update_admin_user(
    user_id: int,
    request: UpdateAdminRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> AdminUserResponse:
    """Update an admin user's username or password.
    
    Args:
        user_id: ID of the user to update.
        request: Update user request.
        admin: Current admin user (from auth).
        db: Database session.
        
    Returns:
        The updated admin user.
    """
    # Find the user
    user = db.query(AdminUser).filter(
        AdminUser.id == user_id,
        AdminUser.site_id == admin.site_id,
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Benutzer nicht gefunden"},
        )
    
    changes = {}
    
    # Update username if provided
    if request.username and request.username != user.username:
        # Check if new username already exists
        existing = db.query(AdminUser).filter(
            AdminUser.site_id == admin.site_id,
            AdminUser.username == request.username,
            AdminUser.id != user_id,
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "message": "Benutzername existiert bereits"},
            )
        
        old_username = user.username
        user.username = request.username
        changes["username"] = {"old": old_username, "new": request.username}
    
    # Update password if provided
    if request.password:
        user.set_password(request.password)
        changes["password"] = "changed"
    
    if changes:
        # Record the change
        record_change(
            db=db,
            site_id=admin.site_id,
            admin_user_id=admin.id,
            module_type="admin",
            field_name="users",
            old_value={"id": user_id, "changes_before": True},
            new_value={"id": user_id, "changes": changes},
            description=f"Benutzer '{user.username}' aktualisiert",
        )
        
        delete_old_changes(db, admin.site_id, keep_count=50)
        db.commit()
        
        logger.info(f"Admin '{admin.username}' updated admin '{user.username}' for site {admin.site_id}")
    
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at.isoformat() if user.created_at else "",
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


@router.delete(
    "/users/delete/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"model": ErrorResponse, "description": "Cannot delete self"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "User not found"},
    },
)
async def delete_admin_user(
    user_id: int,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> None:
    """Delete an admin user.
    
    Args:
        user_id: ID of the user to delete.
        admin: Current admin user (from auth).
        db: Database session.
        
    Raises:
        HTTPException: If trying to delete self or user not found.
    """
    # Cannot delete self
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Sie können sich nicht selbst löschen"},
        )
    
    # Find the user
    user = db.query(AdminUser).filter(
        AdminUser.id == user_id,
        AdminUser.site_id == admin.site_id,
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Benutzer nicht gefunden"},
        )
    
    deleted_username = user.username
    
    # Delete all sessions for this user
    db.query(AdminSession).filter(AdminSession.admin_user_id == user_id).delete()
    
    # Delete the user
    db.delete(user)
    
    # Record the change
    record_change(
        db=db,
        site_id=admin.site_id,
        admin_user_id=admin.id,
        module_type="admin",
        field_name="users",
        old_value={"username": deleted_username, "id": user_id},
        new_value=None,
        description=f"Benutzer '{deleted_username}' gelöscht",
    )
    
    delete_old_changes(db, admin.site_id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin '{admin.username}' deleted admin '{deleted_username}' from site {admin.site_id}")
