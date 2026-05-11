"""User endpoint tests."""

from httpx import AsyncClient


async def login_admin(client: AsyncClient) -> dict[str, str]:
    """Return auth headers for admin-only endpoints."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_seed_users_are_available(client: AsyncClient) -> None:
    """Base users are available in test setup."""
    response = await client.get("/users")

    assert response.status_code == 200
    usernames = {user["username"] for user in response.json()}
    assert {"admin", "Sergio", "Ignacio"}.issubset(usernames)
    roles = {user["username"]: user["role"] for user in response.json()}
    assert roles["admin"] == "admin"
    assert roles["Sergio"] == "admin"
    assert roles["Ignacio"] == "member"


async def test_create_user_with_company_priority(client: AsyncClient) -> None:
    """A user can be created with ordered company priorities."""
    admin_headers = await login_admin(client)
    company_response = await client.post(
        "/companies",
        json={"name": "Areti", "code": "ARETI", "description": "Empresa demo.", "repo_branch": "feature/areti"},
    )
    company_id = company_response.json()["id"]

    response = await client.post(
        "/users",
        json={
            "username": "demo",
            "password": "demo",
            "full_name": "Usuario Demo",
            "company_priorities": [{"company_id": company_id, "priority_order": 1}],
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "demo"
    assert body["company_priorities"][0]["company_id"] == company_id


async def test_delete_user_requires_admin(client: AsyncClient) -> None:
    """Only admin users can delete users."""
    admin_headers = await login_admin(client)
    create_response = await client.post(
        "/users",
        json={"username": "delete_me", "password": "delete_me", "full_name": "Delete Me"},
        headers=admin_headers,
    )
    user_id = create_response.json()["id"]
    member_login = await client.post("/auth/login", json={"username": "Ignacio", "password": "ignacio"})

    forbidden = await client.delete(
        f"/users/{user_id}",
        headers={"Authorization": f"Bearer {member_login.json()['access_token']}"},
    )
    deleted = await client.delete(f"/users/{user_id}", headers=admin_headers)

    assert forbidden.status_code == 403
    assert deleted.status_code == 204


async def test_update_user_can_change_password(client: AsyncClient) -> None:
    """Admins can edit existing users and change their password."""
    admin_headers = await login_admin(client)

    update_response = await client.put(
        "/users/3",
        json={"full_name": "Ignacio Editado", "password": "nueva-clave"},
        headers=admin_headers,
    )
    old_login = await client.post("/auth/login", json={"username": "Ignacio", "password": "ignacio"})
    new_login = await client.post("/auth/login", json={"username": "Ignacio", "password": "nueva-clave"})

    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Ignacio Editado"
    assert old_login.status_code == 401
    assert new_login.status_code == 200
