"""Tests for FastAPI application factory."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


class TestAppFactory:
    """Tests for create_app function."""

    def test_create_app_returns_fastapi_instance(self):
        """create_app should return a FastAPI application."""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_has_title(self):
        """Application should have a title configured."""
        app = create_app()
        assert app.title == "WebsiteCMS"

    def test_app_has_version(self):
        """Application should have a version configured."""
        app = create_app()
        assert app.version == "0.1.0"

    def test_app_includes_health_router(self):
        """Application should include the health router."""
        app = create_app()
        
        # Check that /health route exists
        routes = [route.path for route in app.routes]
        assert "/health" in routes

    def test_app_openapi_schema(self):
        """Application should generate valid OpenAPI schema."""
        app = create_app()
        
        with TestClient(app) as client:
            response = client.get("/openapi.json")
            assert response.status_code == 200
            
            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert schema["info"]["title"] == "WebsiteCMS"

    def test_app_docs_endpoint(self):
        """Application should serve Swagger UI docs."""
        app = create_app()
        
        with TestClient(app) as client:
            response = client.get("/docs")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    def test_app_redoc_endpoint(self):
        """Application should serve ReDoc docs."""
        app = create_app()
        
        with TestClient(app) as client:
            response = client.get("/redoc")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
