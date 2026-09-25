from fastapi.testclient import TestClient

from app.core.config import settings


def test_health_check(client: TestClient) -> None:
    """Verify that the health check endpoint returns 200 OK and expected payload."""
    response = client.get(f"{settings.API_V1_PREFIX}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == settings.ENVIRONMENT
    assert data["project"] == settings.PROJECT_NAME


def test_openapi_schema(client: TestClient) -> None:
    """Verify that OpenAPI documentation schema is generated and accessible."""
    response = client.get(f"{settings.API_V1_PREFIX}/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == settings.PROJECT_NAME
