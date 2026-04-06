from __future__ import annotations

from fastapi.testclient import TestClient

from jbl_audit_api.main import create_app


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "JBL WCAG Audit API",
        "environment": "local",
    }
