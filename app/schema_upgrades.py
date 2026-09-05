"""Schema versioning and upgrade management.

This module provides simple schema versioning without Alembic.

Rationale:
- Each site is generated fresh from the Builder with a new DB
- Schema changes during development can simply recreate the DB
- For production upgrades, simple version-based scripts are sufficient
"""

from __future__ import annotations

import logging
import json
from typing import Callable, Dict, Tuple

from sqlalchemy import Column, Integer, String, Table, MetaData, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Current schema version - increment when adding upgrade functions
SCHEMA_VERSION = 5


def upgrade_v1_to_v2(engine: Engine) -> None:
    """Upgrade from schema v1 to v2.
    
    Changes in v2:
    - Added Site, AdminUser, SiteContent, SiteConfig, ContentChange models
    - These are created by SQLAlchemy create_all() if missing
    
    For fresh databases, this is a no-op since tables are created from scratch.
    For existing v1 databases, the tables should already be created by create_all().
    """
    logger.info("Applying schema v2 upgrade (Phase 2 models)")
    # No-op: SQLAlchemy create_all() handles the new tables
    # This function exists to satisfy the upgrade path requirement


def upgrade_v2_to_v3(engine: Engine) -> None:
    """Upgrade from schema v2 to v3.
    
    Changes in v3:
    - Added logo_image and favicon_image columns to site_config table
    """
    logger.info("Applying schema v3 upgrade (logo and favicon fields)")
    
    with engine.begin() as conn:
        # Check if columns already exist
        result = conn.execute(text("PRAGMA table_info(site_config)"))
        columns = {row[1] for row in result.fetchall()}
        
        if "logo_image" not in columns:
            conn.execute(text(
                "ALTER TABLE site_config ADD COLUMN logo_image VARCHAR(255)"
            ))
            logger.info("Added logo_image column to site_config")
        
        if "favicon_image" not in columns:
            conn.execute(text(
                "ALTER TABLE site_config ADD COLUMN favicon_image VARCHAR(255)"
            ))
            logger.info("Added favicon_image column to site_config")


def upgrade_v3_to_v4(engine: Engine) -> None:
    """Upgrade from schema v3 to v4 by adding the repertoire module."""
    logger.info("Applying schema v4 upgrade (repertoire module)")

    with engine.begin() as conn:
        result = conn.execute(text("PRAGMA table_info(site_content)"))
        columns = {row[1] for row in result.fetchall()}
        if "repertoire_entries" not in columns:
            conn.execute(text("ALTER TABLE site_content ADD COLUMN repertoire_entries JSON"))
            logger.info("Added repertoire_entries column to site_content")

        configs = conn.execute(text("SELECT id, module_states, module_order FROM site_config")).fetchall()
        for config_id, module_states, module_order in configs:
            states = json.loads(module_states) if module_states else {}
            order = json.loads(module_order) if module_order else []
            states.setdefault("repertoire", "enabled")
            if "repertoire" not in order:
                insert_at = order.index("about") + 1 if "about" in order else len(order)
                order.insert(insert_at, "repertoire")
            conn.execute(
                text("UPDATE site_config SET module_states = :states, module_order = :order WHERE id = :id"),
                {"id": config_id, "states": json.dumps(states), "order": json.dumps(order)},
            )


def upgrade_v4_to_v5(engine: Engine) -> None:
    """Upgrade from schema v4 to v5 with an editable repertoire introduction."""
    logger.info("Applying schema v5 upgrade (editable repertoire introduction)")

    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(site_content)"))}
        if "repertoire_intro" not in columns:
            conn.execute(text("ALTER TABLE site_content ADD COLUMN repertoire_intro VARCHAR(500)"))
            logger.info("Added repertoire_intro column to site_content")


# Schema version table definition
metadata = MetaData()
schema_version_table = Table(
    "schema_version",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
    Column("description", String(255), nullable=True),
)

# Dictionary of upgrade functions: version -> (description, upgrade_function)
# Each function takes an engine and performs the upgrade
UPGRADES: Dict[int, Tuple[str, Callable[[Engine], None]]] = {
    2: ("Phase 2 models: Site, AdminUser, SiteContent, SiteConfig, ContentChange", upgrade_v1_to_v2),
    3: ("Phase 15: Logo and favicon fields in SiteConfig", upgrade_v2_to_v3),
    4: ("Repertoire module", upgrade_v3_to_v4),
    5: ("Editable repertoire introduction", upgrade_v4_to_v5),
}


def ensure_schema_version_table(engine: Engine) -> None:
    """Create the schema_version table if it doesn't exist."""
    metadata.create_all(bind=engine, tables=[schema_version_table])


def get_schema_version(engine: Engine) -> int:
    """Get the current schema version from the database.
    
    Returns:
        Current schema version, or 0 if no version is set.
    """
    ensure_schema_version_table(engine)
    
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT version FROM schema_version ORDER BY id DESC LIMIT 1")
        )
        row = result.fetchone()
        return row[0] if row else 0


def set_schema_version(engine: Engine, version: int, description: str = "") -> None:
    """Set the schema version in the database.
    
    Args:
        engine: SQLAlchemy engine
        version: New schema version number
        description: Optional description of the version
    """
    ensure_schema_version_table(engine)
    
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO schema_version (version, description) VALUES (:version, :description)"
            ),
            {"version": version, "description": description},
        )
    
    logger.info(f"Schema version set to {version}: {description}")


def upgrade_schema(engine: Engine, from_version: int, to_version: int) -> None:
    """Upgrade the database schema from one version to another.
    
    Args:
        engine: SQLAlchemy engine
        from_version: Current schema version
        to_version: Target schema version
        
    Raises:
        ValueError: If upgrade path is not available
    """
    if from_version >= to_version:
        logger.info(f"Schema already at version {from_version}, no upgrade needed")
        return
    
    for version in range(from_version + 1, to_version + 1):
        if version not in UPGRADES:
            raise ValueError(
                f"No upgrade function defined for version {version}. "
                f"Cannot upgrade from {from_version} to {to_version}."
            )
        
        description, upgrade_func = UPGRADES[version]
        logger.info(f"Upgrading schema to version {version}: {description}")
        
        upgrade_func(engine)
        set_schema_version(engine, version, description)
    
    logger.info(f"Schema upgrade complete: {from_version} -> {to_version}")


def initialize_schema(engine: Engine) -> None:
    """Initialize schema versioning for a fresh database.
    
    This should be called after creating all tables on a new database.
    """
    current = get_schema_version(engine)
    
    if current == 0:
        set_schema_version(engine, SCHEMA_VERSION, "Initial schema")
        logger.info(f"Initialized schema at version {SCHEMA_VERSION}")
    elif current < SCHEMA_VERSION:
        logger.info(f"Schema needs upgrade from {current} to {SCHEMA_VERSION}")
        upgrade_schema(engine, current, SCHEMA_VERSION)
    else:
        logger.info(f"Schema is up to date at version {current}")
