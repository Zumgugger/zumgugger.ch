"""Tests for SiteConfig model (Phase 2.5)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Site, SiteConfig, MODULE_STATES, DEFAULT_MODULE_ORDER


@pytest.fixture
def db_session(temp_db_path):
    """Create a test database session with all models."""
    engine = create_engine(
        f"sqlite:///{temp_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
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


@pytest.fixture
def site(db_session: Session) -> Site:
    """Create a test site."""
    site = Site(domain="config-test.com", site_type="band", name="Config Test")
    db_session.add(site)
    db_session.commit()
    return site


class TestSiteConfigModel:
    """Tests for the SiteConfig model."""

    def test_create_site_config(self, db_session: Session, site: Site):
        """Test creating a SiteConfig."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            module_states={"hero": "enabled", "services": "enabled"},
            module_order=["hero", "services", "contact"],
        )
        db_session.add(config)
        db_session.commit()
        
        assert config.id is not None
        assert config.site_id == site.id
        assert config.theme_name == "clean"
        assert config.module_states["hero"] == "enabled"

    def test_unique_site_id(self, db_session: Session, site: Site):
        """Test that site_id is unique (one config per site)."""
        config1 = SiteConfig(site_id=site.id, theme_name="clean")
        db_session.add(config1)
        db_session.commit()
        
        config2 = SiteConfig(site_id=site.id, theme_name="bold")
        db_session.add(config2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_css_variables_json(self, db_session: Session, site: Site):
        """Test css_variables JSON field."""
        css_vars = {
            "--color-primary": "#ff0000",
            "--font-size-base": "16px",
        }
        
        config = SiteConfig(
            site_id=site.id,
            theme_name="custom",
            css_variables=css_vars,
        )
        db_session.add(config)
        db_session.commit()
        
        db_session.refresh(config)
        assert config.css_variables == css_vars

    def test_nav_labels_json(self, db_session: Session, site: Site):
        """Test nav_labels JSON field."""
        labels = {
            "services": "Leistungen",
            "about": "Über uns",
        }
        
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            nav_labels=labels,
        )
        db_session.add(config)
        db_session.commit()
        
        db_session.refresh(config)
        assert config.nav_labels == labels

    def test_site_relationship(self, db_session: Session, site: Site):
        """Test SiteConfig-Site relationship."""
        config = SiteConfig(site_id=site.id, theme_name="clean")
        db_session.add(config)
        db_session.commit()
        
        db_session.refresh(config)
        db_session.refresh(site)
        
        assert config.site == site
        assert site.config == config

    def test_cascade_delete(self, db_session: Session, site: Site):
        """Test that deleting site cascades to config."""
        config = SiteConfig(site_id=site.id, theme_name="clean")
        db_session.add(config)
        db_session.commit()
        
        config_id = config.id
        
        db_session.delete(site)
        db_session.commit()
        
        deleted_config = db_session.get(SiteConfig, config_id)
        assert deleted_config is None


class TestSiteConfigMethods:
    """Tests for SiteConfig helper methods."""

    def test_is_module_enabled(self, db_session: Session, site: Site):
        """Test is_module_enabled method."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            module_states={
                "hero": "enabled",
                "media": "available",
                "faq": "excluded",
            },
        )
        
        assert config.is_module_enabled("hero") is True
        assert config.is_module_enabled("media") is False
        assert config.is_module_enabled("faq") is False
        assert config.is_module_enabled("unknown") is False

    def test_is_module_available(self, db_session: Session, site: Site):
        """Test is_module_available method."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            module_states={
                "hero": "enabled",
                "media": "available",
                "faq": "excluded",
            },
        )
        
        assert config.is_module_available("hero") is True
        assert config.is_module_available("media") is True
        assert config.is_module_available("faq") is False

    def test_get_enabled_modules(self, db_session: Session, site: Site):
        """Test get_enabled_modules method."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            module_states={
                "hero": "enabled",
                "services": "enabled",
                "media": "available",
                "contact": "enabled",
            },
            module_order=["hero", "media", "services", "contact"],
        )
        
        enabled = config.get_enabled_modules()
        
        assert enabled == ["hero", "services", "contact"]
        assert "media" not in enabled

    def test_get_nav_label_custom(self, db_session: Session, site: Site):
        """Test get_nav_label with custom label."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            nav_labels={"services": "Mein Angebot"},
        )
        
        assert config.get_nav_label("services") == "Mein Angebot"

    def test_get_nav_label_default(self, db_session: Session, site: Site):
        """Test get_nav_label with default label."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            nav_labels={},
        )
        
        assert config.get_nav_label("services") == "Angebot"
        assert config.get_nav_label("about") == "Über mich"
        assert config.get_nav_label("hero") == ""  # No nav item for hero

    def test_set_module_state(self, db_session: Session, site: Site):
        """Test set_module_state method."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            module_states={"hero": "enabled"},
        )
        
        config.set_module_state("media", "enabled")
        
        assert config.module_states["media"] == "enabled"

    def test_set_module_state_invalid(self, db_session: Session, site: Site):
        """Test set_module_state with invalid state."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.set_module_state("hero", "invalid_state")
        
        assert "Invalid module state" in str(exc_info.value)

    def test_set_module_order(self, db_session: Session, site: Site):
        """Test set_module_order method."""
        config = SiteConfig(
            site_id=site.id,
            theme_name="clean",
            module_order=["hero", "services"],
        )
        
        new_order = ["hero", "about", "services", "contact"]
        config.set_module_order(new_order)
        
        assert config.module_order == new_order

    def test_get_default_states_for_site_type_band(self):
        """Test get_default_states_for_site_type for band."""
        states = SiteConfig.get_default_states_for_site_type("band")
        
        assert states["hero"] == "enabled"
        assert states["media"] == "enabled"  # Enabled for bands
        assert states["faq"] == "available"

    def test_get_default_states_for_site_type_rolfing(self):
        """Test get_default_states_for_site_type for rolfing."""
        states = SiteConfig.get_default_states_for_site_type("rolfing")
        
        assert states["hero"] == "enabled"
        assert states["media"] == "available"  # Not enabled for rolfing
        assert states["faq"] == "enabled"  # Enabled for rolfing


class TestModuleStatesConstants:
    """Tests for module states constants."""

    def test_module_states_values(self):
        """Test MODULE_STATES contains expected values."""
        assert "enabled" in MODULE_STATES
        assert "available" in MODULE_STATES
        assert "excluded" in MODULE_STATES

    def test_default_module_order(self):
        """Test DEFAULT_MODULE_ORDER contains expected modules."""
        assert "hero" in DEFAULT_MODULE_ORDER
        assert "services" in DEFAULT_MODULE_ORDER
        assert "contact" in DEFAULT_MODULE_ORDER
        assert "footer" in DEFAULT_MODULE_ORDER
        
        # Hero should be first, footer should be last
        assert DEFAULT_MODULE_ORDER[0] == "hero"
        assert DEFAULT_MODULE_ORDER[-1] == "footer"
