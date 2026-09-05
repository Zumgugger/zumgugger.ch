"""Image cleanup utilities for WebsiteCMS.

This module provides functionality to clean up orphaned images:
- Images that are no longer referenced in content
- Images that have been pushed out of undo history
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import SiteContent
from app.models.history import ContentChange
from app.utils.image_processing import extract_file_id_from_path
from app.utils.storage import (
    delete_image,
    get_upload_dir,
    image_exists,
)

logger = logging.getLogger(__name__)


def get_referenced_file_ids_from_content(content: SiteContent) -> Set[str]:
    """Extract all file IDs referenced in site content.
    
    Args:
        content: Site content model.
        
    Returns:
        Set of file IDs.
    """
    file_ids = set()
    
    # Hero background image
    if content.hero_bg_image:
        file_id = extract_file_id_from_path(content.hero_bg_image)
        if file_id:
            file_ids.add(file_id)
    
    # Trust images
    for item in content.trust_images or []:
        if isinstance(item, dict):
            src = item.get("src") or item.get("image")
            if src:
                file_id = extract_file_id_from_path(src)
                if file_id:
                    file_ids.add(file_id)
            # Check for file_id directly
            if item.get("file_id"):
                file_ids.add(item["file_id"])
    
    # Services images
    for item in content.services or []:
        if isinstance(item, dict):
            src = item.get("image")
            if src:
                file_id = extract_file_id_from_path(src)
                if file_id:
                    file_ids.add(file_id)
            if item.get("file_id"):
                file_ids.add(item["file_id"])
    
    # About blocks (images and galleries)
    for block in content.about_blocks or []:
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type == "image":
                src = block.get("src") or block.get("image")
                if src:
                    file_id = extract_file_id_from_path(src)
                    if file_id:
                        file_ids.add(file_id)
                if block.get("file_id"):
                    file_ids.add(block["file_id"])
            elif block_type == "gallery":
                for image in block.get("images", []):
                    if isinstance(image, dict):
                        src = image.get("src") or image.get("image")
                        if src:
                            file_id = extract_file_id_from_path(src)
                            if file_id:
                                file_ids.add(file_id)
                        if image.get("file_id"):
                            file_ids.add(image["file_id"])
    
    # Media blocks
    for block in content.media_blocks or []:
        if isinstance(block, dict):
            block_type = block.get("type")
            if block_type == "image":
                src = block.get("src") or block.get("image")
                if src:
                    file_id = extract_file_id_from_path(src)
                    if file_id:
                        file_ids.add(file_id)
                if block.get("file_id"):
                    file_ids.add(block["file_id"])
            elif block_type == "gallery":
                for image in block.get("images", []):
                    if isinstance(image, dict):
                        src = image.get("src") or image.get("image")
                        if src:
                            file_id = extract_file_id_from_path(src)
                            if file_id:
                                file_ids.add(file_id)
                        if image.get("file_id"):
                            file_ids.add(image["file_id"])
    
    return file_ids


def get_referenced_file_ids_from_history(
    db: Session,
    site_id: int,
) -> Set[str]:
    """Extract all file IDs referenced in content change history.
    
    Args:
        db: Database session.
        site_id: Site ID.
        
    Returns:
        Set of file IDs.
    """
    file_ids = set()
    
    # Query all history changes for this site
    changes = db.query(ContentChange).filter(
        ContentChange.site_id == site_id
    ).all()
    
    for change in changes:
        # Check old_value
        if change.old_value:
            _extract_file_ids_from_value(change.old_value, file_ids)
        
        # Check new_value
        if change.new_value:
            _extract_file_ids_from_value(change.new_value, file_ids)
    
    return file_ids


def _extract_file_ids_from_value(value, file_ids: Set[str]) -> None:
    """Extract file IDs from a history value.
    
    Args:
        value: The value to check (could be string, dict, or list).
        file_ids: Set to add found file IDs to.
    """
    if isinstance(value, str):
        file_id = extract_file_id_from_path(value)
        if file_id:
            file_ids.add(file_id)
    elif isinstance(value, dict):
        # Check common image fields
        for key in ("image", "src", "bg_image", "file_id"):
            if key in value:
                if key == "file_id":
                    file_ids.add(value[key])
                elif isinstance(value[key], str):
                    file_id = extract_file_id_from_path(value[key])
                    if file_id:
                        file_ids.add(file_id)
        # Recurse into dict values
        for v in value.values():
            _extract_file_ids_from_value(v, file_ids)
    elif isinstance(value, list):
        for item in value:
            _extract_file_ids_from_value(item, file_ids)


def get_all_uploaded_file_ids() -> Set[str]:
    """Get all file IDs in the uploads directory.
    
    Returns:
        Set of file IDs.
    """
    file_ids = set()
    upload_dir = get_upload_dir()
    
    for path in upload_dir.iterdir():
        if path.is_file() and path.suffix == ".webp":
            # Extract file ID from filename
            file_id = extract_file_id_from_path(path.name)
            if file_id:
                file_ids.add(file_id)
    
    return file_ids


def cleanup_orphaned_images(
    db: Session,
    site_id: int,
    soft_delete: bool = True,
) -> List[str]:
    """Clean up images that are no longer referenced.
    
    An image is orphaned if:
    - It's not referenced in the current site content
    - It's not referenced in any undo history record
    
    Args:
        db: Database session.
        site_id: Site ID.
        soft_delete: If True, move to trash instead of deleting.
        
    Returns:
        List of deleted file IDs.
    """
    # Get content for the site
    content = db.query(SiteContent).filter(SiteContent.site_id == site_id).first()
    if not content:
        logger.warning(f"No content found for site {site_id}")
        return []
    
    # Get all referenced file IDs
    content_file_ids = get_referenced_file_ids_from_content(content)
    history_file_ids = get_referenced_file_ids_from_history(db, site_id)
    
    # Combine all referenced IDs
    all_referenced = content_file_ids | history_file_ids
    
    # Get all uploaded file IDs
    uploaded_file_ids = get_all_uploaded_file_ids()
    
    # Find orphaned images
    orphaned = uploaded_file_ids - all_referenced
    
    # Delete orphaned images
    deleted = []
    for file_id in orphaned:
        if delete_image(file_id, soft_delete=soft_delete):
            deleted.append(file_id)
            logger.info(f"Cleaned up orphaned image: {file_id}")
    
    if deleted:
        logger.info(f"Cleaned up {len(deleted)} orphaned images for site {site_id}")
    
    return deleted


def cleanup_images_for_expired_history(
    db: Session,
    site_id: int,
    keep_count: int = 50,
    soft_delete: bool = True,
) -> List[str]:
    """Clean up images from changes that will be pushed out of history.
    
    This is called after deleting old history records. It identifies
    images that were only referenced in the deleted history and
    removes them if they're not used elsewhere.
    
    Args:
        db: Database session.
        site_id: Site ID.
        keep_count: Number of history records to keep.
        soft_delete: If True, move to trash instead of deleting.
        
    Returns:
        List of cleaned up file IDs.
    """
    # This is essentially the same as cleanup_orphaned_images
    # since after history deletion, orphaned images are those
    # not in content or remaining history
    return cleanup_orphaned_images(db, site_id, soft_delete=soft_delete)


def schedule_image_cleanup(
    db: Session,
    site_id: int,
    old_image_path: Optional[str] = None,
) -> None:
    """Schedule an image for potential cleanup.
    
    This is called when an image is replaced. The old image
    will be cleaned up after it's pushed out of undo history.
    
    Args:
        db: Database session.
        site_id: Site ID.
        old_image_path: Path to the old image.
    """
    # For now, we don't need to do anything special here
    # The image will be cleaned up when it's no longer
    # referenced in content or history
    if old_image_path:
        file_id = extract_file_id_from_path(old_image_path)
        if file_id:
            logger.debug(
                f"Image {file_id} scheduled for cleanup when pushed out of history"
            )
