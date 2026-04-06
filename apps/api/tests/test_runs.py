from __future__ import annotations

from fastapi.testclient import TestClient


def test_post_runs_creates_run_and_defaults_to_partial_without_manifest(client: TestClient) -> None:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://example.com/course/accessibility-101",
            "auth_metadata": {"method": "placeholder", "has_credentials": False},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"]
    assert body["status"] == "queued"
    assert body["current_stage"] == "intake"
    assert body["mode"] == "partial"
    assert body["run_plan"]["status"] == "awaiting_assets"
    assert body["run_plan"]["dispatcher_name"] == "local_in_process"
    assert body["run_plan"]["scan_batch_count"] == 0
    assert body["run_plan"]["manual_task_count"] == 0
    assert body["run_plan"]["scan_batches"] == []
    assert "created_at" in body
    assert "updated_at" in body


def test_get_run_returns_typed_run_details(client: TestClient) -> None:
    create_response = client.post(
        "/runs",
        json={
            "course_url_or_name": "JBL Accessibility Foundations",
            "auth_metadata": {"method": "placeholder", "username": "reviewer@example.com"},
            "manifest_metadata": {"source": "upload", "filename": "manifest.json"},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["status"] == "queued"
    assert body["current_stage"] == "intake"
    assert body["mode"] == "manifest/full"
    assert body["audit_input"]["course_url_or_name"] == "JBL Accessibility Foundations"
    assert body["audit_input"]["auth_metadata"] == {
        "method": "placeholder",
        "username": "reviewer@example.com",
    }
    assert body["audit_input"]["manifest_metadata"] == {
        "source": "upload",
        "filename": "manifest.json",
    }
    assert body["schema_registry_entries"] == []
    assert body["report_records"] == []
    assert body["run_plan"]["status"] == "awaiting_assets"
    assert body["run_plan"]["scan_batches"] == []
