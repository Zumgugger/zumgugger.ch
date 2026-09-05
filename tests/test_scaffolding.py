"""Tests to verify project scaffolding is complete."""

from pathlib import Path

import pytest


# Get project root directory (site_template/)
PROJECT_ROOT = Path(__file__).parent.parent

# Get repo root directory (parent of site_template/)
REPO_ROOT = PROJECT_ROOT.parent


class TestProjectStructure:
    """Tests to verify required project files and folders exist."""

    def test_app_package_exists(self):
        """app/ package should exist with __init__.py."""
        app_dir = PROJECT_ROOT / "app"
        assert app_dir.is_dir()
        assert (app_dir / "__init__.py").is_file()

    def test_models_package_exists(self):
        """app/models/ package should exist."""
        models_dir = PROJECT_ROOT / "app" / "models"
        assert models_dir.is_dir()
        assert (models_dir / "__init__.py").is_file()
        assert (models_dir / "base.py").is_file()

    def test_routes_package_exists(self):
        """app/routes/ package should exist."""
        routes_dir = PROJECT_ROOT / "app" / "routes"
        assert routes_dir.is_dir()
        assert (routes_dir / "__init__.py").is_file()
        assert (routes_dir / "health.py").is_file()

    def test_utils_package_exists(self):
        """app/utils/ package should exist."""
        utils_dir = PROJECT_ROOT / "app" / "utils"
        assert utils_dir.is_dir()
        assert (utils_dir / "__init__.py").is_file()

    def test_templates_directory_exists(self):
        """app/templates/ directory should exist."""
        templates_dir = PROJECT_ROOT / "app" / "templates"
        assert templates_dir.is_dir()

    def test_static_directories_exist(self):
        """app/static/css and app/static/js directories should exist."""
        static_dir = PROJECT_ROOT / "app" / "static"
        assert static_dir.is_dir()
        assert (static_dir / "css").is_dir()
        assert (static_dir / "js").is_dir()

    def test_tests_package_exists(self):
        """tests/ package should exist."""
        tests_dir = PROJECT_ROOT / "tests"
        assert tests_dir.is_dir()
        assert (tests_dir / "__init__.py").is_file()
        assert (tests_dir / "conftest.py").is_file()

    def test_data_directory_exists(self):
        """data/ directory should exist."""
        data_dir = PROJECT_ROOT / "data"
        assert data_dir.is_dir()

    def test_core_app_files_exist(self):
        """Core app files should exist."""
        app_dir = PROJECT_ROOT / "app"
        assert (app_dir / "config.py").is_file()
        assert (app_dir / "database.py").is_file()
        assert (app_dir / "main.py").is_file()
        assert (app_dir / "schema_upgrades.py").is_file()

    def test_project_config_files_exist(self):
        """Project configuration files should exist."""
        assert (PROJECT_ROOT / "requirements.txt").is_file()
        assert (PROJECT_ROOT / "pyproject.toml").is_file()
        assert (PROJECT_ROOT / ".env.example").is_file()
        # .gitignore is at the repo root level (covers both Builder and Site Template)
        assert (REPO_ROOT / ".gitignore").is_file()

    def test_docker_files_exist(self):
        """Docker configuration files should exist."""
        assert (PROJECT_ROOT / "Dockerfile").is_file()
        assert (PROJECT_ROOT / "docker-compose.yml").is_file()
        assert (PROJECT_ROOT / ".dockerignore").is_file()

    def test_run_script_exists(self):
        """run.py entry point should exist."""
        assert (PROJECT_ROOT / "run.py").is_file()


class TestModuleImports:
    """Tests to verify all modules can be imported."""

    def test_import_app(self):
        """Should be able to import app package."""
        import app
        assert hasattr(app, "__version__")

    def test_import_config(self):
        """Should be able to import config module."""
        from app.config import Settings, get_settings
        assert Settings is not None
        assert get_settings is not None

    def test_import_database(self):
        """Should be able to import database module."""
        from app.database import get_db, init_db, check_db_connection
        assert get_db is not None
        assert init_db is not None
        assert check_db_connection is not None

    def test_import_main(self):
        """Should be able to import main module."""
        from app.main import create_app
        assert create_app is not None

    def test_import_models(self):
        """Should be able to import models."""
        from app.models import Base, BaseMixin
        assert Base is not None
        assert BaseMixin is not None

    def test_import_health_route(self):
        """Should be able to import health route."""
        from app.routes.health import router
        assert router is not None

    def test_import_schema_upgrades(self):
        """Should be able to import schema upgrades."""
        from app.schema_upgrades import SCHEMA_VERSION, initialize_schema
        assert SCHEMA_VERSION is not None
        assert initialize_schema is not None
