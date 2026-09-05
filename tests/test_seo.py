"""Tests for SEO utilities (Phase 4.4)."""

from __future__ import annotations

import json
import pytest

from app.utils.seo import (
    generate_meta_tags,
    generate_schema_org,
    generate_faq_schema,
    generate_sitemap_xml,
    generate_robots_txt,
    schema_to_json_ld,
)


class TestGenerateMetaTags:
    """Test meta tag generation."""
    
    def test_basic_meta_tags(self):
        """Test basic meta tag generation."""
        meta = generate_meta_tags(
            site_name="Test Site",
            site_domain="example.com",
            site_type="band",
        )
        
        assert meta["og:title"] == "Test Site"
        assert meta["og:type"] == "website"
        assert meta["og:url"] == "https://example.com/"
        assert "description" in meta
    
    def test_meta_tags_with_headline(self):
        """Test meta tags with headline."""
        meta = generate_meta_tags(
            site_name="Test Site",
            site_domain="example.com",
            site_type="band",
            headline="Welcome to our site",
        )
        
        assert "Welcome to our site" in meta["description"]
    
    def test_meta_tags_with_custom_description(self):
        """Test meta tags with custom description."""
        meta = generate_meta_tags(
            site_name="Test Site",
            site_domain="example.com",
            site_type="band",
            description="Custom description here",
        )
        
        assert meta["description"] == "Custom description here"
    
    def test_meta_tags_truncates_long_description(self):
        """Test that long descriptions are truncated."""
        long_desc = "A" * 200
        meta = generate_meta_tags(
            site_name="Test Site",
            site_domain="example.com",
            site_type="band",
            description=long_desc,
        )
        
        assert len(meta["description"]) <= 160
        assert meta["description"].endswith("...")
    
    def test_meta_tags_with_image(self):
        """Test meta tags with image URL."""
        meta = generate_meta_tags(
            site_name="Test Site",
            site_domain="example.com",
            site_type="band",
            image_url="/uploads/hero.jpg",
        )
        
        assert meta["og:image"] == "https://example.com/uploads/hero.jpg"
        assert meta["twitter:image"] == "https://example.com/uploads/hero.jpg"
    
    def test_meta_tags_with_absolute_image_url(self):
        """Test meta tags with absolute image URL."""
        meta = generate_meta_tags(
            site_name="Test Site",
            site_domain="example.com",
            site_type="band",
            image_url="https://cdn.example.com/image.jpg",
        )
        
        assert meta["og:image"] == "https://cdn.example.com/image.jpg"


class TestGenerateSchemaOrg:
    """Test schema.org structured data generation."""
    
    def test_basic_schema(self):
        """Test basic schema generation."""
        schema = generate_schema_org(
            site_name="Test Band",
            site_domain="testband.com",
            site_type="band",
        )
        
        assert schema["@context"] == "https://schema.org"
        assert schema["@type"] == "MusicGroup"
        assert schema["name"] == "Test Band"
        assert schema["url"] == "https://testband.com"
    
    def test_schema_for_business(self):
        """Test schema generation for business."""
        schema = generate_schema_org(
            site_name="Rolfing Practice",
            site_domain="rolfing.com",
            site_type="rolfing",
        )
        
        assert schema["@type"] == "LocalBusiness"
    
    def test_schema_with_contact_info(self):
        """Test schema with contact information."""
        schema = generate_schema_org(
            site_name="Test",
            site_domain="test.com",
            site_type="band",
            phone="+41791234567",
            email="info@test.com",
            address="123 Main St, Zurich",
        )
        
        assert schema["telephone"] == "+41791234567"
        assert schema["email"] == "info@test.com"
        assert schema["address"]["@type"] == "PostalAddress"
        assert schema["address"]["streetAddress"] == "123 Main St, Zurich"
    
    def test_schema_with_social_links(self):
        """Test schema with social media links."""
        schema = generate_schema_org(
            site_name="Test",
            site_domain="test.com",
            site_type="band",
            social_links=[
                "https://instagram.com/test",
                "https://facebook.com/test",
            ],
        )
        
        assert "sameAs" in schema
        assert len(schema["sameAs"]) == 2


class TestGenerateFaqSchema:
    """Test FAQ schema generation."""
    
    def test_faq_schema(self):
        """Test FAQ schema generation."""
        faq_items = [
            {"question": "What is this?", "answer": "A test."},
            {"question": "How does it work?", "answer": "It just works."},
        ]
        
        schema = generate_faq_schema(faq_items)
        
        assert schema["@context"] == "https://schema.org"
        assert schema["@type"] == "FAQPage"
        assert len(schema["mainEntity"]) == 2
        assert schema["mainEntity"][0]["@type"] == "Question"
        assert schema["mainEntity"][0]["name"] == "What is this?"
        assert schema["mainEntity"][0]["acceptedAnswer"]["@type"] == "Answer"
        assert schema["mainEntity"][0]["acceptedAnswer"]["text"] == "A test."
    
    def test_empty_faq_schema(self):
        """Test FAQ schema with empty list."""
        schema = generate_faq_schema([])
        
        assert schema["@type"] == "FAQPage"
        assert schema["mainEntity"] == []


class TestGenerateSitemapXml:
    """Test sitemap.xml generation."""
    
    def test_basic_sitemap(self):
        """Test basic sitemap generation."""
        sitemap = generate_sitemap_xml(
            site_domain="example.com",
            last_modified="2026-02-02",
        )
        
        assert '<?xml version="1.0"' in sitemap
        assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in sitemap
        assert "<loc>https://example.com/</loc>" in sitemap
        assert "<priority>1.0</priority>" in sitemap
    
    def test_sitemap_includes_legal_pages(self):
        """Test that sitemap includes legal pages by default."""
        sitemap = generate_sitemap_xml(
            site_domain="example.com",
            last_modified="2026-02-02",
        )
        
        assert "<loc>https://example.com/impressum</loc>" in sitemap
        assert "<loc>https://example.com/datenschutz</loc>" in sitemap
    
    def test_sitemap_without_legal_pages(self):
        """Test sitemap without legal pages."""
        sitemap = generate_sitemap_xml(
            site_domain="example.com",
            last_modified="2026-02-02",
            include_legal=False,
        )
        
        assert "<loc>https://example.com/impressum</loc>" not in sitemap
        assert "<loc>https://example.com/datenschutz</loc>" not in sitemap
    
    def test_sitemap_valid_xml_structure(self):
        """Test that sitemap has valid XML structure."""
        sitemap = generate_sitemap_xml(
            site_domain="example.com",
            last_modified="2026-02-02",
        )
        
        # Check it's well-formed XML (basic check)
        assert sitemap.count("<url>") == sitemap.count("</url>")
        assert sitemap.endswith("</urlset>")


class TestGenerateRobotsTxt:
    """Test robots.txt generation."""
    
    def test_basic_robots(self):
        """Test basic robots.txt generation."""
        robots = generate_robots_txt("example.com")
        
        assert "User-agent: *" in robots
        assert "Allow: /" in robots
        assert "Disallow: /admin/" in robots
        assert "Disallow: /api/" in robots
    
    def test_robots_includes_sitemap(self):
        """Test that robots.txt includes sitemap reference."""
        robots = generate_robots_txt("example.com")
        
        assert "Sitemap: https://example.com/sitemap.xml" in robots


class TestSchemaToJsonLd:
    """Test schema to JSON-LD conversion."""
    
    def test_schema_to_json(self):
        """Test converting schema to JSON string."""
        schema = {
            "@context": "https://schema.org",
            "@type": "MusicGroup",
            "name": "Test Band",
        }
        
        json_ld = schema_to_json_ld(schema)
        
        # Verify it's valid JSON
        parsed = json.loads(json_ld)
        assert parsed["@type"] == "MusicGroup"
    
    def test_schema_preserves_unicode(self):
        """Test that JSON-LD preserves unicode characters."""
        schema = {
            "@context": "https://schema.org",
            "name": "Über uns",
        }
        
        json_ld = schema_to_json_ld(schema)
        
        assert "Über uns" in json_ld
