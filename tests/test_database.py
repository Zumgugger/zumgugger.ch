"""Tests for database functionality."""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from app.models.base import Base, BaseMixin
from app.database import (
    init_db,
    check_db_connection,
    get_db_context,
)
from app.schema_upgrades import (
    get_schema_version,
    set_schema_version,
    initialize_schema,
    upgrade_v3_to_v4,
    SCHEMA_VERSION,
)


class TestDatabaseConnection:
    """Tests for database connection functionality."""

    def test_check_db_connection_success(self, test_engine):
        """Should return True when database is accessible."""
        assert check_db_connection(test_engine) is True

    def test_check_db_connection_failure(self):
        """Should return False when database is not accessible."""
        # Create engine with invalid path
        bad_engine = create_engine(
            "sqlite:///nonexistent_directory_12345/test.db",
            connect_args={"check_same_thread": False},
        )
        
        # This will fail because the directory doesn't exist
        result = check_db_connection(bad_engine)
        assert result is False

    def test_init_db_creates_tables(self, temp_db_path):
        """init_db should create all tables."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        
        init_db(engine)
        
        # Check that we can query the database
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        
        engine.dispose()

    def test_init_db_is_idempotent(self, temp_db_path):
        """Calling init_db twice should not cause errors."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        
        # Call init_db twice
        init_db(engine)
        init_db(engine)  # Should not raise
        
        # Verify database still works
        assert check_db_connection(engine) is True
        
        engine.dispose()


class TestSchemaVersioning:
    """Tests for schema version management."""

    def test_get_schema_version_fresh_db(self, temp_db_path):
        """Fresh database should have version 0."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        
        version = get_schema_version(engine)
        assert version == 0
        
        engine.dispose()

    def test_set_schema_version(self, temp_db_path):
        """Should be able to set and retrieve schema version."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        
        set_schema_version(engine, 5, "Test version")
        version = get_schema_version(engine)
        
        assert version == 5
        
        engine.dispose()

    def test_initialize_schema_fresh_db(self, temp_db_path):
        """initialize_schema should set version on fresh database."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        
        # Initialize
        init_db(engine)
        initialize_schema(engine)
        
        # Check version is set to current
        version = get_schema_version(engine)
        assert version == SCHEMA_VERSION
        
        engine.dispose()

    def test_initialize_schema_existing_db(self, temp_db_path):
        """initialize_schema should not change version on up-to-date database."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )
        
        # Set version manually
        set_schema_version(engine, SCHEMA_VERSION, "Existing")
        
        # Initialize again
        initialize_schema(engine)
        
        # Version should remain the same
        version = get_schema_version(engine)
        assert version == SCHEMA_VERSION
        
        engine.dispose()

    def test_upgrade_v3_to_v4_adds_repertoire_column(self, temp_db_path):
        """Existing databases receive repertoire storage and module configuration."""
        engine = create_engine(
            f"sqlite:///{temp_db_path}",
            connect_args={"check_same_thread": False},
        )

        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE site_content (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE site_config (id INTEGER PRIMARY KEY, site_id INTEGER, theme_name TEXT, module_states JSON, module_order JSON)"))
            conn.execute(text("INSERT INTO site_config (site_id, theme_name, module_states, module_order) VALUES (1, 'clean', '{\"about\": \"enabled\"}', '[\"about\"]')"))

        upgrade_v3_to_v4(engine)

        with engine.connect() as conn:
            columns = {column["name"] for column in inspect(conn).get_columns("site_content")}
            config = conn.execute(text("SELECT module_states, module_order FROM site_config WHERE site_id = 1")).one()

        assert "repertoire_entries" in columns
        assert '"repertoire": "enabled"' in config.module_states
        assert config.module_order == '["about", "repertoire"]'

        engine.dispose()


class TestBaseMixin:
    """Tests for BaseMixin model functionality."""

    def test_base_mixin_has_required_fields(self):
        """BaseMixin should define id, created_at, updated_at."""
        # Check that the mixin has the expected attributes
        assert hasattr(BaseMixin, 'id')
        assert hasattr(BaseMixin, 'created_at')
        assert hasattr(BaseMixin, 'updated_at')
