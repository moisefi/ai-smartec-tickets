"""Ticket analysis endpoint tests."""

from httpx import AsyncClient


async def test_analyze_ticket(client: AsyncClient) -> None:
    """Analyze endpoint persists and returns mock technical analysis."""
    company_response = await client.post(
        "/companies",
        json={"name": "EDP", "code": "EDP", "description": "Empresa electrica."},
    )
    company_id = company_response.json()["id"]
    ticket_response = await client.post(
        "/tickets",
        json={
            "title": "Cambio regulatorio",
            "description": "Adaptar el flujo de validacion por cambio regulatorio.",
            "company_id": company_id,
            "type": "bug",
            "priority": "urgente",
        },
    )
    ticket_id = ticket_response.json()["id"]

    response = await client.post(f"/tickets/{ticket_id}/analyze")

    assert response.status_code == 201
    body = response.json()
    assert body["ticket_id"] == ticket_id
    assert body["complexity"] == "alta"
    assert body["estimated_hours"] >= 28
    assert "app/api/routes/tickets.py" in body["affected_files"]
    assert body["risks"]
    assert body["recommended_tasks"]
    assert body["proposed_changes"]
    assert "Pendiente de desarrollar" in body["proposed_changes"][0]["change"]
