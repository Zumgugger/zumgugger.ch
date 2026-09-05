"""FastAPI application factory and main entry point."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import init_db, get_engine, check_db_connection, get_db_context
from app.routes import health, admin, public, admin_content, images, contact
from app.schema_upgrades import initialize_schema
from app.utils.storage import ensure_directories, cleanup_temp_files
from app.middleware.maintenance import MaintenanceMiddleware

logger = logging.getLogger(__name__)

# Initialize Jinja2 templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Path to site.config.json (exported from Builder)
SITE_CONFIG_PATH = Path(__file__).parent.parent / "site.config.json"


async def seed_from_config_if_needed():
    """Seed database from site.config.json if no sites exist (production mode).
    
    This allows exported sites to auto-initialize their database on first startup
    without requiring manual database seeding.
    """
    from app.models.site import Site, AdminUser
    from app.models.content import SiteContent
    from app.models.site_config import SiteConfig
    from app.seeds import load_seed
    
    # Check if site.config.json exists
    if not SITE_CONFIG_PATH.exists():
        logger.debug("No site.config.json found, skipping production seed")
        return
    
    try:
        with get_db_context() as db:
            # Check if any site exists
            existing_site = db.query(Site).first()
            if existing_site:
                logger.debug(f"Site already exists: {existing_site.domain}")
                return
            
            # Load site config
            with open(SITE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                site_config = json.load(f)
            
            logger.info("No sites found, seeding from site.config.json...")
            
            site_type = site_config.get("site_type", "band")
            seed = load_seed(site_type)
            
            # Create site
            site = Site(
                domain=site_config.get("domain", "localhost"),
                site_type=site_type,
                name=site_config.get("sitename", "Website"),
            )
            db.add(site)
            db.flush()
            
            # Create content from seed
            content = SiteContent(
                site_id=site.id,
                **seed["content"]
            )
            db.add(content)
            
            # Create config from seed (with any overrides from site.config.json)
            config_data = seed["config"].copy()
            if site_config.get("css_variables"):
                config_data["css_variables"] = site_config["css_variables"]
            if site_config.get("theme"):
                config_data["theme_name"] = site_config["theme"]
            
            config = SiteConfig(
                site_id=site.id,
                theme_name=config_data.get("theme_name", "clean"),
                module_states=config_data.get("module_states", {}),
                module_order=config_data.get("module_order", []),
                css_variables=config_data.get("css_variables", {}),
                nav_labels=config_data.get("nav_labels", {}),
            )
            db.add(config)
            
            # Create admin users from credentials in site.config.json
            admin_creds = site_config.get("admin_credentials", {})
            
            # Agency admin (required)
            agency_username = admin_creds.get("agency_username", "agency")
            agency_password_hash = admin_creds.get("agency_password_hash")
            
            if agency_password_hash:
                agency_admin = AdminUser(
                    site_id=site.id,
                    username=agency_username,
                )
                # Set password hash directly (already hashed by Builder)
                agency_admin.password_hash = agency_password_hash
                db.add(agency_admin)
                logger.info(f"Agency admin created: {agency_username}")
            else:
                logger.warning("No agency password hash in site.config.json!")
            
            # Customer admin (optional)
            customer_username = admin_creds.get("customer_username")
            customer_password_hash = admin_creds.get("customer_password_hash")
            
            if customer_username and customer_password_hash:
                customer_admin = AdminUser(
                    site_id=site.id,
                    username=customer_username,
                )
                customer_admin.password_hash = customer_password_hash
                db.add(customer_admin)
                logger.info(f"Customer admin created: {customer_username}")
            
            db.commit()
            logger.info(f"Site seeded from config: {site.name} (domain: {site.domain})")
            
    except Exception as e:
        logger.error(f"Failed to seed from site.config.json: {e}")
        raise  # Re-raise so deployment knows something went wrong


async def create_demo_site_if_needed():
    """Create a demo site if no sites exist (for development)."""
    from app.models.site import Site, AdminUser
    from app.models.content import SiteContent
    from app.models.site_config import SiteConfig
    from app.seeds import load_seed
    
    try:
        with get_db_context() as db:
            # Check if any site exists
            existing_site = db.query(Site).first()
            if existing_site:
                return
            
            logger.info("No sites found, creating demo site...")
            
            # Create demo site with band seed
            seed = load_seed("band")
            
            site = Site(
                domain="localhost",
                site_type="band",
                name="Demo Band",
            )
            db.add(site)
            db.flush()
            
            # Create content
            content = SiteContent(
                site_id=site.id,
                **seed["content"]
            )
            db.add(content)
            
            # Create config
            config = SiteConfig(
                site_id=site.id,
                theme_name=seed["config"]["theme_name"],
                module_states=seed["config"]["module_states"],
                module_order=seed["config"]["module_order"],
                css_variables=seed["config"].get("css_variables", {}),
                nav_labels=seed["config"].get("nav_labels", {}),
            )
            db.add(config)
            
            # Create admin user
            admin_user = AdminUser(
                site_id=site.id,
                username="admin",
            )
            admin_user.set_password("admin")  # Simple password for demo
            db.add(admin_user)
            
            db.commit()
            logger.info(f"Demo site created: {site.name} (domain: {site.domain})")
            logger.info("Demo admin credentials: username='admin', password='admin'")
            
    except Exception as e:
        logger.error(f"Failed to create demo site: {e}")


async def cleanup_expired_sessions_on_startup():
    """Clean up expired sessions on application startup."""
    from app.middleware.auth import cleanup_expired_sessions
    
    try:
        with get_db_context() as db:
            count = await cleanup_expired_sessions(db)
            if count > 0:
                logger.info(f"Cleaned up {count} expired sessions on startup")
    except Exception as e:
        logger.warning(f"Failed to cleanup expired sessions on startup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting WebsiteCMS application...")
    
    settings = get_settings()
    settings.configure_logging()
    
    # Ensure storage directories exist
    ensure_directories()
    
    # Clean up old temp files
    cleanup_temp_files(max_age_hours=24)
    
    # Initialize database
    engine = get_engine()
    
    # Check if this is a fresh database
    db_path = settings.database_url.replace("sqlite:///", "")
    is_fresh_db = not Path(db_path).exists()
    
    # Create tables
    init_db(engine)
    
    # Initialize or upgrade schema versioning
    initialize_schema(engine)
    
    # Verify database connection
    if check_db_connection(engine):
        logger.info("Database connection verified")
    else:
        logger.error("Failed to connect to database!")
    
    # Create demo site if no sites exist (development mode)
    if settings.debug:
        await create_demo_site_if_needed()
    else:
        # Production mode: seed from site.config.json if available
        await seed_from_config_if_needed()
    
    # Clean up expired sessions
    await cleanup_expired_sessions_on_startup()
    
    # Configure email client
    if settings.smtp_host:
        from app.utils.email import configure_email_client
        configure_email_client(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            from_address=settings.smtp_from,
            use_tls=settings.smtp_tls,
            use_starttls=settings.smtp_starttls,
        )
        logger.info(f"Email client configured with SMTP host: {settings.smtp_host}")
    
    # Configure SMS client
    if settings.sms_enabled and settings.twilio_account_sid:
        from app.utils.sms import configure_sms_client
        configure_sms_client(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            from_number=settings.twilio_from_number,
            enabled=settings.sms_enabled,
        )
        logger.info("SMS client configured with Twilio")
    
    # Configure CAPTCHA verifier
    if settings.captcha_enabled and settings.turnstile_secret_key:
        from app.utils.captcha import configure_captcha_verifier
        configure_captcha_verifier(
            secret_key=settings.turnstile_secret_key,
            site_key=settings.turnstile_site_key,
            enabled=settings.captcha_enabled,
        )
        logger.info("CAPTCHA verifier configured with Cloudflare Turnstile")
    
    logger.info(f"WebsiteCMS started on port {settings.port}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down WebsiteCMS application...")


async def render_404_page(request: Request) -> HTMLResponse:
    """Render the styled 404 error page.
    
    Args:
        request: The incoming request.
        
    Returns:
        HTMLResponse with styled 404 page.
    """
    from app.routes.public import get_site_from_request, get_template_context
    from app.models.session import AdminSession
    
    # Try to get site context for theming
    try:
        with get_db_context() as db:
            site = get_site_from_request(request, db)
            if site and site.content and site.config:
                # Get admin status for template
                session_token = request.cookies.get("session")
                is_admin = False
                if session_token:
                    session = db.query(AdminSession).filter(AdminSession.token == session_token).first()
                    is_admin = session is not None and not session.is_expired()
                
                context = get_template_context(site, site.content, site.config, is_admin)
                context["request"] = request
                return templates.TemplateResponse(request, "404.html", context, status_code=404)
    except Exception as e:
        logger.warning(f"Error getting site context for 404 page: {e}")
    
    # Fallback: simple 404 without site context
    return templates.TemplateResponse(request, "404.html", {
        "request": request,
        "site": {"name": "Website", "domain": "localhost", "type": "business"},
        "theme": "clean",
        "css_variables": {},
        "nav_items": [],
        "config": None,
        "is_admin": False,
    }, status_code=404)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()
    settings.configure_logging()
    
    app = FastAPI(
        title="WebsiteCMS",
        description="A simple CMS for generating one-page websites",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )
    
    # Include routers
    app.include_router(health.router)
    app.include_router(admin.router)
    app.include_router(admin_content.router)
    app.include_router(images.router)
    app.include_router(contact.router)
    app.include_router(public.router)
    
    # Add maintenance mode middleware
    app.add_middleware(MaintenanceMiddleware)
    
    # Add custom 404 exception handler
    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc: StarletteHTTPException):
        """Custom 404 handler to show styled error page."""
        return await render_404_page(request)
    
    # Mount static files if directory exists
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    logger.info("FastAPI application created")
    
    return app


# Create the app instance for uvicorn
app = create_app()
