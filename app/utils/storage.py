"""Storage utilities for file handling.

This module provides utilities for managing file storage,
including uploads directory management and file ID generation.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Base data directory (can be overridden via environment)
DEFAULT_DATA_DIR = "data"
DEFAULT_UPLOAD_DIR = "uploads"
DEFAULT_TEMP_DIR = "temp"


def get_data_dir() -> Path:
    """Get the base data directory.
    
    Returns:
        Path to the data directory.
    """
    data_dir = os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_upload_dir() -> Path:
    """Get the uploads directory.
    
    Returns:
        Path to the uploads directory.
    """
    upload_dir = os.environ.get("UPLOAD_DIR")
    if upload_dir:
        path = Path(upload_dir)
    else:
        path = get_data_dir() / DEFAULT_UPLOAD_DIR
    
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_temp_dir() -> Path:
    """Get the temporary files directory.
    
    Returns:
        Path to the temp directory.
    """
    temp_dir = os.environ.get("TEMP_DIR")
    if temp_dir:
        path = Path(temp_dir)
    else:
        path = get_data_dir() / DEFAULT_TEMP_DIR
    
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_trash_dir() -> Path:
    """Get the trash directory for soft-deleted images.
    
    Returns:
        Path to the trash directory.
    """
    path = get_data_dir() / "trash"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_file_id() -> str:
    """Generate a unique, safe filename ID.
    
    Returns:
        A UUID-based file ID.
    """
    return str(uuid.uuid4())


def get_image_path(file_id: str, size: str) -> Path:
    """Get the path for an optimized image.
    
    Args:
        file_id: The unique file ID.
        size: The image size suffix (e.g., "2400w", "960w", "400w").
        
    Returns:
        Full path to the image file.
    """
    return get_upload_dir() / f"{file_id}_{size}.webp"


def get_all_image_sizes(file_id: str) -> list[Path]:
    """Get paths for all sizes of an image.
    
    Args:
        file_id: The unique file ID.
        
    Returns:
        List of paths for all image sizes.
    """
    sizes = ["2400w", "960w", "400w"]
    return [get_image_path(file_id, size) for size in sizes]


def image_exists(file_id: str) -> bool:
    """Check if an image with the given ID exists (any size).
    
    Args:
        file_id: The unique file ID.
        
    Returns:
        True if at least one size exists.
    """
    paths = get_all_image_sizes(file_id)
    return any(path.exists() for path in paths)


def delete_image(file_id: str, soft_delete: bool = True) -> bool:
    """Delete an image and all its sizes.
    
    Args:
        file_id: The unique file ID.
        soft_delete: If True, move to trash instead of deleting.
        
    Returns:
        True if any files were deleted/moved.
    """
    paths = get_all_image_sizes(file_id)
    deleted = False
    
    for path in paths:
        if path.exists():
            if soft_delete:
                trash_path = get_trash_dir() / path.name
                try:
                    shutil.move(str(path), str(trash_path))
                    logger.info(f"Moved {path} to trash")
                    deleted = True
                except Exception as e:
                    logger.error(f"Failed to move {path} to trash: {e}")
            else:
                try:
                    path.unlink()
                    logger.info(f"Deleted {path}")
                    deleted = True
                except Exception as e:
                    logger.error(f"Failed to delete {path}: {e}")
    
    return deleted


def cleanup_temp_files(max_age_hours: int = 24) -> int:
    """Clean up old temporary files.
    
    Args:
        max_age_hours: Maximum age of temp files before deletion.
        
    Returns:
        Number of files cleaned up.
    """
    import time
    
    temp_dir = get_temp_dir()
    max_age_seconds = max_age_hours * 3600
    now = time.time()
    count = 0
    
    for path in temp_dir.iterdir():
        if path.is_file():
            age = now - path.stat().st_mtime
            if age > max_age_seconds:
                try:
                    path.unlink()
                    count += 1
                    logger.debug(f"Cleaned up temp file: {path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {path}: {e}")
    
    if count > 0:
        logger.info(f"Cleaned up {count} temporary files")
    
    return count


def cleanup_trash(max_age_hours: int = 168) -> int:
    """Clean up old files from trash (default: 7 days).
    
    Args:
        max_age_hours: Maximum age of trash files before permanent deletion.
        
    Returns:
        Number of files cleaned up.
    """
    import time
    
    trash_dir = get_trash_dir()
    max_age_seconds = max_age_hours * 3600
    now = time.time()
    count = 0
    
    for path in trash_dir.iterdir():
        if path.is_file():
            age = now - path.stat().st_mtime
            if age > max_age_seconds:
                try:
                    path.unlink()
                    count += 1
                    logger.debug(f"Permanently deleted from trash: {path}")
                except Exception as e:
                    logger.warning(f"Failed to delete trash file {path}: {e}")
    
    if count > 0:
        logger.info(f"Permanently deleted {count} files from trash")
    
    return count


def ensure_directories() -> None:
    """Ensure all required directories exist.
    
    Called during application startup.
    """
    get_data_dir()
    get_upload_dir()
    get_temp_dir()
    get_trash_dir()
    logger.info("Storage directories initialized")
