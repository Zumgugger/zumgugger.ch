"""Tests for public frontend routes (Phase 4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.site import Site, AdminUser
from app.models.content import SiteContent
from app.models.site_config import SiteConfig
from app.seeds.band import get_band_seed


@pytest.fixture
def site_with_content(test_session: Session) -> Site:
    """Create a test site with content and config."""
    # Create site
    site = Site(
        domain="testband.example.com",
        site_type="band",
        name="Test Band",
    )
    test_session.add(site)
    test_session.flush()
    
    # Get seed data
    seed = get_band_seed()
    
    # Create content
    content = SiteContent(
        site_id=site.id,
        **seed["content"]
    )
    test_session.add(content)
    
    # Create config
    config = SiteConfig(
        site_id=site.id,
        theme_name=seed["config"]["theme_name"],
        module_states=seed["config"]["module_states"],
        module_order=seed["config"]["module_order"],
        css_variables=seed["config"].get("css_variables", {}),
        nav_labels=seed["config"].get("nav_labels", {}),
    )
    test_session.add(config)
    
    # Create admin user
    admin = AdminUser(
        site_id=site.id,
        username="admin",
    )
    admin.set_password("testpassword123")
    test_session.add(admin)
    
    test_session.commit()
    test_session.refresh(site)
    
    return site


class TestPublicRoutes:
    """Test public-facing routes."""
    
    def test_home_page_returns_html(self, client: TestClient, site_with_content: Site):
        """Test that GET / returns HTML."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_home_page_contains_site_name(self, client: TestClient, site_with_content: Site):
        """Test that home page contains site name."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert site_with_content.name in response.text
    
    def test_home_page_contains_hero(self, client: TestClient, site_with_content: Site):
        """Test that home page contains hero section."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'id="hero"' in response.text
        assert "Ihre Band für unvergessliche Momente" in response.text

    def test_home_page_renders_saved_line_breaks(self, client: TestClient, test_session: Session, site_with_content: Site):
        """Saved inline newlines render as safe HTML breaks on the public page."""
        content = test_session.query(SiteContent).filter_by(site_id=site_with_content.id).one()
        content.about_blocks[0]["content"] = "Erste Zeile\nZweite Zeile"
        flag_modified(content, "about_blocks")
        test_session.commit()

        response = client.get("/", params={"site_domain": site_with_content.domain})

        assert "Erste Zeile<br>\nZweite Zeile" in response.text
    
    def test_home_page_contains_navigation(self, client: TestClient, site_with_content: Site):
        """Test that home page contains navigation."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "nav-menu" in response.text
        assert "Referenzen" in response.text
        assert "Angebot" in response.text
        assert "Kontakt" in response.text
    
    def test_home_page_nonexistent_site(self, client: TestClient):
        """Test that nonexistent site returns 404."""
        response = client.get("/", params={"site_domain": "nonexistent.example.com"})
        
        assert response.status_code == 404
    
    def test_impressum_page(self, client: TestClient, site_with_content: Site):
        """Test that GET /impressum returns legal page."""
        response = client.get("/impressum", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Impressum" in response.text
    
    def test_datenschutz_page(self, client: TestClient, site_with_content: Site):
        """Test that GET /datenschutz returns privacy policy."""
        response = client.get("/datenschutz", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Datenschutz" in response.text
    
    def test_sitemap_xml(self, client: TestClient, site_with_content: Site):
        """Test that GET /sitemap.xml returns valid XML."""
        response = client.get("/sitemap.xml", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        assert '<?xml version="1.0"' in response.text
        assert "<urlset" in response.text
        assert f"https://{site_with_content.domain}/" in response.text
    
    def test_robots_txt(self, client: TestClient, site_with_content: Site):
        """Test that GET /robots.txt returns valid robots.txt."""
        response = client.get("/robots.txt", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "User-agent: *" in response.text
        assert "Allow: /" in response.text
        assert "Disallow: /admin/" in response.text
        assert "Sitemap:" in response.text
    
    def test_robots_txt_no_site(self, client: TestClient):
        """Test that robots.txt works even without a site."""
        response = client.get("/robots.txt", params={"site_domain": "nonexistent.example.com"})
        
        # Should return basic robots.txt even for nonexistent site
        assert response.status_code == 200
        assert "User-agent: *" in response.text


class TestModuleRendering:
    """Test module rendering in templates."""
    
    def test_services_module_renders(self, client: TestClient, site_with_content: Site):
        """Test that services module renders correctly."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'id="services"' in response.text
        assert "Hochzeiten" in response.text
        assert "Firmenevents" in response.text
    
    def test_trust_module_renders(self, client: TestClient, site_with_content: Site):
        """Test that trust/proof module renders correctly."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'id="trust"' in response.text
        # Check testimonials
        assert "Maria Müller" in response.text
        assert "fantastische Band" in response.text
    
    def test_about_module_renders(self, client: TestClient, site_with_content: Site):
        """Test that about module renders correctly."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'id="about"' in response.text
        assert "leidenschaftliche Band" in response.text
    
    def test_contact_module_renders(self, client: TestClient, site_with_content: Site):
        """Test that contact module renders correctly."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'id="contact"' in response.text
        assert "contact-form" in response.text
    
    def test_footer_module_renders(self, client: TestClient, site_with_content: Site):
        """Test that footer module renders correctly."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'id="footer"' in response.text
        assert "Impressum" in response.text
        assert "Datenschutz" in response.text
    
    def test_disabled_module_not_rendered(self, client: TestClient, test_session: Session, site_with_content: Site):
        """Test that disabled modules are not rendered."""
        # FAQ is available but not enabled by default for band
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        # The FAQ section should not be in the output
        # (it's "available" but not "enabled")
        assert 'id="faq"' not in response.text


class TestThemeSystem:
    """Test theme CSS variable system."""
    
    def test_theme_class_applied(self, client: TestClient, site_with_content: Site):
        """Test that theme class is applied to body."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'class="theme-clean"' in response.text
    
    def test_css_files_loaded(self, client: TestClient, site_with_content: Site):
        """Test that CSS files are referenced."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "/static/css/define.css" in response.text
        assert "/static/css/base.css" in response.text
        assert "/static/css/components.css" in response.text
    
    def test_static_css_files_exist(self, client: TestClient):
        """Test that static CSS files are served."""
        css_files = [
            "/static/css/define.css",
            "/static/css/base.css",
            "/static/css/components.css",
        ]
        
        for css_file in css_files:
            response = client.get(css_file)
            assert response.status_code == 200, f"CSS file {css_file} not found"
            assert "text/css" in response.headers["content-type"]
    
    def test_static_js_files_exist(self, client: TestClient):
        """Test that static JS files are served."""
        response = client.get("/static/js/nav.js")
        
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]


class TestAdminAffordances:
    """Test that admin affordances are properly hidden/shown."""
    
    def test_no_admin_toolbar_for_public(self, client: TestClient, site_with_content: Site):
        """Test that admin toolbar is not shown to public."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "admin-toolbar" not in response.text
    
    def test_no_editable_attributes_for_public(self, client: TestClient, site_with_content: Site):
        """Test that contenteditable is not present for public."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'contenteditable="true"' not in response.text
    
    def test_no_admin_css_for_public(self, client: TestClient, site_with_content: Site):
        """Test that admin CSS is not loaded for public."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "/static/css/admin.css" not in response.text


class TestSEO:
    """Test SEO features."""
    
    def test_meta_description_present(self, client: TestClient, site_with_content: Site):
        """Test that meta description is present."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert '<meta name="description"' in response.text
    
    def test_og_tags_present(self, client: TestClient, site_with_content: Site):
        """Test that Open Graph tags are present."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert '<meta property="og:type"' in response.text
        assert '<meta property="og:title"' in response.text
        assert '<meta property="og:url"' in response.text
    
    def test_schema_org_present(self, client: TestClient, site_with_content: Site):
        """Test that schema.org JSON-LD is present."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'application/ld+json' in response.text
        assert '"@context": "https://schema.org"' in response.text
    
    def test_legal_pages_noindex(self, client: TestClient, site_with_content: Site):
        """Test that legal pages have noindex meta tag."""
        response = client.get("/impressum", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert 'noindex' in response.text


class TestResponsiveNavigation:
    """Test responsive navigation elements."""
    
    def test_hamburger_menu_present(self, client: TestClient, site_with_content: Site):
        """Test that hamburger menu button is present."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "nav-toggle" in response.text
        assert "nav-toggle-bar" in response.text
    
    def test_nav_js_loaded(self, client: TestClient, site_with_content: Site):
        """Test that navigation JS is loaded."""
        response = client.get("/", params={"site_domain": site_with_content.domain})
        
        assert response.status_code == 200
        assert "/static/js/nav.js" in response.text
