"""Pytest configuration and fixtures for WebsiteCMS tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///test_site.db"
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key"

from app.config import Settings, get_settings
from app.database import get_db, reset_engine, init_db
from app.main import create_app
from app.models.base import Base


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide test settings."""
    return Settings(
        database_url="sqlite:///test_site.db",
        debug=True,
        log_level="DEBUG",
        secret_key="test-secret-key",
        port=8002,
    )


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def test_engine(temp_db_path: Path):
    """Create a test database engine with temporary database."""
    engine = create_engine(
        f"sqlite:///{temp_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    engine.dispose()


@pytest.fixture
def test_session(test_engine) -> Generator[Session, None, None]:
    """Provide a test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_app(test_engine):
    """Create a test FastAPI application with test database."""
    # Reset any existing engine
    reset_engine()
    
    app = create_app()
    
    # Override the get_db dependency to use test database
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    yield app
    
    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_app) -> Generator[TestClient, None, None]:
    """Provide a test client for the FastAPI application."""
    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture
def client_no_db() -> Generator[TestClient, None, None]:
    """Provide a test client without database initialization.
    
    Useful for testing database connection failure scenarios.
    """
    # Set invalid database URL
    os.environ["DATABASE_URL"] = "sqlite:///nonexistent/path/db.sqlite"
    
    reset_engine()
    
    app = create_app()
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    # Reset to default
    os.environ["DATABASE_URL"] = "sqlite:///test_site.db"
    reset_engine()


# ============================================
# Fixtures for Phase 5: Admin Content Tests
# ============================================

@pytest.fixture
def test_db(test_engine) -> Generator[Session, None, None]:
    """Provide a test database session (alias for test_session)."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_site(test_db: Session):
    """Create a test site with content and config."""
    from app.models.site import Site
    from app.models.content import SiteContent
    from app.models.site_config import SiteConfig, DEFAULT_MODULE_ORDER
    
    site = Site(
        domain="localhost",
        site_type="band",
        name="Test Site",
    )
    test_db.add(site)
    test_db.flush()
    
    # Create content
    content = SiteContent(
        site_id=site.id,
        hero_headline="Test Headline",
        hero_cta_text="Kontakt",
        hero_cta_target="contact",
        services=[
            {"title": "Service 1", "description": "Description 1"},
            {"title": "Service 2", "description": "Description 2"},
        ],
        testimonials=[
            {"quote": "Great service!", "author_name": "John", "author_role": "Customer"},
        ],
        faq_items=[
            {"question": "Test Question?", "answer": "Test Answer"},
        ],
        footer_social_links=[
            {"platform": "instagram", "url": "https://instagram.com/test"},
        ],
    )
    test_db.add(content)
    
    # Create config
    config = SiteConfig(
        site_id=site.id,
        theme_name="clean",
        module_states={
            "hero": "enabled",
            "trust": "enabled",
            "services": "enabled",
            "about": "enabled",
            "media": "enabled",
            "faq": "available",
            "contact": "enabled",
            "footer": "enabled",
        },
        module_order=list(DEFAULT_MODULE_ORDER),
        nav_labels={},
        css_variables={},
    )
    test_db.add(config)
    
    test_db.commit()
    
    return site


@pytest.fixture
def test_admin_user(test_db: Session, test_site):
    """Create a test admin user."""
    from app.models.site import AdminUser
    
    admin = AdminUser(
        site_id=test_site.id,
        username="testadmin",
    )
    admin.set_password("testpassword")
    test_db.add(admin)
    test_db.commit()
    
    return admin


@pytest.fixture
def test_admin_session(test_db: Session, test_admin_user, test_site):
    """Create a test admin session."""
    from app.models.session import AdminSession
    from app.utils.auth import generate_session_token
    
    token = generate_session_token()
    session = AdminSession.create_session(
        admin_user_id=test_admin_user.id,
        site_id=test_site.id,
        token=token,
    )
    test_db.add(session)
    test_db.commit()
    
    return session


@pytest.fixture
def test_client_with_site(test_engine, test_db: Session, test_site):
    """Create a test client with a pre-configured test site."""
    reset_engine()
    
    app = create_app()
    
    # Override the get_db dependency to use test database
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()
