"""Ticket endpoint tests."""

from pathlib import Path

from httpx import AsyncClient

from app.api.routes import tickets as tickets_route
from app.api.routes.analysis import get_analyzer
from app.main import app
from app.services.analysis import GeneratedTicketAnalysis, MockTicketImpactAnalyzer
from app.services.repository import RepositorySnapshot


class FailingAnalyzer:
    """Analyzer test double that simulates an external AI outage."""

    async def analyze(self, ticket) -> None:
        raise RuntimeError("OpenAI unavailable")


class UnexpectedAnalyzer:
    """Analyzer test double that must not be called."""

    async def analyze(self, ticket) -> None:
        raise AssertionError("AI analyzer should not be called")


class InaccessibleRepositoryReader:
    """Repository reader test double that simulates a Git access failure."""

    async def snapshot_for_company(self, company, ticket_text: str) -> RepositorySnapshot:
        return RepositorySnapshot(
            repo_url=company.repo_url,
            branch=company.repo_branch or "master",
            local_path=Path("."),
            candidate_files=[],
            read_error="Repository not found",
        )


class FixedAnalyzer:
    """Analyzer test double with controlled complexity."""

    def __init__(self, complexity: str, required_skill_level: str, estimated_hours: int) -> None:
        self.complexity = complexity
        self.required_skill_level = required_skill_level
        self.estimated_hours = estimated_hours

    async def analyze(self, ticket) -> GeneratedTicketAnalysis:
        return GeneratedTicketAnalysis(
            complexity=self.complexity,
            required_skill_level=self.required_skill_level,
            estimated_hours=self.estimated_hours,
            affected_files=["app/example.py"],
            risks=[],
            technical_summary="Analisis de prueba.",
            recommended_tasks=[],
            proposed_changes=[],
        )


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


async def test_create_ticket_auto_assigns_and_analyzes(client: AsyncClient, monkeypatch) -> None:
    """Creating a ticket without assignee auto-assigns and creates an analysis."""
    monkeypatch.setattr(tickets_route, "get_configured_analyzer", lambda: MockTicketImpactAnalyzer())
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
    assert ticket["assigned_user_id"] == 3
    assert ticket["status"] == "pendiente"
    assert analyses_response.status_code == 200
    assert analyses_response.json()[0]["estimated_hours"] > 0
    assert analyses_response.json()[0]["required_skill_level"] == "mid"


async def test_create_high_complexity_ticket_prefers_senior_user(client: AsyncClient, monkeypatch) -> None:
    """High-complexity tickets are assigned to a user with enough skill."""
    monkeypatch.setattr(tickets_route, "get_configured_analyzer", lambda: MockTicketImpactAnalyzer())
    admin_headers = await login_admin(client)
    company_response = await client.post(
        "/companies",
        json={"name": "SkillCo", "code": "SKILL", "description": "Empresa demo."},
    )
    company_id = company_response.json()["id"]
    junior_response = await client.post(
        "/users",
        json={
            "username": "junior_user",
            "password": "junior_user",
            "skill_level": "junior",
            "company_priorities": [{"company_id": company_id, "priority_order": 1}],
        },
        headers=admin_headers,
    )

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Incidencia critica de facturacion",
            "description": "Corregir un fallo urgente en el calculo de facturacion.",
            "company_id": company_id,
            "type": "incidencia",
            "priority": "urgente",
        },
    )
    ticket = create_response.json()
    analyses_response = await client.get(f"/tickets/{ticket['id']}/analyses")

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] != junior_response.json()["id"]
    assert ticket["assigned_user_id"] == 2
    assert analyses_response.json()[0]["required_skill_level"] == "senior"


async def test_create_low_complexity_ticket_prefers_junior_user(client: AsyncClient, monkeypatch) -> None:
    """Low-complexity tickets are assigned to junior users first."""
    monkeypatch.setattr(tickets_route, "get_configured_analyzer", lambda: FixedAnalyzer("baja", "junior", 4))
    admin_headers = await login_admin(client)
    company_response = await client.post(
        "/companies",
        json={"name": "LowCo", "code": "LOW", "description": "Empresa demo."},
    )
    company_id = company_response.json()["id"]
    junior_response = await client.post(
        "/users",
        json={
            "username": "junior_low",
            "password": "junior_low",
            "skill_level": "junior",
            "company_priorities": [{"company_id": company_id, "priority_order": 1}],
        },
        headers=admin_headers,
    )

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Cambio menor",
            "description": "Ajustar texto de validacion.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "baja",
        },
    )
    ticket = create_response.json()

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] == junior_response.json()["id"]


async def test_create_low_complexity_ticket_falls_back_to_mid_user(client: AsyncClient, monkeypatch) -> None:
    """Low-complexity tickets fall back to mid users when no junior is available."""
    monkeypatch.setattr(tickets_route, "get_configured_analyzer", lambda: FixedAnalyzer("baja", "junior", 4))
    company_id = await create_company(client)

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Cambio menor sin junior",
            "description": "Ajustar texto de validacion sin junior disponible.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "baja",
        },
    )
    ticket = create_response.json()

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] == 3


async def test_create_ticket_never_auto_assigns_admin_user(client: AsyncClient) -> None:
    """Admin is not used as an automatic ticket assignee."""
    admin_headers = await login_admin(client)
    company_id = await create_company(client)
    await client.put("/users/2", json={"is_active": False}, headers=admin_headers)
    await client.put("/users/3", json={"is_active": False}, headers=admin_headers)

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Ticket sin asignable",
            "description": "Debe quedar sin usuario asignado si solo esta activo admin.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "media",
        },
    )
    ticket = create_response.json()

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] is None
    assert ticket["assigned_to"] is None


async def test_create_ticket_survives_initial_analysis_failure(client: AsyncClient, monkeypatch) -> None:
    """A ticket can be created without AI analysis and analyzed later."""
    monkeypatch.setattr(tickets_route, "get_configured_analyzer", lambda: FailingAnalyzer())
    company_id = await create_company(client)

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Ticket con OpenAI caido",
            "description": "Debe crearse aunque el proveedor IA falle temporalmente.",
            "company_id": company_id,
            "type": "incidencia",
            "priority": "urgente",
        },
    )
    ticket = create_response.json()
    initial_analyses = await client.get(f"/tickets/{ticket['id']}/analyses")

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] is None
    assert ticket["analysis_error"] == "No se ha podido analizar con la IA: error generico."
    assert initial_analyses.status_code == 200
    assert initial_analyses.json() == []

    app.dependency_overrides[get_analyzer] = lambda: MockTicketImpactAnalyzer()
    retry_response = await client.post(f"/tickets/{ticket['id']}/analyze")
    updated_ticket = await client.get(f"/tickets/{ticket['id']}")

    assert retry_response.status_code == 201
    assert retry_response.json()["required_skill_level"] == "senior"
    assert updated_ticket.json()["assigned_user_id"] == 2


async def test_create_ticket_skips_ai_when_repository_cannot_be_read(client: AsyncClient, monkeypatch) -> None:
    """A repository access failure creates a basic ticket without invoking AI."""
    monkeypatch.setattr(tickets_route, "RepositoryReader", lambda: InaccessibleRepositoryReader())
    monkeypatch.setattr(tickets_route, "get_configured_analyzer", lambda: UnexpectedAnalyzer())
    company_response = await client.post(
        "/companies",
        json={
            "name": "RepoCaido",
            "code": "REPO",
            "description": "Empresa con repo inaccesible.",
            "repo_url": "https://git.example.invalid/repo.git",
            "repo_branch": "main",
        },
    )
    company_id = company_response.json()["id"]

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Ticket sin repo",
            "description": "Debe crearse basico si el repo no se puede leer.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "media",
        },
    )
    ticket = create_response.json()
    analyses_response = await client.get(f"/tickets/{ticket['id']}/analyses")

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] is None
    assert ticket["analysis_error"] == (
        "No se ha podido acceder al repositorio. Se ha creado un ticket basico sin analisis IA."
    )
    assert analyses_response.json() == []


async def test_create_ticket_without_configured_ai_has_no_fake_estimate(client: AsyncClient) -> None:
    """No complexity, hours, or automatic assignment are produced without configured AI."""
    company_id = await create_company(client)

    create_response = await client.post(
        "/tickets",
        json={
            "title": "Ticket sin IA",
            "description": "Debe crearse sin valoracion falsa si no hay IA configurada.",
            "company_id": company_id,
            "type": "tarea",
            "priority": "media",
        },
    )
    ticket = create_response.json()
    analyses_response = await client.get(f"/tickets/{ticket['id']}/analyses")

    assert create_response.status_code == 201
    assert ticket["assigned_user_id"] is None
    assert ticket["analysis_error"] == "No se ha podido analizar con la IA: no hay IA configurada."
    assert analyses_response.json() == []


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
