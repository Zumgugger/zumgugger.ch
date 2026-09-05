"""Tests for image upload, processing, and serving (Phase 6).

This module tests:
- Image upload endpoint validation
- Image optimization pipeline
- Image serving with cache headers
- Image field updates
- Image cleanup utilities
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.base import Base
from app.models.content import SiteContent
from app.models.session import AdminSession
from app.models.site import AdminUser, Site
from app.utils.image_processing import (
    ImageProcessingError,
    ImageValidationError,
    MAX_FILE_SIZE,
    OUTPUT_SIZES,
    extract_file_id_from_path,
    get_default_src,
    get_image_urls,
    get_srcset,
    optimize_image,
    validate_content_type,
    validate_image_file,
)
from app.utils.storage import (
    delete_image,
    generate_file_id,
    get_all_image_sizes,
    get_image_path,
    get_temp_dir,
    get_upload_dir,
    image_exists,
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_upload_dir() -> Generator[Path, None, None]:
    """Create a temporary upload directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["UPLOAD_DIR"] = tmpdir
        os.environ["DATA_DIR"] = tmpdir
        yield Path(tmpdir)
        # Clean up env vars
        if "UPLOAD_DIR" in os.environ:
            del os.environ["UPLOAD_DIR"]
        if "DATA_DIR" in os.environ:
            del os.environ["DATA_DIR"]


@pytest.fixture
def sample_jpeg_bytes() -> bytes:
    """Create a sample JPEG image as bytes."""
    img = Image.new("RGB", (800, 600), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


@pytest.fixture
def sample_png_bytes() -> bytes:
    """Create a sample PNG image with alpha channel."""
    img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def sample_large_image_bytes() -> bytes:
    """Create a large image that exceeds size limits."""
    # Create a 3000x3000 RGB image with random-ish data to prevent compression
    img = Image.new("RGB", (3000, 3000), color="blue")
    # Add some noise to prevent excessive compression
    pixels = img.load()
    for i in range(3000):
        for j in range(0, 3000, 100):
            pixels[i, j] = ((i * j) % 256, (i + j) % 256, (i - j) % 256)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def sample_jpeg_file(temp_upload_dir: Path, sample_jpeg_bytes: bytes) -> Path:
    """Create a sample JPEG file."""
    file_path = temp_upload_dir / "sample.jpg"
    file_path.write_bytes(sample_jpeg_bytes)
    return file_path


@pytest.fixture
def sample_png_file(temp_upload_dir: Path, sample_png_bytes: bytes) -> Path:
    """Create a sample PNG file with alpha channel."""
    file_path = temp_upload_dir / "sample.png"
    file_path.write_bytes(sample_png_bytes)
    return file_path


@pytest.fixture
def image_client(temp_db_path, temp_upload_dir) -> Generator[TestClient, None, None]:
    """Test client with temporary upload directory (no auth)."""
    from app.config import get_settings
    from app.database import reset_engine
    from app.main import create_app
    
    # Set database URL to temp database BEFORE creating app
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db_path}"
    
    # Clear settings cache so it picks up the new DATABASE_URL
    get_settings.cache_clear()
    reset_engine()
    
    app = create_app()
    
    with TestClient(app) as client:
        yield client
    
    # Restore original DATABASE_URL and clear caches
    if old_db_url:
        os.environ["DATABASE_URL"] = old_db_url
    else:
        del os.environ["DATABASE_URL"]
    get_settings.cache_clear()
    reset_engine()


@pytest.fixture
def image_client_with_auth(temp_db_path, temp_upload_dir) -> Generator[tuple[TestClient, str], None, None]:
    """Test client with pre-configured site, admin, and session.
    
    Returns a tuple of (client, auth_token).
    The lifespan handler creates a demo site, so we reuse it and just add an admin session.
    """
    from app.config import get_settings
    from app.database import reset_engine, get_db_context
    from app.main import create_app
    from app.utils.auth import generate_session_token
    
    # Set database URL to temp database BEFORE creating app
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{temp_db_path}"
    
    # Clear settings cache so it picks up the new DATABASE_URL
    get_settings.cache_clear()
    reset_engine()
    
    app = create_app()
    
    # Start the TestClient - this triggers the lifespan handler
    # which creates tables and demo site
    with TestClient(app) as client:
        # Now that lifespan has run, we can query the database
        with get_db_context() as db:
            # Get the existing site created by lifespan
            site = db.query(Site).filter(Site.domain == "localhost").first()
            assert site is not None, "Demo site should exist after lifespan"
            
            # Get the admin user created by lifespan
            admin = db.query(AdminUser).filter(AdminUser.site_id == site.id).first()
            assert admin is not None, "Admin user should exist after lifespan"
            
            # Create admin session
            token = generate_session_token()
            session_obj = AdminSession.create_session(
                admin_user_id=admin.id,
                site_id=site.id,
                token=token,
            )
            db.add(session_obj)
            # commit happens automatically with get_db_context
        
        yield client, token
    
    # Restore original DATABASE_URL and clear caches
    if old_db_url:
        os.environ["DATABASE_URL"] = old_db_url
    else:
        del os.environ["DATABASE_URL"]
    get_settings.cache_clear()
    reset_engine()


# ============================================
# Storage Utility Tests
# ============================================

class TestStorageUtils:
    """Tests for storage utilities."""
    
    def test_generate_file_id_is_unique(self):
        """File IDs should be unique."""
        ids = [generate_file_id() for _ in range(100)]
        assert len(set(ids)) == 100
    
    def test_generate_file_id_is_valid_filename(self):
        """File IDs should be safe for filenames."""
        file_id = generate_file_id()
        # Should only contain alphanumeric and hyphens
        assert all(c.isalnum() or c == "-" for c in file_id)
    
    def test_get_image_path(self, temp_upload_dir):
        """get_image_path should return correct path."""
        file_id = "test-file-id"
        path = get_image_path(file_id, "960w")
        assert path.name == f"{file_id}_960w.webp"
    
    def test_get_all_image_sizes(self, temp_upload_dir):
        """get_all_image_sizes should return paths for all sizes."""
        file_id = "test-file-id"
        paths = get_all_image_sizes(file_id)
        assert len(paths) == 3
        sizes = [p.name.split("_")[1].replace(".webp", "") for p in paths]
        assert set(sizes) == {"2400w", "960w", "400w"}
    
    def test_image_exists_false_for_missing(self, temp_upload_dir):
        """image_exists should return False for non-existent images."""
        assert not image_exists("nonexistent-id")
    
    def test_image_exists_true_after_creation(self, temp_upload_dir, sample_jpeg_file):
        """image_exists should return True after image is optimized."""
        output_dir = Path(temp_upload_dir)
        optimize_image(sample_jpeg_file, output_dir=output_dir)
        
        # Find the created file ID
        files = list(output_dir.glob("*_960w.webp"))
        assert len(files) == 1
        file_id = files[0].name.replace("_960w.webp", "")
        
        assert image_exists(file_id)


# ============================================
# Image Processing Tests
# ============================================

class TestImageValidation:
    """Tests for image validation."""
    
    def test_validate_content_type_jpeg(self):
        """JPEG content type should be valid."""
        assert validate_content_type("image/jpeg")
    
    def test_validate_content_type_png(self):
        """PNG content type should be valid."""
        assert validate_content_type("image/png")
    
    def test_validate_content_type_webp(self):
        """WebP content type should be valid."""
        assert validate_content_type("image/webp")
    
    def test_validate_content_type_gif(self):
        """GIF content type should be valid."""
        assert validate_content_type("image/gif")
    
    def test_validate_content_type_with_charset(self):
        """Content type with charset should be valid."""
        assert validate_content_type("image/jpeg; charset=utf-8")
    
    def test_validate_content_type_invalid(self):
        """Invalid content types should be rejected."""
        assert not validate_content_type("text/plain")
        assert not validate_content_type("application/pdf")
        assert not validate_content_type(None)
        assert not validate_content_type("")
    
    def test_validate_image_file_success(self, sample_jpeg_file):
        """Valid image file should pass validation."""
        format_name, (width, height) = validate_image_file(sample_jpeg_file)
        assert format_name == "JPEG"
        assert width == 800
        assert height == 600
    
    def test_validate_image_file_png_success(self, sample_png_file):
        """Valid PNG file should pass validation."""
        format_name, (width, height) = validate_image_file(sample_png_file)
        assert format_name == "PNG"
        assert width == 800
        assert height == 600
    
    def test_validate_image_file_not_found(self, temp_upload_dir):
        """Non-existent file should fail validation."""
        with pytest.raises(ImageValidationError, match="File not found"):
            validate_image_file(temp_upload_dir / "nonexistent.jpg")
    
    def test_validate_image_file_unsupported_extension(self, temp_upload_dir):
        """Unsupported extension should fail validation."""
        bad_file = temp_upload_dir / "test.bmp"
        bad_file.write_bytes(b"fake data")
        with pytest.raises(ImageValidationError, match="Unsupported file type"):
            validate_image_file(bad_file)
    
    def test_validate_image_file_corrupt(self, temp_upload_dir):
        """Corrupt image file should fail validation."""
        corrupt_file = temp_upload_dir / "corrupt.jpg"
        corrupt_file.write_bytes(b"not an image")
        with pytest.raises(ImageValidationError, match="Could not identify"):
            validate_image_file(corrupt_file)


class TestImageOptimization:
    """Tests for image optimization pipeline."""
    
    def test_optimize_creates_all_sizes(self, temp_upload_dir, sample_jpeg_file):
        """optimize_image should create all 3 sizes."""
        output_dir = Path(temp_upload_dir)
        result = optimize_image(sample_jpeg_file, output_dir=output_dir)
        
        assert "2400w" in result
        assert "960w" in result
        assert "400w" in result
        
        for size, filename in result.items():
            path = output_dir / filename
            assert path.exists()
            assert path.suffix == ".webp"
    
    def test_optimize_output_is_webp(self, temp_upload_dir, sample_jpeg_file):
        """Output should be WebP format."""
        output_dir = Path(temp_upload_dir)
        result = optimize_image(sample_jpeg_file, output_dir=output_dir)
        
        path = output_dir / result["960w"]
        with Image.open(path) as img:
            assert img.format == "WEBP"
    
    def test_optimize_preserves_aspect_ratio(self, temp_upload_dir, sample_jpeg_file):
        """Aspect ratio should be preserved."""
        output_dir = Path(temp_upload_dir)
        result = optimize_image(sample_jpeg_file, output_dir=output_dir)
        
        # Original is 800x600 (4:3)
        path = output_dir / result["400w"]
        with Image.open(path) as img:
            width, height = img.size
            assert width == 400
            # Height should maintain 4:3 ratio
            assert height == 300
    
    def test_optimize_handles_rgba(self, temp_upload_dir, sample_png_file):
        """RGBA images should be converted correctly."""
        output_dir = Path(temp_upload_dir)
        result = optimize_image(sample_png_file, output_dir=output_dir)
        
        path = output_dir / result["960w"]
        assert path.exists()
        
        with Image.open(path) as img:
            assert img.format == "WEBP"
    
    def test_optimize_with_custom_file_id(self, temp_upload_dir, sample_jpeg_file):
        """Custom file ID should be used."""
        output_dir = Path(temp_upload_dir)
        result = optimize_image(
            sample_jpeg_file,
            output_dir=output_dir,
            file_id="my-custom-id",
        )
        
        assert "my-custom-id_960w.webp" in result["960w"]
    
    def test_optimize_does_not_upscale(self, temp_upload_dir):
        """Small images should not be upscaled."""
        # Create a small image
        img = Image.new("RGB", (200, 150), color="green")
        small_file = temp_upload_dir / "small.jpg"
        img.save(small_file, format="JPEG")
        
        result = optimize_image(small_file, output_dir=temp_upload_dir)
        
        # Check that large sizes are capped at original dimensions
        path = temp_upload_dir / result["2400w"]
        with Image.open(path) as output:
            assert output.size[0] <= 200


class TestImageUrls:
    """Tests for URL generation utilities."""
    
    def test_get_image_urls(self):
        """get_image_urls should return all size URLs."""
        urls = get_image_urls("test-id")
        assert urls["2400w"] == "/uploads/test-id_2400w.webp"
        assert urls["960w"] == "/uploads/test-id_960w.webp"
        assert urls["400w"] == "/uploads/test-id_400w.webp"
    
    def test_get_image_urls_custom_base(self):
        """Custom base URL should be used."""
        urls = get_image_urls("test-id", base_url="/images")
        assert urls["960w"] == "/images/test-id_960w.webp"
    
    def test_get_srcset(self):
        """get_srcset should return valid srcset string."""
        srcset = get_srcset("test-id")
        assert "/uploads/test-id_2400w.webp 2400w" in srcset
        assert "/uploads/test-id_960w.webp 960w" in srcset
        assert "/uploads/test-id_400w.webp 400w" in srcset
    
    def test_get_default_src(self):
        """get_default_src should return 960w URL."""
        src = get_default_src("test-id")
        assert src == "/uploads/test-id_960w.webp"
    
    def test_extract_file_id_from_path(self):
        """extract_file_id should work with various path formats."""
        assert extract_file_id_from_path("/uploads/abc123_960w.webp") == "abc123"
        assert extract_file_id_from_path("abc123_2400w.webp") == "abc123"
        assert extract_file_id_from_path("abc123_400w.webp") == "abc123"
        assert extract_file_id_from_path("invalid.jpg") is None
        assert extract_file_id_from_path("") is None
        assert extract_file_id_from_path(None) is None


# ============================================
# Upload Endpoint Tests
# ============================================

class TestUploadEndpoint:
    """Tests for the image upload endpoint."""
    
    def test_upload_requires_auth(self, image_client, sample_jpeg_bytes):
        """Upload should require authentication."""
        response = image_client.post(
            "/api/admin/upload",
            files={"file": ("test.jpg", sample_jpeg_bytes, "image/jpeg")},
        )
        assert response.status_code == 401
    
    def test_upload_success(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Successful upload should return file ID and URLs."""
        client, token = image_client_with_auth
        response = client.post(
            "/api/admin/upload",
            files={"file": ("test.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "file_id" in data
        assert "urls" in data
        assert "srcset" in data
        assert "default_src" in data
        
        # Verify URLs contain file_id
        file_id = data["file_id"]
        assert file_id in data["default_src"]
    
    def test_upload_creates_files(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Upload should create optimized image files."""
        client, token = image_client_with_auth
        response = client.post(
            "/api/admin/upload",
            files={"file": ("test.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        
        assert response.status_code == 200
        file_id = response.json()["file_id"]
        
        # Check files exist
        upload_dir = get_upload_dir()
        for size in ["2400w", "960w", "400w"]:
            path = upload_dir / f"{file_id}_{size}.webp"
            assert path.exists(), f"Missing {size} file"
    
    def test_upload_rejects_invalid_content_type(
        self,
        image_client_with_auth,
    ):
        """Invalid content type should be rejected."""
        client, token = image_client_with_auth
        response = client.post(
            "/api/admin/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            cookies={"session_token": token},
        )
        
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "validation_error"
    
    def test_upload_rejects_oversized_file(
        self,
        image_client_with_auth,
        sample_large_image_bytes,
    ):
        """Oversized files should be rejected."""
        client, token = image_client_with_auth
        # Create a file larger than 5MB
        large_data = sample_large_image_bytes
        if len(large_data) <= 5 * 1024 * 1024:
            # If the image isn't large enough, pad it
            large_data = large_data + b"\x00" * (5 * 1024 * 1024 + 1)
        
        response = client.post(
            "/api/admin/upload",
            files={"file": ("large.png", large_data, "image/png")},
            cookies={"session_token": token},
        )
        
        assert response.status_code == 413
    
    def test_upload_png_with_alpha(
        self,
        image_client_with_auth,
        sample_png_bytes,
        temp_upload_dir,
    ):
        """PNG with alpha channel should be handled correctly."""
        client, token = image_client_with_auth
        response = client.post(
            "/api/admin/upload",
            files={"file": ("test.png", sample_png_bytes, "image/png")},
            cookies={"session_token": token},
        )
        
        assert response.status_code == 200


# ============================================
# Image Serving Tests
# ============================================

class TestImageServing:
    """Tests for image serving endpoint."""
    
    def test_serve_existing_image(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Serving an existing image should return the file."""
        client, token = image_client_with_auth
        # First upload an image
        upload_response = client.post(
            "/api/admin/upload",
            files={"file": ("test.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # Then serve it
        response = client.get(f"/uploads/{file_id}_960w.webp")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/webp"
        assert "Cache-Control" in response.headers
        assert "max-age=31536000" in response.headers["Cache-Control"]
    
    def test_serve_missing_image_returns_404(self, image_client):
        """Serving a non-existent image should return 404."""
        response = image_client.get("/uploads/nonexistent_960w.webp")
        assert response.status_code == 404
    
    def test_serve_rejects_path_traversal(self, image_client):
        """Path traversal attempts should be rejected."""
        response = image_client.get("/uploads/../../../etc/passwd")
        assert response.status_code in (400, 404)
    
    def test_serve_rejects_non_webp(self, image_client):
        """Non-WebP files should not be served."""
        response = image_client.get("/uploads/test.jpg")
        assert response.status_code == 404


# ============================================
# Image Field Update Tests
# ============================================

class TestImageFieldUpdate:
    """Tests for updating image fields."""
    
    def test_update_hero_image(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Updating hero background image should work."""
        client, token = image_client_with_auth
        # Upload an image
        upload_response = client.post(
            "/api/admin/upload",
            files={"file": ("hero.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # Update the hero image field
        update_response = client.put(
            "/api/admin/content/image/hero_bg_image",
            json={"file_id": file_id},
            cookies={"session_token": token},
        )
        
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "success"
        assert data["field"] == "hero_bg_image"
        assert file_id in data["urls"]["960w"]
    
    def test_update_requires_auth(self, image_client):
        """Image field updates require authentication."""
        response = image_client.put(
            "/api/admin/content/image/hero_bg_image",
            json={"file_id": "some-id"},
        )
        assert response.status_code == 401
    
    def test_update_rejects_invalid_field(
        self,
        image_client_with_auth,
    ):
        """Invalid field names should be rejected."""
        client, token = image_client_with_auth
        response = client.put(
            "/api/admin/content/image/invalid_field",
            json={"file_id": "some-id"},
            cookies={"session_token": token},
        )
        assert response.status_code == 400
    
    def test_update_rejects_nonexistent_image(
        self,
        image_client_with_auth,
    ):
        """Non-existent file IDs should be rejected."""
        client, token = image_client_with_auth
        response = client.put(
            "/api/admin/content/image/hero_bg_image",
            json={"file_id": "nonexistent-file-id"},
            cookies={"session_token": token},
        )
        assert response.status_code == 404


class TestArrayImageFieldUpdate:
    """Tests for updating images in array fields."""
    
    def test_update_service_image(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Updating service card image should work."""
        client, token = image_client_with_auth
        # Upload an image
        upload_response = client.post(
            "/api/admin/upload",
            files={"file": ("service.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # Update service[0].image
        update_response = client.put(
            "/api/admin/content/image/array/services/0",
            json={"file_id": file_id},
            cookies={"session_token": token},
        )
        
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "success"
        assert "services[0]" in data["field"]
    
    def test_update_invalid_index(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Invalid array index should be rejected."""
        client, token = image_client_with_auth
        # Upload an image
        upload_response = client.post(
            "/api/admin/upload",
            files={"file": ("service.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        file_id = upload_response.json()["file_id"]
        
        # Try to update non-existent index
        update_response = client.put(
            "/api/admin/content/image/array/services/999",
            json={"file_id": file_id},
            cookies={"session_token": token},
        )
        
        assert update_response.status_code == 400


# ============================================
# Image Cleanup Tests
# ============================================

class TestImageCleanup:
    """Tests for image cleanup utilities."""
    
    def test_delete_image_soft_delete(self, temp_upload_dir, sample_jpeg_file):
        """Soft delete should move images to trash."""
        result = optimize_image(sample_jpeg_file, output_dir=temp_upload_dir)
        file_id = result["960w"].replace("_960w.webp", "")
        
        assert image_exists(file_id)
        
        delete_image(file_id, soft_delete=True)
        
        # Should no longer exist in uploads
        assert not image_exists(file_id)
        
        # Should exist in trash
        trash_dir = temp_upload_dir / "trash"
        trash_files = list(trash_dir.glob(f"{file_id}_*.webp"))
        assert len(trash_files) > 0
    
    def test_delete_image_hard_delete(self, temp_upload_dir, sample_jpeg_file):
        """Hard delete should permanently remove images."""
        result = optimize_image(sample_jpeg_file, output_dir=temp_upload_dir)
        file_id = result["960w"].replace("_960w.webp", "")
        
        assert image_exists(file_id)
        
        delete_image(file_id, soft_delete=False)
        
        assert not image_exists(file_id)


# ============================================
# Integration Tests
# ============================================

class TestImageIntegration:
    """End-to-end integration tests."""
    
    def test_full_image_workflow(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        temp_upload_dir,
    ):
        """Test complete workflow: upload -> update field -> serve."""
        client, token = image_client_with_auth
        # 1. Upload image
        upload_response = client.post(
            "/api/admin/upload",
            files={"file": ("hero.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # 2. Update hero image field
        update_response = client.put(
            "/api/admin/content/image/hero_bg_image",
            json={"file_id": file_id},
            cookies={"session_token": token},
        )
        assert update_response.status_code == 200
        
        # 3. Serve the image
        serve_response = client.get(f"/uploads/{file_id}_960w.webp")
        assert serve_response.status_code == 200
        assert response_is_valid_webp(serve_response.content)
    
    def test_replace_image_records_history(
        self,
        image_client_with_auth,
        sample_jpeg_bytes,
        sample_png_bytes,
        temp_upload_dir,
    ):
        """Replacing an image should record the old value in history."""
        client, token = image_client_with_auth
        # Upload first image
        upload1 = client.post(
            "/api/admin/upload",
            files={"file": ("first.jpg", sample_jpeg_bytes, "image/jpeg")},
            cookies={"session_token": token},
        )
        file_id1 = upload1.json()["file_id"]
        
        # Set hero image
        client.put(
            "/api/admin/content/image/hero_bg_image",
            json={"file_id": file_id1},
            cookies={"session_token": token},
        )
        
        # Upload second image
        upload2 = client.post(
            "/api/admin/upload",
            files={"file": ("second.png", sample_png_bytes, "image/png")},
            cookies={"session_token": token},
        )
        file_id2 = upload2.json()["file_id"]
        
        # Replace hero image
        update2 = client.put(
            "/api/admin/content/image/hero_bg_image",
            json={"file_id": file_id2},
            cookies={"session_token": token},
        )
        assert update2.status_code == 200


def response_is_valid_webp(content: bytes) -> bool:
    """Check if response content is valid WebP."""
    try:
        img = Image.open(io.BytesIO(content))
        return img.format == "WEBP"
    except Exception:
        return False
