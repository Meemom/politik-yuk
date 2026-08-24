from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Politik Yuk",
        "environment": "test",
    }


def test_ready_endpoint_reports_dependency_statuses() -> None:
    client = TestClient(app)

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Politik Yuk"
    assert payload["status"] in {"ok", "degraded", "unavailable"}
    dependency_names = {dependency["name"] for dependency in payload["dependencies"]}
    assert dependency_names == {
        "model_provider",
        "search_provider",
        "postgres",
        "redis",
        "worker_queue",
    }
