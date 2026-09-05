"""SEO utilities for generating meta tags and structured data."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json


def generate_meta_tags(
    site_name: str,
    site_domain: str,
    site_type: str,
    headline: Optional[str] = None,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict[str, str]:
    """Generate meta tags for the site.
    
    Args:
        site_name: Name of the site.
        site_domain: Domain of the site.
        site_type: Type of site (band, rolfing, etc.)
        headline: Optional headline text for description.
        description: Optional custom description.
        image_url: Optional image URL for og:image.
        
    Returns:
        Dictionary of meta tag names to values.
    """
    # Generate description if not provided
    if not description:
        if headline:
            description = f"{site_name} - {headline}"
        else:
            description = site_name
    
    # Truncate description to 160 chars for SEO
    if len(description) > 160:
        description = description[:157] + "..."
    
    base_url = f"https://{site_domain}"
    
    meta_tags = {
        "description": description,
        "og:type": "website",
        "og:url": f"{base_url}/",
        "og:title": site_name,
        "og:description": description,
        "og:site_name": site_name,
        "twitter:card": "summary_large_image",
        "twitter:title": site_name,
        "twitter:description": description,
    }
    
    if image_url:
        # Ensure absolute URL
        if not image_url.startswith("http"):
            image_url = f"{base_url}{image_url}"
        meta_tags["og:image"] = image_url
        meta_tags["twitter:image"] = image_url
    
    return meta_tags


def generate_schema_org(
    site_name: str,
    site_domain: str,
    site_type: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    social_links: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Generate schema.org JSON-LD structured data.
    
    Args:
        site_name: Name of the site/business.
        site_domain: Domain of the site.
        site_type: Type of site (band, rolfing, etc.)
        phone: Optional phone number.
        email: Optional email address.
        address: Optional address.
        social_links: Optional list of social media URLs.
        
    Returns:
        Dictionary representing schema.org JSON-LD.
    """
    base_url = f"https://{site_domain}"
    
    # Determine schema type based on site type
    schema_type = "MusicGroup" if site_type == "band" else "LocalBusiness"
    
    schema = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "name": site_name,
        "url": base_url,
    }
    
    if phone:
        schema["telephone"] = phone
    
    if email:
        schema["email"] = email
    
    if address:
        schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": address,
        }
    
    if social_links:
        schema["sameAs"] = social_links
    
    return schema


def generate_faq_schema(faq_items: List[Dict[str, str]]) -> Dict[str, Any]:
    """Generate FAQPage schema.org JSON-LD.
    
    Args:
        faq_items: List of FAQ items with 'question' and 'answer' keys.
        
    Returns:
        Dictionary representing FAQPage schema.org JSON-LD.
    """
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": item["answer"],
                },
            }
            for item in faq_items
        ],
    }


def generate_sitemap_xml(
    site_domain: str,
    last_modified: str,
    include_legal: bool = True,
) -> str:
    """Generate sitemap.xml content.
    
    Args:
        site_domain: Domain of the site.
        last_modified: ISO date string for lastmod.
        include_legal: Whether to include legal pages.
        
    Returns:
        XML string for sitemap.
    """
    base_url = f"https://{site_domain}"
    
    urls = [
        {
            "loc": f"{base_url}/",
            "lastmod": last_modified,
            "changefreq": "weekly",
            "priority": "1.0",
        },
    ]
    
    if include_legal:
        urls.extend([
            {
                "loc": f"{base_url}/impressum",
                "lastmod": last_modified,
                "changefreq": "monthly",
                "priority": "0.3",
            },
            {
                "loc": f"{base_url}/datenschutz",
                "lastmod": last_modified,
                "changefreq": "monthly",
                "priority": "0.3",
            },
        ])
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for url in urls:
        xml_parts.append("    <url>")
        xml_parts.append(f"        <loc>{url['loc']}</loc>")
        xml_parts.append(f"        <lastmod>{url['lastmod']}</lastmod>")
        xml_parts.append(f"        <changefreq>{url['changefreq']}</changefreq>")
        xml_parts.append(f"        <priority>{url['priority']}</priority>")
        xml_parts.append("    </url>")
    
    xml_parts.append("</urlset>")
    
    return "\n".join(xml_parts)


def generate_robots_txt(site_domain: str) -> str:
    """Generate robots.txt content.
    
    Args:
        site_domain: Domain of the site.
        
    Returns:
        Text content for robots.txt.
    """
    base_url = f"https://{site_domain}"
    
    return f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: {base_url}/sitemap.xml
"""


def schema_to_json_ld(schema: Dict[str, Any]) -> str:
    """Convert schema dictionary to JSON-LD script tag content.
    
    Args:
        schema: Schema.org dictionary.
        
    Returns:
        JSON string for embedding in script tag.
    """
    return json.dumps(schema, ensure_ascii=False, indent=2)
