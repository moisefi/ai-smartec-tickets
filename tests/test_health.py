"""Healthcheck tests."""

from httpx import AsyncClient


async def test_healthcheck(client: AsyncClient) -> None:
    """Healthcheck returns service status."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "AI SmartEC Tickets"}


async def test_openapi_schema_is_available(client: AsyncClient) -> None:
    """OpenAPI schema is exposed for Swagger UI."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    assert body["info"]["title"] == "AI SmartEC Tickets"
    assert "/tickets/{ticket_id}/analyze" in body["paths"]
    assert "/users" in body["paths"]
