"""Tests for seed data and fixtures (Phase 2.4)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Site, SiteContent, SiteConfig
from app.seeds import (
    load_seed,
    get_available_site_types,
    validate_seed_data,
    SEED_TYPES,
)
from app.seeds.band import get_band_seed
from app.seeds.rolfing import get_rolfing_seed
from app.schemas import (
    ServiceCardSchema,
    CustomerTestimonialSchema,
    FAQItemSchema,
    SocialLinkSchema,
)


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


class TestSeedLoader:
    """Tests for seed loading functions."""

    def test_load_band_seed(self):
        """Test loading Band seed data."""
        seed = load_seed("band")
        
        assert seed["site_type"] == "band"
        assert "content" in seed
        assert "config" in seed

    def test_load_rolfing_seed(self):
        """Test loading Rolfing seed data."""
        seed = load_seed("rolfing")
        
        assert seed["site_type"] == "rolfing"
        assert "content" in seed
        assert "config" in seed

    def test_load_unknown_seed_raises(self):
        """Test that loading unknown seed type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_seed("unknown")
        
        assert "Unknown site type" in str(exc_info.value)
        assert "band" in str(exc_info.value)
        assert "rolfing" in str(exc_info.value)

    def test_get_available_site_types(self):
        """Test getting available site types."""
        types = get_available_site_types()
        
        assert "band" in types
        assert "rolfing" in types
        assert len(types) == len(SEED_TYPES)


class TestBandSeed:
    """Tests for Band seed data."""

    def test_band_seed_structure(self):
        """Test Band seed has correct structure."""
        seed = get_band_seed()
        
        assert validate_seed_data(seed) is True

    def test_band_seed_content(self):
        """Test Band seed content fields."""
        seed = get_band_seed()
        content = seed["content"]
        
        # Hero
        assert content["hero_headline"] is not None
        assert len(content["hero_headline"]) > 0
        assert content["hero_cta_text"] is not None
        assert content["hero_cta_target"] == "contact"
        
        # Services
        assert len(content["services"]) >= 1
        
        # Testimonials
        assert len(content["testimonials"]) >= 1
        
        # Legal pages
        assert content["impressum_content"] is not None
        assert content["datenschutz_content"] is not None

    def test_band_seed_services_valid(self):
        """Test Band seed services match schema."""
        seed = get_band_seed()
        
        for service in seed["content"]["services"]:
            # Should be valid ServiceCardSchema
            ServiceCardSchema(**service)

    def test_band_seed_testimonials_valid(self):
        """Test Band seed testimonials match schema."""
        seed = get_band_seed()
        
        for testimonial in seed["content"]["testimonials"]:
            CustomerTestimonialSchema(**testimonial)

    def test_band_seed_config(self):
        """Test Band seed config."""
        seed = get_band_seed()
        config = seed["config"]
        
        assert config["theme_name"] == "clean"
        assert config["module_states"]["media"] == "enabled"  # Enabled for bands
        assert "module_order" in config


class TestRolfingSeed:
    """Tests for Rolfing seed data."""

    def test_rolfing_seed_structure(self):
        """Test Rolfing seed has correct structure."""
        seed = get_rolfing_seed()
        
        assert validate_seed_data(seed) is True

    def test_rolfing_seed_content(self):
        """Test Rolfing seed content fields."""
        seed = get_rolfing_seed()
        content = seed["content"]
        
        # Hero
        assert content["hero_headline"] is not None
        assert "Rolfing" in content["hero_headline"] or "Struktur" in content["hero_headline"]
        
        # FAQ (enabled for rolfing)
        assert len(content["faq_items"]) >= 1

    def test_rolfing_seed_faq_valid(self):
        """Test Rolfing seed FAQ items match schema."""
        seed = get_rolfing_seed()
        
        for faq in seed["content"]["faq_items"]:
            FAQItemSchema(**faq)

    def test_rolfing_seed_config(self):
        """Test Rolfing seed config."""
        seed = get_rolfing_seed()
        config = seed["config"]
        
        assert config["theme_name"] == "elegant"
        assert config["module_states"]["faq"] == "enabled"  # Enabled for rolfing
        assert config["module_states"]["media"] == "available"  # Not enabled


class TestSeedDataValidation:
    """Tests for seed data validation."""

    def test_validate_seed_data_valid(self):
        """Test validation passes for valid seed data."""
        seed = get_band_seed()
        assert validate_seed_data(seed) is True

    def test_validate_seed_data_missing_site_type(self):
        """Test validation fails if site_type is missing."""
        seed = {"content": {}, "config": {}}
        
        with pytest.raises(ValueError) as exc_info:
            validate_seed_data(seed)
        
        assert "site_type" in str(exc_info.value)

    def test_validate_seed_data_missing_content(self):
        """Test validation fails if content is missing."""
        seed = {"site_type": "test", "config": {}}
        
        with pytest.raises(ValueError) as exc_info:
            validate_seed_data(seed)
        
        assert "content" in str(exc_info.value)

    def test_validate_seed_data_missing_content_keys(self):
        """Test validation fails if required content keys are missing."""
        seed = {
            "site_type": "test",
            "content": {"hero_headline": "Test"},  # Missing other required keys
            "config": {"theme_name": "clean", "module_states": {}, "module_order": []},
        }
        
        with pytest.raises(ValueError) as exc_info:
            validate_seed_data(seed)
        
        assert "content" in str(exc_info.value).lower()


class TestSeedDataIntegration:
    """Integration tests for seed data with database."""

    def test_insert_band_seed_into_db(self, db_session: Session):
        """Test inserting Band seed data into database."""
        seed = get_band_seed()
        
        # Create site
        site = Site(
            domain="band-test.com",
            site_type=seed["site_type"],
            name="Test Band Site",
        )
        db_session.add(site)
        db_session.commit()
        
        # Create content
        content_data = seed["content"]
        content = SiteContent(
            site_id=site.id,
            hero_headline=content_data["hero_headline"],
            hero_cta_text=content_data["hero_cta_text"],
            hero_cta_target=content_data["hero_cta_target"],
            services=content_data["services"],
            testimonials=content_data["testimonials"],
            about_blocks=content_data["about_blocks"],
            faq_items=content_data["faq_items"],
            footer_social_links=content_data["footer_social_links"],
            impressum_content=content_data["impressum_content"],
            datenschutz_content=content_data["datenschutz_content"],
        )
        db_session.add(content)
        
        # Create config
        config_data = seed["config"]
        config = SiteConfig(
            site_id=site.id,
            theme_name=config_data["theme_name"],
            module_states=config_data["module_states"],
            module_order=config_data["module_order"],
            css_variables=config_data["css_variables"],
            nav_labels=config_data["nav_labels"],
        )
        db_session.add(config)
        
        db_session.commit()
        
        # Verify
        db_session.refresh(site)
        assert site.content is not None
        assert site.content.hero_headline == content_data["hero_headline"]
        assert site.config is not None
        assert site.config.theme_name == "clean"

    def test_insert_rolfing_seed_into_db(self, db_session: Session):
        """Test inserting Rolfing seed data into database."""
        seed = get_rolfing_seed()
        
        site = Site(
            domain="rolfing-test.com",
            site_type=seed["site_type"],
            name="Test Rolfing Site",
        )
        db_session.add(site)
        db_session.commit()
        
        content_data = seed["content"]
        content = SiteContent(
            site_id=site.id,
            hero_headline=content_data["hero_headline"],
            hero_cta_text=content_data["hero_cta_text"],
            services=content_data["services"],
            faq_items=content_data["faq_items"],
            impressum_content=content_data["impressum_content"],
            datenschutz_content=content_data["datenschutz_content"],
        )
        db_session.add(content)
        
        config_data = seed["config"]
        config = SiteConfig(
            site_id=site.id,
            theme_name=config_data["theme_name"],
            module_states=config_data["module_states"],
            module_order=config_data["module_order"],
        )
        db_session.add(config)
        
        db_session.commit()
        
        db_session.refresh(site)
        assert site.content is not None
        assert len(site.content.faq_items) > 0
        assert site.config.is_module_enabled("faq") is True
