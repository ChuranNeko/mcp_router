"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.mcp.router import MCPRouter
from src.utils.security import SecurityManager


@pytest.fixture
def test_client_with_auth(router: MCPRouter, security_manager: SecurityManager) -> TestClient:
    """Create test client with authentication."""
    app = create_app(router, security_manager)
    return TestClient(app)


@pytest.fixture
def test_client_no_auth(router: MCPRouter, security_manager_no_auth: SecurityManager) -> TestClient:
    """Create test client without authentication."""
    app = create_app(router, security_manager_no_auth)
    return TestClient(app)


def test_root_endpoint(test_client_no_auth: TestClient):
    """Test root endpoint."""
    response = test_client_no_auth.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_health_endpoint(test_client_no_auth: TestClient):
    """Test health check endpoint."""
    response = test_client_no_auth.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_list_instances_no_auth(test_client_no_auth: TestClient):
    """Test listing instances without authentication."""
    response = test_client_no_auth.get("/api/instances")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_instances_with_auth_missing_token(test_client_with_auth: TestClient):
    """Test listing instances with authentication but missing token."""
    response = test_client_with_auth.get("/api/instances")
    assert response.status_code == 401


def test_list_instances_with_auth_valid_token(test_client_with_auth: TestClient):
    """Test listing instances with valid authentication token."""
    headers = {"Authorization": "Bearer test_token"}
    response = test_client_with_auth.get("/api/instances", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_instances_with_auth_invalid_token(test_client_with_auth: TestClient):
    """Test listing instances with invalid authentication token."""
    headers = {"Authorization": "Bearer wrong_token"}
    response = test_client_with_auth.get("/api/instances", headers=headers)
    assert response.status_code == 401


def test_list_tools(test_client_no_auth: TestClient):
    """Test listing all tools."""
    response = test_client_no_auth.get("/api/tools")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_get_config(test_client_no_auth: TestClient):
    """Test getting configuration."""
    response = test_client_no_auth.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "instances" in data

