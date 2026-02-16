"""
Unit and integration tests for the API service.
Run: pytest tests/ -v
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """Create a test client for the FastAPI app."""
    # Set test environment before importing the app
    import os
    os.environ.setdefault("ENVIRONMENT", "testing")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing")
    os.environ.setdefault("REDIS_PASSWORD", "")
    os.environ.setdefault("POSTGRES_HOST", "localhost")

    from api_service.app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoints:
    """Test health, readiness, and liveness probes."""

    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "api"

    @pytest.mark.asyncio
    async def test_liveness(self, client):
        response = await client.get("/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"


class TestAuthEndpoints:
    """Test registration, login, and token refresh."""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "SecurePass123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        # Register first user
        await client.post(
            "/auth/register",
            json={
                "email": "dup@example.com",
                "username": "user1",
                "password": "SecurePass123",
            },
        )
        # Try to register with same email
        response = await client.post(
            "/auth/register",
            json={
                "email": "dup@example.com",
                "username": "user2",
                "password": "SecurePass123",
            },
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        # Register
        await client.post(
            "/auth/register",
            json={
                "email": "login@example.com",
                "username": "loginuser",
                "password": "SecurePass123",
            },
        )
        # Login
        response = await client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "SecurePass123"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client):
        response = await client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "WrongPass"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_input_validation_short_password(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "val@example.com",
                "username": "valuser",
                "password": "short",
            },
        )
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_input_validation_invalid_email(self, client):
        response = await client.post(
            "/auth/register",
            json={
                "email": "not-an-email",
                "username": "valuser2",
                "password": "SecurePass123",
            },
        )
        assert response.status_code == 422


class TestRBAC:
    """Test role-based access control."""

    @pytest.mark.asyncio
    async def test_admin_endpoint_requires_admin(self, client):
        # Register a regular user
        reg_response = await client.post(
            "/auth/register",
            json={
                "email": "regular@example.com",
                "username": "regular",
                "password": "SecurePass123",
            },
        )
        token = reg_response.json()["access_token"]

        # Try to access admin endpoint
        response = await client.post(
            "/admin/retrain",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_request(self, client):
        response = await client.get("/books")
        assert response.status_code == 403  # No token provided


class TestBookEndpoints:
    """Test book CRUD operations."""

    @pytest.mark.asyncio
    async def test_list_books_requires_auth(self, client):
        response = await client.get("/books")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_nonexistent_book(self, client):
        # Register and get token
        reg = await client.post(
            "/auth/register",
            json={
                "email": "booktest@example.com",
                "username": "booktest",
                "password": "SecurePass123",
            },
        )
        token = reg.json()["access_token"]

        response = await client.get(
            "/books/99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestMetrics:
    """Test Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "http_requests_total" in response.text
