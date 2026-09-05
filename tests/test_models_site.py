"""Tests for Site and AdminUser models (Phase 2.1)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Site, AdminUser


@pytest.fixture
def db_session(temp_db_path):
    """Create a test database session with all models."""
    engine = create_engine(
        f"sqlite:///{temp_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestSiteModel:
    """Tests for the Site model."""

    def test_create_site(self, db_session: Session):
        """Test creating a Site."""
        site = Site(
            domain="example.com",
            site_type="band",
            name="Example Band",
        )
        db_session.add(site)
        db_session.commit()
        
        assert site.id is not None
        assert site.domain == "example.com"
        assert site.site_type == "band"
        assert site.name == "Example Band"
        assert site.created_at is not None
        assert site.updated_at is not None

    def test_site_unique_domain(self, db_session: Session):
        """Test that domain is unique."""
        site1 = Site(domain="unique.com", site_type="band", name="Site 1")
        db_session.add(site1)
        db_session.commit()
        
        site2 = Site(domain="unique.com", site_type="rolfing", name="Site 2")
        db_session.add(site2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_site_repr(self, db_session: Session):
        """Test Site string representation."""
        site = Site(domain="test.com", site_type="band", name="Test")
        db_session.add(site)
        db_session.commit()
        
        repr_str = repr(site)
        assert "Site" in repr_str
        assert "test.com" in repr_str
        assert "band" in repr_str


class TestAdminUserModel:
    """Tests for the AdminUser model."""

    @pytest.fixture
    def site(self, db_session: Session) -> Site:
        """Create a test site."""
        site = Site(domain="admin-test.com", site_type="band", name="Admin Test")
        db_session.add(site)
        db_session.commit()
        return site

    def test_create_admin_user(self, db_session: Session, site: Site):
        """Test creating an AdminUser."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="placeholder",
        )
        db_session.add(admin)
        db_session.commit()
        
        assert admin.id is not None
        assert admin.site_id == site.id
        assert admin.username == "admin"
        assert admin.last_login is None

    def test_set_password_hashes_securely(self, db_session: Session, site: Site):
        """Test that set_password creates a bcrypt hash."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="",
        )
        admin.set_password("mysecretpassword")
        
        # Should be bcrypt hash (starts with $2b$)
        assert admin.password_hash.startswith("$2b$")
        # Should not contain the plain password
        assert "mysecretpassword" not in admin.password_hash
        # Hash should be sufficiently long (bcrypt hashes are 60 chars)
        assert len(admin.password_hash) == 60

    def test_verify_password_correct(self, db_session: Session, site: Site):
        """Test password verification with correct password."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="",
        )
        admin.set_password("correctpassword")
        
        assert admin.verify_password("correctpassword") is True

    def test_verify_password_incorrect(self, db_session: Session, site: Site):
        """Test password verification with incorrect password."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="",
        )
        admin.set_password("correctpassword")
        
        assert admin.verify_password("wrongpassword") is False

    def test_verify_password_empty(self, db_session: Session, site: Site):
        """Test password verification with empty password."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="",
        )
        admin.set_password("somepassword")
        
        assert admin.verify_password("") is False

    def test_unique_username_per_site(self, db_session: Session, site: Site):
        """Test that username is unique per site."""
        admin1 = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="hash1",
        )
        db_session.add(admin1)
        db_session.commit()
        
        admin2 = AdminUser(
            site_id=site.id,
            username="admin",  # Same username
            password_hash="hash2",
        )
        db_session.add(admin2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_same_username_different_sites(self, db_session: Session, site: Site):
        """Test that same username can exist on different sites."""
        site2 = Site(domain="other.com", site_type="rolfing", name="Other")
        db_session.add(site2)
        db_session.commit()
        
        admin1 = AdminUser(site_id=site.id, username="admin", password_hash="h1")
        admin2 = AdminUser(site_id=site2.id, username="admin", password_hash="h2")
        
        db_session.add_all([admin1, admin2])
        db_session.commit()  # Should not raise
        
        assert admin1.id != admin2.id

    def test_update_last_login(self, db_session: Session, site: Site):
        """Test updating last_login timestamp."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="hash",
        )
        db_session.add(admin)
        db_session.commit()
        
        assert admin.last_login is None
        
        admin.update_last_login()
        db_session.commit()
        
        assert admin.last_login is not None

    def test_admin_site_relationship(self, db_session: Session, site: Site):
        """Test AdminUser-Site relationship."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="hash",
        )
        db_session.add(admin)
        db_session.commit()
        
        # Refresh to load relationship
        db_session.refresh(admin)
        
        assert admin.site is not None
        assert admin.site.id == site.id
        assert admin in site.admin_users

    def test_cascade_delete(self, db_session: Session, site: Site):
        """Test that deleting site cascades to admin users."""
        admin = AdminUser(
            site_id=site.id,
            username="admin",
            password_hash="hash",
        )
        db_session.add(admin)
        db_session.commit()
        
        admin_id = admin.id
        
        # Delete the site
        db_session.delete(site)
        db_session.commit()
        
        # Admin should be deleted too
        deleted_admin = db_session.get(AdminUser, admin_id)
        assert deleted_admin is None

    def test_admin_repr(self, db_session: Session, site: Site):
        """Test AdminUser string representation."""
        admin = AdminUser(
            site_id=site.id,
            username="testuser",
            password_hash="hash",
        )
        db_session.add(admin)
        db_session.commit()
        
        repr_str = repr(admin)
        assert "AdminUser" in repr_str
        assert "testuser" in repr_str
