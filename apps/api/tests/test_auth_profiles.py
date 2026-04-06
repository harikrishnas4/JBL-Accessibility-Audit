from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_get_auth_profile(client: TestClient) -> None:
    run_id = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://example.com/course/private",
            "auth_metadata": {"method": "placeholder"},
        },
    ).json()["run_id"]

    create_response = client.post(
        "/auth-profiles",
        json={
            "run_id": run_id,
            "auth_context": {
                "role": "learner",
                "login_method": "manual_session_import",
                "captcha_bypassed_manually": True,
            },
            "session_state_path": "encrypted-blob-placeholder:manual-cookie-session",
            "validation_status": "validated",
        },
    )

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["auth_profile_id"]
    assert body["run_id"] == run_id
    assert body["auth_context"]["role"] == "learner"
    assert body["auth_context"]["captcha_bypassed_manually"] is True
    assert body["session_state_path"] == "encrypted-blob-placeholder:manual-cookie-session"
    assert body["validation_status"] == "validated"

    get_response = client.get(f"/auth-profiles/{body['auth_profile_id']}")

    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["auth_profile_id"] == body["auth_profile_id"]
    assert fetched["run_id"] == body["run_id"]
    assert fetched["auth_context"] == body["auth_context"]
    assert fetched["session_state_path"] == body["session_state_path"]
    assert fetched["validation_status"] == body["validation_status"]
    assert fetched["created_at"]


def test_create_auth_profile_requires_existing_run(client: TestClient) -> None:
    response = client.post(
        "/auth-profiles",
        json={
            "run_id": "missing-run",
            "auth_context": {"role": "admin"},
            "session_state_path": None,
            "validation_status": "pending",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "run 'missing-run' does not exist"}
