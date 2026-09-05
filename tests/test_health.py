"""Tests for the health check endpoint."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_200_when_db_connected(self, client: TestClient):
        """Health endpoint should return 200 when database is connected."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] == "connected"

    def test_health_response_structure(self, client: TestClient):
        """Health response should have expected structure."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields exist
        assert "status" in data
        assert "db" in data

    def test_health_returns_json(self, client: TestClient):
        """Health endpoint should return JSON content type."""
        response = client.get("/health")
        
        assert "application/json" in response.headers["content-type"]
