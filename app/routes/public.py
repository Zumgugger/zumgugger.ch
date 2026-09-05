"""Public-facing routes for WebsiteCMS."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.site import Site
from app.models.content import SiteContent
from app.models.site_config import SiteConfig
from app.middleware.auth import get_optional_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])


def get_site_from_request(request: Request, db: Session) -> Optional[Site]:
    """Get the site based on request host or query parameter.
    
    Args:
        request: The incoming request.
        db: Database session.
        
    Returns:
        Site if found, None otherwise.
    """
    # For development/testing, allow site_domain query param
    site_domain = request.query_params.get("site_domain")
    
    if not site_domain:
        # Extract from Host header
        host = request.headers.get("host", "localhost")
        # Remove port if present
        site_domain = host.split(":")[0]
    
    # Try to find the site
    site = db.query(Site).filter(Site.domain == site_domain).first()
    
    # If not found and domain is localhost, try to get the first site (dev mode)
    if not site and site_domain in ("localhost", "127.0.0.1"):
        site = db.query(Site).first()
    
    return site


def get_template_context(site: Site, content: SiteContent, config: SiteConfig, is_admin: bool = False) -> dict:
    """Build the template context for rendering.
    
    Args:
        site: The site model.
        content: The site content model.
        config: The site config model.
        is_admin: Whether the current user is an admin.
        
    Returns:
        Dictionary containing all template context data.
    """
    enabled_modules = config.get_enabled_modules()
    
    # Build navigation items (exclude hero and footer)
    nav_items = []
    for module_type in enabled_modules:
        if module_type not in ("hero", "footer"):
            label = config.get_nav_label(module_type)
            if label:  # Only add if label is not empty
                nav_items.append({
                    "type": module_type,
                    "label": label,
                    "anchor": f"#{module_type}",
                })
    
    # Build module data for enabled modules
    modules = []
    for module_type in enabled_modules:
        module_data = content.get_module_data(module_type)
        modules.append({
            "type": module_type,
            "data": module_data,
            "anchor_id": module_type,
            "title": config.get_nav_label(module_type),
            "enabled": True,
        })
    
    # For admins, build a complete module list (enabled + available) in correct order for eye mode
    all_modules_ordered = []
    if is_admin:
        module_order = config.module_order or []
        for module_type in module_order:
            state = config.module_states.get(module_type)
            if state == "enabled":
                # Find the module data from the already-built modules list
                module_data = content.get_module_data(module_type)
                all_modules_ordered.append({
                    "type": module_type,
                    "data": module_data,
                    "anchor_id": module_type,
                    "title": config.get_nav_label(module_type),
                    "enabled": True,
                })
            elif state == "available":
                module_data = content.get_module_data(module_type)
                all_modules_ordered.append({
                    "type": module_type,
                    "data": module_data,
                    "anchor_id": module_type,
                    "title": config.get_nav_label(module_type),
                    "enabled": False,
                })
    
    # Get analytics settings
    settings = get_settings()
    
    return {
        "site": {
            "name": site.name,
            "domain": site.domain,
            "type": site.site_type,
        },
        "theme": config.theme_name,
        "css_variables": config.css_variables or {},
        "nav_items": nav_items,
        "modules": modules,  # Enabled modules only (for public view)
        "all_modules_ordered": all_modules_ordered,  # All modules in order (for admin eye mode)
        "content": content,
        "config": config,
        "is_admin": is_admin,
        "current_year": datetime.now(timezone.utc).year,
        # Analytics settings
        "analytics_enabled": settings.analytics_enabled,
        "plausible_domain": settings.plausible_domain,
        "plausible_script_src": settings.plausible_script_src,
        # Maintenance mode
        "maintenance_mode": settings.maintenance_mode,
    }


@router.get("/", response_class=HTMLResponse)
async def render_site(
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_optional_admin),
):
    """Render the full one-page website.
    
    Args:
        request: The incoming request.
        db: Database session.
        admin: Optional admin user if logged in.
        
    Returns:
        Rendered HTML page.
    """
    from app.main import templates
    
    site = get_site_from_request(request, db)
    
    if not site:
        # Raise 404 to trigger custom exception handler
        raise HTTPException(status_code=404, detail="Site not found")
    
    # Get content and config
    content = site.content
    config = site.config
    
    if not content or not config:
        return HTMLResponse(
            content="<html><body><h1>Site not configured</h1></body></html>",
            status_code=500,
        )
    
    is_admin = admin is not None
    context = get_template_context(site, content, config, is_admin)
    context["request"] = request
    
    return templates.TemplateResponse(request, "base.html", context)


@router.get("/impressum", response_class=HTMLResponse)
async def render_impressum(
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_optional_admin),
):
    """Render the Impressum (legal notice) page.
    
    Args:
        request: The incoming request.
        db: Database session.
        admin: Optional admin user if logged in.
        
    Returns:
        Rendered HTML page.
    """
    from app.main import templates
    
    site = get_site_from_request(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    content = site.content
    config = site.config
    
    if not content or not config:
        return HTMLResponse(
            content="<html><body><h1>Site not configured</h1></body></html>",
            status_code=500,
        )
    
    is_admin = admin is not None
    context = get_template_context(site, content, config, is_admin)
    context["request"] = request
    context["page_title"] = "Impressum"
    context["legal_content"] = content.impressum_content or "<p>Impressum nicht verfügbar.</p>"
    
    return templates.TemplateResponse(request, "legal.html", context)


@router.get("/datenschutz", response_class=HTMLResponse)
async def render_datenschutz(
    request: Request,
    db: Session = Depends(get_db),
    admin = Depends(get_optional_admin),
):
    """Render the Datenschutz (privacy policy) page.
    
    Args:
        request: The incoming request.
        db: Database session.
        admin: Optional admin user if logged in.
        
    Returns:
        Rendered HTML page.
    """
    from app.main import templates
    
    site = get_site_from_request(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    content = site.content
    config = site.config
    
    if not content or not config:
        return HTMLResponse(
            content="<html><body><h1>Site not configured</h1></body></html>",
            status_code=500,
        )
    
    is_admin = admin is not None
    context = get_template_context(site, content, config, is_admin)
    context["request"] = request
    context["page_title"] = "Datenschutzerklärung"
    context["legal_content"] = content.datenschutz_content or "<p>Datenschutzerklärung nicht verfügbar.</p>"
    
    return templates.TemplateResponse(request, "legal.html", context)


@router.get("/sitemap.xml")
async def sitemap(
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate sitemap.xml for the site.
    
    Args:
        request: The incoming request.
        db: Database session.
        
    Returns:
        XML sitemap response.
    """
    site = get_site_from_request(request, db)
    
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    
    base_url = f"https://{site.domain}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{base_url}/</loc>
        <lastmod>{now}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>{base_url}/impressum</loc>
        <lastmod>{now}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.3</priority>
    </url>
    <url>
        <loc>{base_url}/datenschutz</loc>
        <lastmod>{now}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.3</priority>
    </url>
</urlset>'''
    
    return Response(
        content=xml_content,
        media_type="application/xml",
    )


@router.get("/robots.txt")
async def robots_txt(
    request: Request,
    db: Session = Depends(get_db),
):
    """Generate robots.txt for the site.
    
    Args:
        request: The incoming request.
        db: Database session.
        
    Returns:
        Text robots.txt response.
    """
    site = get_site_from_request(request, db)
    
    if not site:
        # Return a basic robots.txt even if site not found
        return Response(
            content="User-agent: *\nDisallow: /admin/\n",
            media_type="text/plain",
        )
    
    base_url = f"https://{site.domain}"
    
    content = f'''User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: {base_url}/sitemap.xml
'''
    
    return Response(
        content=content,
        media_type="text/plain",
    )
