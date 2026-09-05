"""Admin content editing routes for WebsiteCMS.

This module provides API endpoints for in-place content editing:
- Text field updates
- Array field operations (add/remove/reorder)
- Undo functionality
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from app.middleware.auth import require_auth, get_site_from_request
from app.models.content import SiteContent
from app.models.site import AdminUser, Site
from app.models.site_config import SiteConfig
from app.utils.history import record_change, get_last_change, delete_old_changes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-content"])


# ============================================
# Request/Response Models
# ============================================

class ContentUpdateRequest(BaseModel):
    """Request body for updating a content field."""
    
    field: str = Field(..., min_length=1, max_length=100, description="Field name to update (e.g., 'hero_headline')")
    value: Any = Field(..., description="New value for the field")
    subfield: Optional[str] = Field(None, max_length=100, description="Subfield for array items (e.g., 'title')")
    index: Optional[int] = Field(None, ge=0, description="Index for array items")
    
    @field_validator("field")
    @classmethod
    def validate_field_name(cls, v: str) -> str:
        """Validate field name contains only safe characters."""
        if not re.match(r"^[a-z_]+$", v):
            raise ValueError("Field name must contain only lowercase letters and underscores")
        return v
    
    @field_validator("subfield")
    @classmethod
    def validate_subfield_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate subfield name contains only safe characters."""
        if v is not None and not re.match(r"^[a-z_]+$", v):
            raise ValueError("Subfield name must contain only lowercase letters and underscores")
        return v


class ContentUpdateResponse(BaseModel):
    """Response body for content updates."""
    
    status: str = "success"
    field: str
    value: Any
    message: Optional[str] = None


class ArrayItemAddRequest(BaseModel):
    """Request body for adding an item to an array field."""
    
    field: str = Field(..., min_length=1, max_length=100)
    item: Dict[str, Any] = Field(default_factory=dict, description="Item data (will use defaults if empty)")


class ArrayItemRemoveRequest(BaseModel):
    """Request body for removing an item from an array field."""
    
    field: str = Field(..., min_length=1, max_length=100)
    index: int = Field(..., ge=0, description="Index of item to remove")


class ArrayReorderRequest(BaseModel):
    """Request body for reordering array items."""
    
    field: str = Field(..., min_length=1, max_length=100)
    order: List[int] = Field(..., min_length=1, description="New order as list of indices")


class UndoResponse(BaseModel):
    """Response body for undo operation."""
    
    status: str
    message: str
    undone_field: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response body."""
    
    error: str
    message: str


# ============================================
# Field Mapping
# ============================================

# Mapping of field names to their module types
FIELD_MODULE_MAP = {
    # Hero fields
    "hero_headline": "hero",
    "hero_cta_text": "hero",
    "hero_cta_target": "hero",
    "hero_bg_image": "hero",
    # Trust fields
    "trust_images": "trust",
    "testimonials": "trust",
    "review_source_url": "trust",
    "review_source_text": "trust",
    # Services fields
    "services": "services",
    # About fields
    "about_blocks": "about",
    # Repertoire fields
    "repertoire_intro": "repertoire",
    "repertoire_entries": "repertoire",
    # Media fields
    "media_blocks": "media",
    # FAQ fields
    "faq_items": "faq",
    # Contact fields
    "contact_phone": "contact",
    "contact_email": "contact",
    "contact_address": "contact",
    "contact_maps_link": "contact",
    # Footer fields
    "footer_social_links": "footer",
    # Legal pages
    "impressum_content": "legal",
    "datenschutz_content": "legal",
}

# Array fields that support add/remove/reorder
ARRAY_FIELDS = {
    "services",
    "testimonials",
    "trust_images",
    "about_blocks",
    "repertoire_entries",
    "media_blocks",
    "faq_items",
    "footer_social_links",
}

# Default templates for new array items
ARRAY_ITEM_DEFAULTS = {
    "services": {
        "title": "Neue Leistung",
        "description": "Beschreibung hinzufügen",
        "image": None,
        "icon": None,
    },
    "testimonials": {
        "quote": "Zitat hinzufügen",
        "author_name": "Name",
        "author_role": None,
    },
    "trust_images": {
        "src": "",
        "alt": "Bildbeschreibung",
    },
    "about_blocks": {
        "type": "text",
        "content": "Text hinzufügen",
    },
    "media_blocks": {
        "type": "text",
        "content": "Text hinzufügen",
    },
    "faq_items": {
        "question": "Neue Frage",
        "answer": "Antwort hinzufügen",
    },
    "footer_social_links": {
        "platform": "custom",
        "url": "https://",
        "label": "Link",
    },
}


# ============================================
# Helper Functions
# ============================================

def sanitize_text(value: str) -> str:
    """Sanitize text input to prevent XSS.
    
    Args:
        value: Raw text input.
        
    Returns:
        Sanitized text with HTML entities escaped.
    """
    # Strip any HTML tags
    value = re.sub(r"<[^>]+>", "", value)
    # Escape HTML entities
    value = html.escape(value)
    # Normalize whitespace
    value = " ".join(value.split())
    return value.strip()


def sanitize_rich_text(value: str) -> str:
    """Sanitize rich text, allowing basic formatting.
    
    Args:
        value: Rich text input.
        
    Returns:
        Sanitized text with only safe HTML allowed.
    """
    # Allow only specific tags
    allowed_tags = {"p", "br", "b", "strong", "i", "em", "a", "ul", "ol", "li", "h2", "h3"}
    
    # For now, just escape everything - rich text editing will be more complex
    # In production, use a library like bleach
    return html.escape(value).strip()


def get_site_for_admin(admin: AdminUser, db: Session) -> Site:
    """Get the site for an admin user.
    
    Args:
        admin: The admin user.
        db: Database session.
        
    Returns:
        The site the admin belongs to.
        
    Raises:
        HTTPException: If site not found.
    """
    site = db.query(Site).filter(Site.id == admin.site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Website nicht gefunden"},
        )
    return site


def get_content_for_site(site: Site, db: Session) -> SiteContent:
    """Get content for a site.
    
    Args:
        site: The site.
        db: Database session.
        
    Returns:
        The site content.
        
    Raises:
        HTTPException: If content not found.
    """
    content = db.query(SiteContent).filter(SiteContent.site_id == site.id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Inhalt nicht gefunden"},
        )
    return content


# ============================================
# Content Update Endpoints
# ============================================

@router.post(
    "/content",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Field not found"},
    },
)
async def update_content_field(
    request: ContentUpdateRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Update a content field with auto-save.
    
    This endpoint handles in-place text editing for all content fields.
    Changes are recorded in history for undo functionality.
    
    Args:
        request: Update request with field name and new value.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with the saved value.
    """
    # Get site and content
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    field_name = request.field
    new_value = request.value
    
    # Validate field exists
    if field_name not in FIELD_MODULE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Unbekanntes Feld: {field_name}"},
        )
    
    # Check if field exists on content model
    if not hasattr(content, field_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Feld nicht gefunden: {field_name}"},
        )
    
    # Get the old value
    old_value = getattr(content, field_name)
    
    # Handle array item updates
    if request.index is not None and field_name in ARRAY_FIELDS:
        return await update_array_item(
            content=content,
            site=site,
            admin=admin,
            field_name=field_name,
            index=request.index,
            subfield=request.subfield,
            new_value=new_value,
            db=db,
        )
    
    # Sanitize text values
    if isinstance(new_value, str):
        if field_name in ("impressum_content", "datenschutz_content"):
            new_value = sanitize_rich_text(new_value)
        else:
            new_value = sanitize_text(new_value)
    
    # Update the field
    setattr(content, field_name, new_value)
    
    # Record the change in history
    module_type = FIELD_MODULE_MAP[field_name]
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    )
    
    # Cleanup old changes (keep last 50)
    delete_old_changes(db, site.id, keep_count=50)
    
    db.commit()
    
    logger.info(f"Admin {admin.username} updated {field_name} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field=field_name,
        value=new_value,
        message="Gespeichert",
    )


async def update_array_item(
    content: SiteContent,
    site: Site,
    admin: AdminUser,
    field_name: str,
    index: int,
    subfield: Optional[str],
    new_value: Any,
    db: Session,
) -> ContentUpdateResponse:
    """Update a specific item in an array field.
    
    Args:
        content: Site content model.
        site: Site model.
        admin: Admin user.
        field_name: Name of the array field.
        index: Index of the item to update.
        subfield: Subfield within the item to update.
        new_value: New value.
        db: Database session.
        
    Returns:
        Update response.
    """
    # Get the array
    array = getattr(content, field_name)
    if not array:
        array = []
    
    # Validate index
    if index < 0 or index >= len(array):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Ungültiger Index: {index}"},
        )
    
    # Store old value for history
    old_item = array[index].copy() if isinstance(array[index], dict) else array[index]
    
    # Update the item
    if subfield:
        if not isinstance(array[index], dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "validation_error", "message": "Element ist kein Objekt"},
            )
        
        # Sanitize text values
        if isinstance(new_value, str):
            new_value = sanitize_text(new_value)
        
        old_subfield_value = array[index].get(subfield)
        array[index][subfield] = new_value
    else:
        # Replace entire item
        if isinstance(new_value, str):
            new_value = sanitize_text(new_value)
        array[index] = new_value
    
    # Update the field (JSON fields need explicit assignment to trigger update)
    setattr(content, field_name, array)
    flag_modified(content, field_name)  # Mark JSON column as modified
    
    # Record the change
    module_type = FIELD_MODULE_MAP[field_name]
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=f"{field_name}[{index}]" + (f".{subfield}" if subfield else ""),
        old_value=old_subfield_value if subfield else old_item,
        new_value=new_value,
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    return ContentUpdateResponse(
        status="success",
        field=f"{field_name}[{index}]" + (f".{subfield}" if subfield else ""),
        value=new_value,
        message="Gespeichert",
    )


@router.post(
    "/content/add",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def add_array_item(
    request: ArrayItemAddRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Add a new item to an array field.
    
    Args:
        request: Add request with field name and optional item data.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with the new array.
    """
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    field_name = request.field
    
    # Validate it's an array field
    if field_name not in ARRAY_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Kein Array-Feld: {field_name}"},
        )
    
    # Get current array
    array = getattr(content, field_name)
    if array is None:
        array = []
    
    old_array = list(array)  # Copy for history
    
    # Create new item with defaults
    defaults = ARRAY_ITEM_DEFAULTS.get(field_name, {})
    new_item = {**defaults, **request.item}
    
    # Sanitize text fields in new item
    for key, value in new_item.items():
        if isinstance(value, str):
            new_item[key] = sanitize_text(value)
    
    # Add to array
    array.append(new_item)
    setattr(content, field_name, array)
    flag_modified(content, field_name)  # Mark JSON column as modified
    
    # Record change
    module_type = FIELD_MODULE_MAP.get(field_name, field_name)
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=field_name,
        old_value=old_array,
        new_value=array,
        description=f"Element hinzugefügt zu {field_name}",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} added item to {field_name} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field=field_name,
        value=array,
        message="Element hinzugefügt",
    )


@router.post(
    "/content/remove",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def remove_array_item(
    request: ArrayItemRemoveRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Remove an item from an array field.
    
    Args:
        request: Remove request with field name and index.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with the updated array.
    """
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    field_name = request.field
    index = request.index
    
    # Validate it's an array field
    if field_name not in ARRAY_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Kein Array-Feld: {field_name}"},
        )
    
    # Get current array
    array = getattr(content, field_name)
    if not array or index >= len(array):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Ungültiger Index: {index}"},
        )
    
    old_array = list(array)  # Copy for history
    removed_item = array[index]
    
    # Remove item
    array.pop(index)
    setattr(content, field_name, array)
    flag_modified(content, field_name)  # Mark JSON column as modified
    
    # Record change
    module_type = FIELD_MODULE_MAP.get(field_name, field_name)
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=field_name,
        old_value=old_array,
        new_value=array,
        description=f"Element entfernt aus {field_name}",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} removed item from {field_name} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field=field_name,
        value=array,
        message="Element entfernt",
    )


@router.post(
    "/content/reorder",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def reorder_array_items(
    request: ArrayReorderRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Reorder items in an array field.
    
    Args:
        request: Reorder request with field name and new order.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with the reordered array.
    """
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    field_name = request.field
    new_order = request.order
    
    # Validate it's an array field
    if field_name not in ARRAY_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Kein Array-Feld: {field_name}"},
        )
    
    # Get current array
    array = getattr(content, field_name)
    if not array:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Feld ist leer"},
        )
    
    # Validate order contains all valid indices
    if sorted(new_order) != list(range(len(array))):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Ungültige Reihenfolge"},
        )
    
    old_array = list(array)  # Copy for history
    
    # Reorder
    reordered = [array[i] for i in new_order]
    setattr(content, field_name, reordered)
    flag_modified(content, field_name)  # Mark JSON column as modified
    
    # Record change
    module_type = FIELD_MODULE_MAP.get(field_name, field_name)
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=field_name,
        old_value=old_array,
        new_value=reordered,
        description=f"Reihenfolge geändert in {field_name}",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} reordered {field_name} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field=field_name,
        value=reordered,
        message="Reihenfolge gespeichert",
    )


# ============================================
# Undo Endpoint
# ============================================

@router.post(
    "/undo",
    response_model=UndoResponse,
    responses={
        400: {"model": ErrorResponse, "description": "No changes to undo"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def undo_last_change(
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> UndoResponse:
    """Undo the last content change.
    
    Args:
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Undo response with status and undone field name.
    """
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    # Get the most recent change
    last_change = get_last_change(db, site.id)
    
    if not last_change:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "no_changes", "message": "Keine Änderungen zum Rückgängigmachen"},
        )
    
    # Extract field name (handle array notation like "services[0].title")
    field_name = last_change.field_name
    base_field = field_name.split("[")[0]
    
    # Check if this is an array item change
    array_match = re.match(r"^([a-z_]+)\[(\d+)\](?:\.([a-z_]+))?$", field_name)
    
    if array_match:
        # Array item change - restore old value
        base_field, index_str, subfield = array_match.groups()
        index = int(index_str)
        
        if hasattr(content, base_field):
            array = getattr(content, base_field)
            if array and index < len(array):
                if subfield:
                    # Restore subfield value
                    if isinstance(array[index], dict):
                        array[index][subfield] = last_change.old_value
                else:
                    # Restore entire item
                    array[index] = last_change.old_value
                setattr(content, base_field, array)
    elif hasattr(content, base_field):
        # Simple field change - restore old value
        setattr(content, base_field, last_change.old_value)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "field_not_found", "message": f"Feld nicht gefunden: {base_field}"},
        )
    
    # Delete the change record
    db.delete(last_change)
    db.commit()
    
    logger.info(f"Admin {admin.username} undid change to {field_name} on site {site.domain}")
    
    return UndoResponse(
        status="success",
        message="Änderung rückgängig gemacht",
        undone_field=field_name,
    )


# ============================================
# Module Toggle Endpoint
# ============================================

class ModuleToggleRequest(BaseModel):
    """Request body for toggling a module."""
    
    module: str = Field(..., min_length=1, max_length=50)
    enabled: bool


@router.post(
    "/module/toggle",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def toggle_module(
    request: ModuleToggleRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Toggle a module's enabled state.
    
    Args:
        request: Toggle request with module name and enabled state.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response.
    """
    site = get_site_for_admin(admin, db)
    
    # Get site config
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    module_name = request.module
    
    # Check if module is available (not excluded)
    current_state = config.module_states.get(module_name)
    if current_state == "excluded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Modul nicht verfügbar: {module_name}"},
        )
    
    if current_state is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Unbekanntes Modul: {module_name}"},
        )
    
    # Update state
    old_states = dict(config.module_states)
    new_state = "enabled" if request.enabled else "available"
    config.module_states = {**config.module_states, module_name: new_state}
    
    # Record change
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="module_states",
        old_value=old_states,
        new_value=config.module_states,
        description=f"Modul {module_name} {'aktiviert' if request.enabled else 'deaktiviert'}",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} toggled {module_name} to {new_state} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="module_states",
        value=config.module_states,
        message=f"Modul {'aktiviert' if request.enabled else 'deaktiviert'}",
    )


# ============================================
# Module Reorder Endpoint
# ============================================

class ModuleReorderRequest(BaseModel):
    """Request body for reordering modules."""
    
    order: List[str] = Field(..., min_length=1)


@router.post(
    "/module/reorder",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def reorder_modules(
    request: ModuleReorderRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Reorder modules on the page.
    
    Args:
        request: Reorder request with new module order.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response.
    """
    site = get_site_for_admin(admin, db)
    
    # Get site config
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    # Validate all modules in new order exist
    current_modules = set(config.module_order)
    new_modules = set(request.order)
    
    logger.info(f"Reorder request - current: {config.module_order}, new: {request.order}")
    logger.info(f"Current set: {current_modules}, New set: {new_modules}")
    
    if current_modules != new_modules:
        logger.warning(f"Module mismatch - missing: {current_modules - new_modules}, extra: {new_modules - current_modules}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Ungültige Modulliste. Erwartet: {list(current_modules)}, Erhalten: {list(new_modules)}"},
        )
    
    old_order = list(config.module_order)
    config.module_order = request.order
    
    # Record change
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="module_order",
        old_value=old_order,
        new_value=request.order,
        description="Modulreihenfolge geändert",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} reordered modules on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="module_order",
        value=config.module_order,
        message="Reihenfolge gespeichert",
    )


# ============================================
# Nav Label Endpoints
# ============================================

class NavLabelUpdateRequest(BaseModel):
    """Request body for updating a navigation label."""
    
    module: str = Field(..., min_length=1, max_length=50, description="Module name (e.g., 'services')")
    label: str = Field(..., max_length=50, description="New nav label (empty string to reset)")
    
    @field_validator("module")
    @classmethod
    def validate_module_name(cls, v: str) -> str:
        """Validate module name contains only safe characters."""
        if not re.match(r"^[a-z_]+$", v):
            raise ValueError("Module name must contain only lowercase letters and underscores")
        return v


@router.put(
    "/config/nav-labels",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def update_nav_label(
    request: NavLabelUpdateRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Update a navigation label for a module.
    
    Args:
        request: Nav label update request with module name and new label.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with new nav labels.
    """
    site = get_site_for_admin(admin, db)
    
    # Get site config
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    # Validate module exists in module_order
    if request.module not in config.module_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Unbekanntes Modul: {request.module}"},
        )
    
    old_labels = dict(config.nav_labels) if config.nav_labels else {}
    new_labels = dict(old_labels)
    
    # If label is empty or only whitespace, remove custom label (revert to default)
    if not request.label.strip():
        if request.module in new_labels:
            del new_labels[request.module]
    else:
        # Sanitize the label
        sanitized_label = html.escape(request.label.strip())
        new_labels[request.module] = sanitized_label
    
    config.nav_labels = new_labels
    
    # Record change for undo
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="nav_labels",
        old_value=old_labels,
        new_value=new_labels,
        description=f"Navigation Label für '{request.module}' geändert",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} updated nav label for {request.module} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="nav_labels",
        value=config.nav_labels,
        message="Navigation Label gespeichert",
    )


@router.delete(
    "/config/nav-labels/{module}",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def delete_nav_label(
    module: str,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Delete a custom navigation label (revert to default).
    
    Args:
        module: Module name to delete custom label for.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with updated nav labels.
    """
    # Validate module name
    if not re.match(r"^[a-z_]+$", module):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Ungültiger Modulname"},
        )
    
    site = get_site_for_admin(admin, db)
    
    # Get site config
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    old_labels = dict(config.nav_labels) if config.nav_labels else {}
    
    # If the module doesn't have a custom label, nothing to do
    if module not in old_labels:
        return ContentUpdateResponse(
            status="success",
            field="nav_labels",
            value=config.nav_labels or {},
            message="Kein benutzerdefiniertes Label vorhanden",
        )
    
    new_labels = dict(old_labels)
    del new_labels[module]
    config.nav_labels = new_labels
    
    # Record change for undo
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="nav_labels",
        old_value=old_labels,
        new_value=new_labels,
        description=f"Navigation Label für '{module}' zurückgesetzt",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} deleted nav label for {module} on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="nav_labels",
        value=config.nav_labels,
        message="Navigation Label zurückgesetzt",
    )


# ============================================
# Logo & Favicon Endpoints
# ============================================

class LogoFaviconUpdateRequest(BaseModel):
    """Request body for updating logo or favicon via file_id."""
    
    file_id: str = Field(..., min_length=1, max_length=100, description="Uploaded file ID")


@router.put(
    "/config/logo",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def update_logo(
    request: LogoFaviconUpdateRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Update the site logo.
    
    Args:
        request: Request with file_id from upload.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with new logo path.
    """
    from app.utils.image_processing import get_default_src
    
    site = get_site_for_admin(admin, db)
    
    # Get site config
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    # Get the image URL from file_id
    logo_url = get_default_src(request.file_id)
    
    old_logo = config.logo_image
    config.logo_image = logo_url
    
    # Record change for undo
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="logo_image",
        old_value=old_logo,
        new_value=logo_url,
        description="Logo geändert",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} updated logo on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="logo_image",
        value=logo_url,
        message="Logo gespeichert",
    )


@router.delete(
    "/config/logo",
    response_model=ContentUpdateResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def delete_logo(
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Remove the site logo (revert to text logo).
    
    Args:
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response.
    """
    site = get_site_for_admin(admin, db)
    
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    old_logo = config.logo_image
    config.logo_image = None
    
    # Record change for undo
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="logo_image",
        old_value=old_logo,
        new_value=None,
        description="Logo entfernt",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} removed logo on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="logo_image",
        value=None,
        message="Logo entfernt",
    )


@router.put(
    "/config/favicon",
    response_model=ContentUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def update_favicon(
    request: LogoFaviconUpdateRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Update the site favicon.
    
    Args:
        request: Request with file_id from upload.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response with new favicon path.
    """
    from app.utils.image_processing import get_default_src
    
    site = get_site_for_admin(admin, db)
    
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    # Get the image URL from file_id
    favicon_url = get_default_src(request.file_id)
    
    old_favicon = config.favicon_image
    config.favicon_image = favicon_url
    
    # Record change for undo
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="favicon_image",
        old_value=old_favicon,
        new_value=favicon_url,
        description="Favicon geändert",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} updated favicon on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="favicon_image",
        value=favicon_url,
        message="Favicon gespeichert",
    )


@router.delete(
    "/config/favicon",
    response_model=ContentUpdateResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def delete_favicon(
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ContentUpdateResponse:
    """Remove the site favicon (revert to default).
    
    Args:
        admin: Current admin user.
        db: Database session.
        
    Returns:
        Update response.
    """
    site = get_site_for_admin(admin, db)
    
    config = db.query(SiteConfig).filter(SiteConfig.site_id == site.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Konfiguration nicht gefunden"},
        )
    
    old_favicon = config.favicon_image
    config.favicon_image = None
    
    # Record change for undo
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type="config",
        field_name="favicon_image",
        old_value=old_favicon,
        new_value=None,
        description="Favicon entfernt",
    )
    
    delete_old_changes(db, site.id, keep_count=50)
    db.commit()
    
    logger.info(f"Admin {admin.username} removed favicon on site {site.domain}")
    
    return ContentUpdateResponse(
        status="success",
        field="favicon_image",
        value=None,
        message="Favicon entfernt",
    )
