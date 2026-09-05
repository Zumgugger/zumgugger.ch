"""Tests for SiteContent model and content schemas (Phase 2.2)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Site, SiteContent
from app.schemas import (
    HeroSchema,
    ServiceCardSchema,
    CustomerTestimonialSchema,
    FAQItemSchema,
    SocialLinkSchema,
    AboutBlockSchema,
    MediaBlockSchema,
    TrustImageSchema,
    ContactSchema,
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


@pytest.fixture
def site(db_session: Session) -> Site:
    """Create a test site."""
    site = Site(domain="content-test.com", site_type="band", name="Content Test")
    db_session.add(site)
    db_session.commit()
    return site


class TestSiteContentModel:
    """Tests for the SiteContent model."""

    def test_create_site_content(self, db_session: Session, site: Site):
        """Test creating SiteContent."""
        content = SiteContent(
            site_id=site.id,
            hero_headline="Welcome to our site",
            hero_cta_text="Contact us",
        )
        db_session.add(content)
        db_session.commit()
        
        assert content.id is not None
        assert content.site_id == site.id
        assert content.hero_headline == "Welcome to our site"

    def test_site_content_json_fields(self, db_session: Session, site: Site):
        """Test JSON fields in SiteContent."""
        services = [
            {"title": "Service 1", "description": "Desc 1"},
            {"title": "Service 2", "description": "Desc 2"},
        ]
        testimonials = [
            {"quote": "Great!", "author_name": "John"},
        ]
        
        content = SiteContent(
            site_id=site.id,
            services=services,
            testimonials=testimonials,
        )
        db_session.add(content)
        db_session.commit()
        
        # Refresh to ensure JSON was stored and retrieved correctly
        db_session.refresh(content)
        
        assert content.services == services
        assert content.testimonials == testimonials

    def test_repertoire_groups_preserve_entered_decade_order(self, db_session: Session, site: Site):
        """Repertoire groups keep the artist's decade order for display."""
        content = SiteContent(
            site_id=site.id,
            repertoire_entries=[
                {"decade": "Irish", "year": "", "title": "Rover", "mundart": False},
                {"decade": "80er", "year": "1982", "title": "Africa", "mundart": False},
                {"decade": "Irish", "year": "1984", "title": "Streams of Whiskey", "mundart": False},
            ],
        )
        db_session.add(content)
        db_session.commit()

        groups = content.get_module_data("repertoire")["groups"]

        assert [group["decade"] for group in groups] == ["Irish", "80er"]
        assert [entry["title"] for entry in groups[0]["entries"]] == ["Rover", "Streams of Whiskey"]
        assert content.get_module_data("repertoire")["import_text"] == (
            "Irish\nRover\n\n80er\n1982 Africa\n\nIrish\n1984 Streams of Whiskey"
        )

    def test_unique_site_id(self, db_session: Session, site: Site):
        """Test that site_id is unique (one content per site)."""
        content1 = SiteContent(site_id=site.id, hero_headline="First")
        db_session.add(content1)
        db_session.commit()
        
        content2 = SiteContent(site_id=site.id, hero_headline="Second")
        db_session.add(content2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_get_module_data(self, db_session: Session, site: Site):
        """Test get_module_data helper method."""
        content = SiteContent(
            site_id=site.id,
            hero_headline="Test Headline",
            hero_cta_text="Click Me",
            hero_cta_target="contact",
            contact_phone="+41791234567",
            contact_email="test@example.com",
        )
        db_session.add(content)
        db_session.commit()
        
        hero_data = content.get_module_data("hero")
        assert hero_data["headline"] == "Test Headline"
        assert hero_data["cta_text"] == "Click Me"
        assert hero_data["cta_target"] == "contact"
        
        contact_data = content.get_module_data("contact")
        assert contact_data["phone"] == "+41791234567"
        assert contact_data["email"] == "test@example.com"

    def test_site_relationship(self, db_session: Session, site: Site):
        """Test SiteContent-Site relationship."""
        content = SiteContent(site_id=site.id, hero_headline="Test")
        db_session.add(content)
        db_session.commit()
        
        db_session.refresh(content)
        db_session.refresh(site)
        
        assert content.site == site
        assert site.content == content

    def test_cascade_delete(self, db_session: Session, site: Site):
        """Test that deleting site cascades to content."""
        content = SiteContent(site_id=site.id, hero_headline="Test")
        db_session.add(content)
        db_session.commit()
        
        content_id = content.id
        
        db_session.delete(site)
        db_session.commit()
        
        deleted_content = db_session.get(SiteContent, content_id)
        assert deleted_content is None


class TestContentSchemas:
    """Tests for Pydantic content schemas."""

    def test_hero_schema_valid(self):
        """Test HeroSchema with valid data."""
        data = HeroSchema(
            headline="Welcome!",
            cta_text="Contact",
            cta_target="contact",
        )
        assert data.headline == "Welcome!"
        assert data.cta_text == "Contact"

    def test_hero_schema_missing_required(self):
        """Test HeroSchema rejects missing required fields."""
        with pytest.raises(ValueError):
            HeroSchema(headline="Welcome!")  # Missing cta_text

    def test_service_card_schema_valid(self):
        """Test ServiceCardSchema with valid data."""
        data = ServiceCardSchema(
            title="My Service",
            description="Service description",
            image="/images/service.jpg",
        )
        assert data.title == "My Service"
        assert data.image == "/images/service.jpg"

    def test_service_card_schema_missing_required(self):
        """Test ServiceCardSchema rejects missing required fields."""
        with pytest.raises(ValueError):
            ServiceCardSchema(title="Service")  # Missing description

    def test_testimonial_schema_valid(self):
        """Test CustomerTestimonialSchema with valid data."""
        data = CustomerTestimonialSchema(
            quote="This is great!",
            author_name="John Doe",
            author_role="Customer",
        )
        assert data.quote == "This is great!"
        assert data.author_role == "Customer"

    def test_testimonial_schema_optional_role(self):
        """Test CustomerTestimonialSchema with optional author_role."""
        data = CustomerTestimonialSchema(
            quote="Great service",
            author_name="Jane",
        )
        assert data.author_role is None

    def test_faq_item_schema_valid(self):
        """Test FAQItemSchema with valid data."""
        data = FAQItemSchema(
            question="How does it work?",
            answer="It works like this...",
        )
        assert data.question == "How does it work?"

    def test_social_link_schema_valid(self):
        """Test SocialLinkSchema with valid data."""
        data = SocialLinkSchema(
            platform="instagram",
            url="https://instagram.com/mypage",
        )
        assert data.platform == "instagram"

    def test_social_link_schema_email(self):
        """Test SocialLinkSchema with email platform."""
        data = SocialLinkSchema(
            platform="email",
            url="mailto:test@example.com",
        )
        assert data.platform == "email"
        
        # Also accepts plain email
        data2 = SocialLinkSchema(
            platform="email",
            url="test@example.com",
        )
        assert "@" in data2.url

    def test_social_link_schema_invalid_url(self):
        """Test SocialLinkSchema rejects invalid URLs."""
        with pytest.raises(ValueError):
            SocialLinkSchema(
                platform="instagram",
                url="not-a-valid-url",
            )

    def test_about_block_text_valid(self):
        """Test AboutBlockSchema for text block."""
        data = AboutBlockSchema(
            type="text",
            content="<p>Hello world</p>",
        )
        assert data.type == "text"
        assert data.content == "<p>Hello world</p>"

    def test_about_block_text_missing_content(self):
        """Test AboutBlockSchema rejects text block without content."""
        with pytest.raises(ValueError):
            AboutBlockSchema(type="text")  # Missing content

    def test_about_block_image_valid(self):
        """Test AboutBlockSchema for image block."""
        data = AboutBlockSchema(
            type="image",
            src="/images/photo.jpg",
            alt="A photo",
        )
        assert data.type == "image"
        assert data.src == "/images/photo.jpg"

    def test_media_block_youtube_valid(self):
        """Test MediaBlockSchema for YouTube block."""
        data = MediaBlockSchema(
            type="youtube",
            youtube_url="https://youtube.com/watch?v=abc123",
        )
        assert data.type == "youtube"
        assert "youtube.com" in data.youtube_url

    def test_media_block_audio_valid(self):
        """Test MediaBlockSchema for audio block."""
        data = MediaBlockSchema(
            type="audio",
            audio_url="https://open.spotify.com/track/xxx",
            audio_provider="spotify",
        )
        assert data.type == "audio"
        assert data.audio_provider == "spotify"

    def test_contact_schema_phone_e164(self):
        """Test ContactSchema validates E.164 phone format."""
        data = ContactSchema(
            phone="+41791234567",
            email="test@example.com",
        )
        assert data.phone == "+41791234567"

    def test_contact_schema_phone_invalid(self):
        """Test ContactSchema rejects non-E.164 phone."""
        with pytest.raises(ValueError):
            ContactSchema(phone="0791234567")  # Missing +

    def test_contact_schema_email_invalid(self):
        """Test ContactSchema rejects invalid email."""
        with pytest.raises(ValueError):
            ContactSchema(email="not-an-email")

    def test_trust_image_schema(self):
        """Test TrustImageSchema."""
        data = TrustImageSchema(
            src="/images/logo.png",
            alt="Company Logo",
        )
        assert data.src == "/images/logo.png"
        assert data.alt == "Company Logo"
