import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "login@example.com", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "login@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "wrong@example.com", "password": "correct"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "wrong@example.com", "password": "incorrect"},
    )
    assert response.status_code == 401
