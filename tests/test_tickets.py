"""Ticket endpoint tests."""

from httpx import AsyncClient


async def login_admin(client: AsyncClient) -> dict[str, str]:
    """Return auth headers for admin-only endpoints."""
    response = await client.post("/auth/login", json={"username": "admin", "password": "admin"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def create_company(client: AsyncClient) -> int:
    """Create a test company and return its ID."""
    response = await client.post(
        "/companies",
        json={
            "name": "Union Fenosa",
            "code": "UF",
            "description": "Distribuidora electrica.",
            "repo_branch": "feature/union-fenosa",
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


async def test_create_and_get_ticket(client: AsyncClient) -> None:
    """A ticket can be created and retrieved."""
    company_id = await create_company(client)
    payload = {
        "title": "Alta de nuevo suministro",
        "description": "Gestionar alta tecnica para un nuevo punto de suministro.",
        "company_id": company_id,
        "type": "historia_usuario",
        "priority": "alta",
        "assigned_user_id": 2,
    }

    create_response = await client.post("/tickets", json=payload)
    created = create_response.json()
    get_response = await client.get(f"/tickets/{created['id']}")

    assert create_response.status_code == 201
    assert created["status"] == "pendiente"
    assert created["assigned_user_id"] == 2
    assert get_response.status_code == 200
    assert get_response.json()["title"] == payload["title"]


async def test_create_ticket_auto_assigns_and_analyzes(client: AsyncClient) -> None:
    """Creating a ticket without assignee auto-assigns and creates an analysis."""
    company_id = await create_company(client)

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Tarea autoasignada",
            "description": "Clasificar automaticamente segun carga y prioridad de empresa.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "media",
        },
    )
    ticket = create_response.json()
    analyses_response = await client.get(f"/tickets/{ticket['id']}/analyses")

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] is not None
    assert ticket["status"] == "pendiente"
    assert analyses_response.status_code == 200
    assert analyses_response.json()[0]["estimated_hours"] > 0


async def test_create_ticket_requires_existing_company(client: AsyncClient) -> None:
    """A ticket cannot be created for an unknown company."""
    response = await client.post(
        "/tickets",
        json={
            "title": "Ticket sin empresa",
            "description": "Debe fallar porque la empresa no existe.",
            "company_id": 999,
            "type": "tarea",
            "priority": "media",
        },
    )

    assert response.status_code == 404


async def test_delete_ticket_requires_admin(client: AsyncClient) -> None:
    """Ticket deletion is protected by the admin role."""
    company_id = await create_company(client)
    create_response = await client.post(
        "/tickets",
        json={
            "title": "Ticket borrable",
            "description": "Debe poder borrarlo solo un admin.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "media",
        },
    )
    ticket_id = create_response.json()["id"]
    member_login = await client.post("/auth/login", json={"username": "Ignacio", "password": "ignacio"})
    admin_headers = await login_admin(client)

    forbidden = await client.delete(
        f"/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer {member_login.json()['access_token']}"},
    )
    deleted = await client.delete(f"/tickets/{ticket_id}", headers=admin_headers)

    assert forbidden.status_code == 403
    assert deleted.status_code == 204
