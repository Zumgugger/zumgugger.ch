"""Image processing utilities for WebsiteCMS.

This module provides image optimization functionality:
- Accepts JPEG, PNG, WebP, GIF
- Converts to WebP format
- Generates 3 sizes: 2400w, 960w, 400w
- Quality: 80%
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, UnidentifiedImageError

from app.utils.storage import get_upload_dir, generate_file_id

logger = logging.getLogger(__name__)

# Supported input formats
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

# Output sizes (width in pixels)
OUTPUT_SIZES = {
    "2400w": 2400,  # Full size (for lightbox / high-res displays)
    "960w": 960,    # Medium size (for regular displays)
    "400w": 400,    # Thumbnail
}

# Output quality (0-100)
OUTPUT_QUALITY = 80

# Maximum file size (5 MB)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB in bytes


class ImageProcessingError(Exception):
    """Exception raised for image processing errors."""
    pass


class ImageValidationError(Exception):
    """Exception raised for image validation errors."""
    pass


def validate_image_file(
    file_path: Path,
    max_size: int = MAX_FILE_SIZE,
) -> Tuple[str, Tuple[int, int]]:
    """Validate an image file.
    
    Args:
        file_path: Path to the image file.
        max_size: Maximum file size in bytes.
        
    Returns:
        Tuple of (format_name, (width, height)).
        
    Raises:
        ImageValidationError: If validation fails.
    """
    # Check file exists
    if not file_path.exists():
        raise ImageValidationError(f"File not found: {file_path}")
    
    # Check file size
    file_size = file_path.stat().st_size
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        file_mb = file_size / (1024 * 1024)
        raise ImageValidationError(
            f"File size {file_mb:.1f}MB exceeds maximum {max_mb:.0f}MB"
        )
    
    # Check file extension
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ImageValidationError(
            f"Unsupported file type: {extension}. "
            f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    
    # Try to open and validate the image
    try:
        with Image.open(file_path) as img:
            format_name = img.format
            if format_name not in SUPPORTED_FORMATS:
                raise ImageValidationError(
                    f"Unsupported image format: {format_name}. "
                    f"Supported formats: {', '.join(SUPPORTED_FORMATS)}"
                )
            
            width, height = img.size
            if width < 1 or height < 1:
                raise ImageValidationError(f"Invalid image dimensions: {width}x{height}")
            
            return format_name, (width, height)
            
    except UnidentifiedImageError:
        raise ImageValidationError("Could not identify image format")
    except Exception as e:
        if isinstance(e, ImageValidationError):
            raise
        raise ImageValidationError(f"Failed to validate image: {str(e)}")


def validate_content_type(content_type: Optional[str]) -> bool:
    """Validate a MIME content type for images.
    
    Args:
        content_type: The MIME type to validate.
        
    Returns:
        True if the content type is supported.
    """
    if not content_type:
        return False
    # Handle content types with charset or other params
    mime_type = content_type.split(";")[0].strip().lower()
    return mime_type in SUPPORTED_MIME_TYPES


def resize_image(
    img: Image.Image,
    max_width: int,
) -> Image.Image:
    """Resize an image maintaining aspect ratio.
    
    Args:
        img: PIL Image object.
        max_width: Maximum width for the output.
        
    Returns:
        Resized PIL Image object.
    """
    width, height = img.size
    
    # Only resize if larger than max_width
    if width <= max_width:
        return img.copy()
    
    # Calculate new dimensions maintaining aspect ratio
    ratio = max_width / width
    new_width = max_width
    new_height = int(height * ratio)
    
    # Use LANCZOS for high-quality downsampling
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def optimize_image(
    source_path: Path,
    output_dir: Optional[Path] = None,
    file_id: Optional[str] = None,
    quality: int = OUTPUT_QUALITY,
) -> Dict[str, str]:
    """Optimize an uploaded image to WebP format with multiple sizes.
    
    Args:
        source_path: Path to the source image file.
        output_dir: Directory for output files (defaults to uploads dir).
        file_id: Unique file ID (generated if not provided).
        quality: Output quality (0-100).
        
    Returns:
        Dictionary mapping size names to relative file paths:
        {"2400w": "abc123_2400w.webp", "960w": "...", "400w": "..."}
        
    Raises:
        ImageValidationError: If source image is invalid.
        ImageProcessingError: If processing fails.
    """
    # Validate the source image
    format_name, (orig_width, orig_height) = validate_image_file(source_path)
    
    # Use default output directory if not specified
    if output_dir is None:
        output_dir = get_upload_dir()
    
    # Generate file ID if not provided
    if file_id is None:
        file_id = generate_file_id()
    
    output_paths: Dict[str, str] = {}
    
    try:
        with Image.open(source_path) as img:
            # Convert to RGB if necessary (for RGBA/P mode images)
            if img.mode in ("RGBA", "P"):
                # Create white background
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            
            # Generate each size
            for size_name, max_width in OUTPUT_SIZES.items():
                output_filename = f"{file_id}_{size_name}.webp"
                output_path = output_dir / output_filename
                
                # Resize image
                resized = resize_image(img, max_width)
                
                # Save as WebP
                resized.save(
                    output_path,
                    format="WEBP",
                    quality=quality,
                    method=6,  # Highest compression method (slower but smaller)
                )
                
                # Store the filename (not full path) for database storage
                output_paths[size_name] = output_filename
                
                logger.debug(f"Created {size_name} image: {output_path}")
            
            logger.info(
                f"Optimized image {file_id}: "
                f"{format_name} {orig_width}x{orig_height} -> WebP"
            )
            
    except Exception as e:
        # Clean up any partial output
        for path in output_paths.values():
            full_path = output_dir / path
            if full_path.exists():
                full_path.unlink()
        
        if isinstance(e, (ImageValidationError, ImageProcessingError)):
            raise
        raise ImageProcessingError(f"Failed to process image: {str(e)}")
    
    return output_paths


def get_image_urls(file_id: str, base_url: str = "/uploads") -> Dict[str, str]:
    """Generate URLs for all sizes of an image.
    
    Args:
        file_id: The unique file ID.
        base_url: Base URL for image serving.
        
    Returns:
        Dictionary mapping size names to URLs.
    """
    return {
        size_name: f"{base_url}/{file_id}_{size_name}.webp"
        for size_name in OUTPUT_SIZES.keys()
    }


def get_srcset(file_id: str, base_url: str = "/uploads") -> str:
    """Generate a srcset attribute value for responsive images.
    
    Args:
        file_id: The unique file ID.
        base_url: Base URL for image serving.
        
    Returns:
        A srcset string for HTML img tags.
    """
    urls = get_image_urls(file_id, base_url)
    srcset_parts = []
    
    for size_name, url in urls.items():
        width = OUTPUT_SIZES[size_name]
        srcset_parts.append(f"{url} {width}w")
    
    return ", ".join(srcset_parts)


def get_default_src(file_id: str, base_url: str = "/uploads") -> str:
    """Get the default (medium) size URL for an image.
    
    Args:
        file_id: The unique file ID.
        base_url: Base URL for image serving.
        
    Returns:
        URL for the medium (960w) size image.
    """
    return f"{base_url}/{file_id}_960w.webp"


def extract_file_id_from_path(path: str) -> Optional[str]:
    """Extract the file ID from an image path or URL.
    
    Args:
        path: Image path or URL (e.g., "/uploads/abc123_960w.webp")
        
    Returns:
        The file ID, or None if not found.
    """
    if not path:
        return None
    
    # Get the filename
    filename = Path(path).name
    
    # Remove the size suffix and extension
    # Expected format: {file_id}_{size}.webp
    for size_name in OUTPUT_SIZES.keys():
        suffix = f"_{size_name}.webp"
        if filename.endswith(suffix):
            return filename[:-len(suffix)]
    
    return None
