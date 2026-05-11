"""Company endpoint tests."""

from httpx import AsyncClient


async def login_admin(client: AsyncClient) -> dict[str, str]:
    """Return auth headers for admin-only endpoints."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_create_and_list_companies(client: AsyncClient) -> None:
    """A company can be created and listed."""
    payload = {
        "name": "Iberdrola",
        "code": "IBE",
        "description": "Empresa electrica para pruebas.",
        "repo_url": "https://github.com/moisefi/Serisa_Control_Fichajes.git",
        "repo_branch": "master",
    }

    create_response = await client.post("/companies", json=payload)
    list_response = await client.get("/companies")

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "Iberdrola"
    assert created["code"] == "IBE"
    assert created["repo_url"] == "https://github.com/moisefi/Serisa_Control_Fichajes.git"
    assert created["repo_branch"] == "master"
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created["id"]


async def test_create_duplicate_company_returns_conflict(client: AsyncClient) -> None:
    """Duplicate company codes are reported as a conflict."""
    payload = {
        "name": "TAQA",
        "code": "TAQA",
        "description": "Empresa electrica para pruebas.",
    }

    first_response = await client.post("/companies", json=payload)
    second_response = await client.post("/companies", json={**payload, "name": "TAQA Energia"})

    assert first_response.status_code == 201
    assert second_response.status_code == 409


async def test_delete_company_requires_admin(client: AsyncClient) -> None:
    """Company deletion is protected by the admin role."""
    create_response = await client.post(
        "/companies",
        json={"name": "DeleteCo", "code": "DEL", "description": "Temporal."},
    )
    company_id = create_response.json()["id"]
    member_login = await client.post("/auth/login", json={"username": "Ignacio", "password": "ignacio"})
    admin_headers = await login_admin(client)

    forbidden = await client.delete(
        f"/companies/{company_id}",
        headers={"Authorization": f"Bearer {member_login.json()['access_token']}"},
    )
    deleted = await client.delete(f"/companies/{company_id}", headers=admin_headers)

    assert forbidden.status_code == 403
    assert deleted.status_code == 204
