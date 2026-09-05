"""Image upload and serving routes for WebsiteCMS.

This module provides API endpoints for:
- Image upload with validation
- Image optimization
- Image serving with caching
- Image field updates
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_auth, get_optional_admin
from app.models.content import SiteContent
from app.models.site import AdminUser, Site
from app.utils.history import record_change
from app.utils.image_processing import (
    ImageProcessingError,
    ImageValidationError,
    MAX_FILE_SIZE,
    SUPPORTED_MIME_TYPES,
    get_default_src,
    get_image_urls,
    get_srcset,
    optimize_image,
    validate_content_type,
    extract_file_id_from_path,
)
from app.utils.storage import (
    generate_file_id,
    get_image_path,
    get_temp_dir,
    get_upload_dir,
    image_exists,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["images"])

# Maximum upload size from environment (default 5MB)
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "5"))
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ============================================
# Request/Response Models
# ============================================

class ImageUploadResponse(BaseModel):
    """Response for successful image upload."""
    
    status: str = "success"
    file_id: str = Field(..., description="Unique identifier for the uploaded image")
    urls: Dict[str, str] = Field(..., description="URLs for each image size")
    srcset: str = Field(..., description="HTML srcset attribute value")
    default_src: str = Field(..., description="Default (medium) size URL")


class ImageFieldUpdateRequest(BaseModel):
    """Request for updating an image field."""
    
    file_id: str = Field(..., description="File ID from upload response")


class ImageFieldUpdateResponse(BaseModel):
    """Response for image field update."""
    
    status: str = "success"
    field: str
    file_id: str
    urls: Dict[str, str]
    message: str = "Bild aktualisiert"


class ErrorResponse(BaseModel):
    """Error response body."""
    
    error: str
    message: str


# ============================================
# Helper Functions
# ============================================

def get_site_for_admin(admin: AdminUser, db: Session) -> Site:
    """Get the site for an admin user."""
    site = db.query(Site).filter(Site.id == admin.site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Website nicht gefunden"},
        )
    return site


def get_content_for_site(site: Site, db: Session) -> SiteContent:
    """Get content for a site."""
    content = db.query(SiteContent).filter(SiteContent.site_id == site.id).first()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Inhalt nicht gefunden"},
        )
    return content


# Image field mapping: field_name -> (module_type, is_array_field)
IMAGE_FIELD_MAP = {
    "hero_bg_image": ("hero", False),
    "trust_images": ("trust", True),
    "services": ("services", True),  # services[i].image
    "about_blocks": ("about", True),  # about_blocks[i] where type=image or gallery
    "media_blocks": ("media", True),  # media_blocks[i] where type=image or gallery
}


# ============================================
# Upload Endpoint
# ============================================

@router.post(
    "/api/admin/upload",
    response_model=ImageUploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload"),
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ImageUploadResponse:
    """Upload and optimize an image.
    
    Accepts JPEG, PNG, WebP, or GIF images up to 5MB.
    Returns optimized WebP images in 3 sizes (2400w, 960w, 400w).
    
    Args:
        file: The uploaded image file.
        admin: Current admin user (authenticated).
        db: Database session.
        
    Returns:
        ImageUploadResponse with file ID and URLs.
    """
    logger.info(f"Admin {admin.username} uploading image: {file.filename}")
    
    # Validate content type
    if not validate_content_type(file.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "message": f"Ungültiger Dateityp: {file.content_type}. "
                           f"Erlaubt: JPEG, PNG, WebP, GIF",
            },
        )
    
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "upload_error", "message": "Fehler beim Lesen der Datei"},
        )
    
    # Validate file size
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "error": "file_too_large",
                "message": f"Datei zu gross. Maximum: {MAX_UPLOAD_SIZE_MB}MB",
            },
        )
    
    # Generate file ID and save to temp location
    file_id = generate_file_id()
    
    # Determine extension from content type
    extension_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    extension = extension_map.get(file.content_type, ".jpg")
    
    temp_dir = get_temp_dir()
    temp_path = temp_dir / f"{file_id}{extension}"
    
    try:
        # Write to temp file
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Optimize the image
        output_paths = optimize_image(
            source_path=temp_path,
            file_id=file_id,
        )
        
        # Generate URLs
        urls = get_image_urls(file_id)
        srcset = get_srcset(file_id)
        default_src = get_default_src(file_id)
        
        logger.info(f"Image uploaded successfully: {file_id}")
        
        return ImageUploadResponse(
            status="success",
            file_id=file_id,
            urls=urls,
            srcset=srcset,
            default_src=default_src,
        )
        
    except ImageValidationError as e:
        logger.warning(f"Image validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": str(e)},
        )
    except ImageProcessingError as e:
        logger.error(f"Image processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "processing_error", "message": str(e)},
        )
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()


# ============================================
# Image Field Update Endpoint
# ============================================

@router.put(
    "/api/admin/content/image/{field_name}",
    response_model=ImageFieldUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Field not found"},
    },
)
async def update_image_field(
    field_name: str,
    request: ImageFieldUpdateRequest,
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ImageFieldUpdateResponse:
    """Update an image field with an uploaded image.
    
    Args:
        field_name: Name of the image field (e.g., "hero_bg_image").
        request: Request with file_id from upload.
        admin: Current admin user.
        db: Database session.
        
    Returns:
        ImageFieldUpdateResponse with updated URLs.
    """
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    # Validate field
    if field_name not in IMAGE_FIELD_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "message": f"Unbekanntes Bildfeld: {field_name}",
            },
        )
    
    module_type, is_array = IMAGE_FIELD_MAP[field_name]
    
    # Only handle simple (non-array) image fields here
    if is_array:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "message": "Für Array-Bildfelder verwenden Sie /api/admin/content/image/array",
            },
        )
    
    # Validate file exists
    if not image_exists(request.file_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Hochgeladenes Bild nicht gefunden"},
        )
    
    # Get the old value for history
    old_value = getattr(content, field_name)
    
    # Update the field with the default src
    new_value = get_default_src(request.file_id)
    setattr(content, field_name, new_value)
    
    # Record change with old image path for potential cleanup
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        description=f"Bild aktualisiert: {field_name}",
    )
    
    db.commit()
    
    logger.info(f"Admin {admin.username} updated image field {field_name}")
    
    return ImageFieldUpdateResponse(
        status="success",
        field=field_name,
        file_id=request.file_id,
        urls=get_image_urls(request.file_id),
        message="Bild aktualisiert",
    )


@router.put(
    "/api/admin/content/image/array/{field_name}/{index}",
    response_model=ImageFieldUpdateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Field or index not found"},
    },
)
async def update_array_image_field(
    field_name: str,
    index: int,
    request: ImageFieldUpdateRequest,
    subfield: str = "image",
    admin: AdminUser = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ImageFieldUpdateResponse:
    """Update an image within an array field.
    
    Args:
        field_name: Name of the array field (e.g., "services").
        index: Index of the item in the array.
        request: Request with file_id from upload.
        subfield: Name of the image subfield (default: "image").
        admin: Current admin user.
        db: Database session.
        
    Returns:
        ImageFieldUpdateResponse with updated URLs.
    """
    site = get_site_for_admin(admin, db)
    content = get_content_for_site(site, db)
    
    # Get the array field
    if not hasattr(content, field_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Feld nicht gefunden: {field_name}"},
        )
    
    array = getattr(content, field_name) or []
    
    # Validate index
    if index < 0 or index >= len(array):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": f"Ungültiger Index: {index}"},
        )
    
    # Validate file exists
    if not image_exists(request.file_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Hochgeladenes Bild nicht gefunden"},
        )
    
    # Get the old value for history
    item = array[index]
    if not isinstance(item, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Array-Element ist kein Objekt"},
        )
    
    old_value = item.get(subfield)
    
    # Update the image field
    new_value = get_default_src(request.file_id)
    array[index][subfield] = new_value
    
    # Also store the srcset if the item has that field
    if "srcset" in item or subfield == "image":
        array[index]["srcset"] = get_srcset(request.file_id)
        array[index]["file_id"] = request.file_id
    
    # Update the content (JSON fields need explicit assignment)
    setattr(content, field_name, array)
    
    # Determine module type
    module_type = IMAGE_FIELD_MAP.get(field_name, (field_name, True))[0]
    
    # Record change
    record_change(
        db=db,
        site_id=site.id,
        admin_user_id=admin.id,
        module_type=module_type,
        field_name=f"{field_name}[{index}].{subfield}",
        old_value=old_value,
        new_value=new_value,
        description=f"Bild aktualisiert: {field_name}[{index}]",
    )
    
    db.commit()
    
    logger.info(f"Admin {admin.username} updated array image {field_name}[{index}].{subfield}")
    
    return ImageFieldUpdateResponse(
        status="success",
        field=f"{field_name}[{index}].{subfield}",
        file_id=request.file_id,
        urls=get_image_urls(request.file_id),
        message="Bild aktualisiert",
    )


# ============================================
# Image Serving Endpoint
# ============================================

@router.get(
    "/uploads/{filename}",
    responses={
        200: {"content": {"image/webp": {}}},
        404: {"model": ErrorResponse, "description": "Image not found"},
    },
)
async def serve_image(
    filename: str,
    request: Request,
) -> Response:
    """Serve an optimized image.
    
    Args:
        filename: Image filename (e.g., "abc123_960w.webp").
        request: FastAPI request object.
        
    Returns:
        FileResponse with the image and cache headers.
    """
    # Security: validate filename format
    if not filename.endswith(".webp"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Bild nicht gefunden"},
        )
    
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_path", "message": "Ungültiger Dateipfad"},
        )
    
    # Get the full path
    upload_dir = get_upload_dir()
    file_path = upload_dir / filename
    
    # Check if file exists
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Bild nicht gefunden"},
        )
    
    # Return with cache headers
    # Since filenames include a unique ID, we can cache aggressively
    return FileResponse(
        path=file_path,
        media_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",  # 1 year
        },
    )
