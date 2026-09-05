"""Database connection and session management."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.base import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _engine
    
    if _engine is None:
        settings = get_settings()
        
        # Ensure data directory exists for SQLite
        if settings.database_url.startswith("sqlite:///"):
            db_path = settings.database_url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
        )
        logger.info(f"Database engine created: {settings.database_url}")
    
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _SessionLocal
    
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions (non-FastAPI use)."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(engine: Engine | None = None) -> None:
    """Initialize the database by creating all tables.
    
    Args:
        engine: SQLAlchemy engine. If None, uses the default engine.
    """
    if engine is None:
        engine = get_engine()
    
    # Import all models to ensure they're registered with Base
    # This will be extended as more models are added
    from app.models import Base  # noqa: F401
    
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")


def check_db_connection(engine: Engine | None = None) -> bool:
    """Check if the database is accessible.
    
    Args:
        engine: SQLAlchemy engine. If None, uses the default engine.
        
    Returns:
        True if database is accessible, False otherwise.
    """
    if engine is None:
        engine = get_engine()
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def reset_engine() -> None:
    """Reset the global engine and session factory.
    
    Useful for testing to ensure clean state.
    """
    global _engine, _SessionLocal
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
    
    _SessionLocal = None
    logger.info("Database engine reset")
