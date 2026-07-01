"""Authentication endpoint tests."""

from httpx import AsyncClient


async def test_login_returns_token_and_role(client: AsyncClient) -> None:
    """A valid user can start a session."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["role"] == "admin"


async def test_login_accepts_exact_sergio_username(client: AsyncClient) -> None:
    """Sergio can start a session with the seeded credentials."""
    response = await client.post("/auth/login", json={"username": "Sergio", "password": "sergio"})

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user"]["username"] == "Sergio"


async def test_login_rejects_wrong_username_case(client: AsyncClient) -> None:
    """Username matching remains case-sensitive."""
    response = await client.post("/auth/login", json={"username": "sergio", "password": "sergio"})

    assert response.status_code == 401


async def test_login_rejects_invalid_password(client: AsyncClient) -> None:
    """Invalid credentials are rejected."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
