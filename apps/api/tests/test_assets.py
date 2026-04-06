from __future__ import annotations

from fastapi.testclient import TestClient


def build_run(client: TestClient) -> str:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://courses.example.com/course/view.php?id=42",
            "auth_metadata": {"method": "session-state", "auth_context": "learner"},
        },
    )
    return response.json()["run_id"]


def test_post_assets_upsert_persists_snapshot_and_assets(client: TestClient) -> None:
    run_id = build_run(client)

    response = client.post(
        "/assets/upsert",
        json={
            "run_id": run_id,
            "crawl_snapshot": {
                "entry_locator": "https://courses.example.com/course/view.php?id=42",
                "started_at": "2026-04-06T10:00:00Z",
                "completed_at": "2026-04-06T10:05:00Z",
                "visited_locators": [
                    "https://courses.example.com/course/view.php?id=42",
                    "https://courses.example.com/mod/page/view.php?id=10",
                ],
                "excluded_locators": [
                    {
                        "locator": "https://courses.example.com/mod/forum/view.php?id=88",
                        "reason": "unsupported_module_path",
                    },
                ],
                "snapshot_metadata": {
                    "supported_path_patterns": ["mod/page", "mod/url", "mod/quiz", "mod/lti"],
                    "asset_count": 2,
                },
            },
            "assets": [
                {
                    "asset_id": "asset-page-10",
                    "asset_type": "course_module_page",
                    "source_system": "moodle",
                    "locator": "https://courses.example.com/mod/page/view.php?id=10",
                    "scope_status": "in_scope",
                    "layer": "course_module",
                    "shared_key": "shared-page-10",
                    "owner_team": "accessibility",
                    "auth_context": {"role": "learner"},
                    "handling_path": "mod/page",
                    "component_fingerprint": {
                        "stable_css_selector": "a#module-page-10",
                        "template_id": "course-module-link",
                        "bundle_name": "view.php",
                        "controlled_dom_signature": "sig-page-10",
                    },
                    "updated_at": "2026-04-06T10:05:00Z",
                },
                {
                    "asset_id": "asset-forum-88",
                    "asset_type": "unsupported_module",
                    "source_system": "moodle",
                    "locator": "https://courses.example.com/mod/forum/view.php?id=88",
                    "scope_status": "out_of_scope",
                    "scope_reason": "unsupported_module_path",
                    "layer": "course_module",
                    "shared_key": "shared-forum-88",
                    "owner_team": None,
                    "auth_context": {"role": "learner"},
                    "handling_path": "mod/forum",
                    "component_fingerprint": {
                        "stable_css_selector": "a#module-forum-88",
                        "template_id": "course-module-link",
                        "bundle_name": "view.php",
                        "controlled_dom_signature": "sig-forum-88",
                    },
                    "updated_at": "2026-04-06T10:05:00Z",
                },
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == run_id
    assert body["crawl_snapshot"]["entry_locator"] == "https://courses.example.com/course/view.php?id=42"
    assert body["crawl_snapshot"]["visited_locators"] == [
        "https://courses.example.com/course/view.php?id=42",
        "https://courses.example.com/mod/page/view.php?id=10",
    ]
    assert body["crawl_snapshot"]["excluded_locators"] == [
        {
            "locator": "https://courses.example.com/mod/forum/view.php?id=88",
            "reason": "unsupported_module_path",
        },
    ]
    assert len(body["assets"]) == 2
    assert {asset["asset_id"] for asset in body["assets"]} == {"asset-page-10", "asset-forum-88"}
    forum_asset = next(asset for asset in body["assets"] if asset["asset_id"] == "asset-forum-88")
    assert forum_asset["scope_status"] == "out_of_scope"
    assert forum_asset["scope_reason"] == "unsupported_module_path"
    assert forum_asset["crawl_snapshot_id"] == body["crawl_snapshot"]["crawl_snapshot_id"]


def test_post_assets_upsert_updates_existing_assets_for_run(client: TestClient) -> None:
    run_id = build_run(client)
    first_payload = {
        "run_id": run_id,
        "crawl_snapshot": {
            "entry_locator": "https://courses.example.com/course/view.php?id=42",
            "started_at": "2026-04-06T10:00:00Z",
            "completed_at": "2026-04-06T10:03:00Z",
            "visited_locators": ["https://courses.example.com/mod/page/view.php?id=10"],
            "excluded_locators": [],
            "snapshot_metadata": {"asset_count": 1},
        },
        "assets": [
            {
                "asset_id": "asset-page-10",
                "asset_type": "course_module_page",
                "source_system": "moodle",
                "locator": "https://courses.example.com/mod/page/view.php?id=10",
                "scope_status": "in_scope",
                "layer": "course_module",
                "shared_key": "shared-page-10",
                "owner_team": "initial-team",
                "auth_context": {"role": "learner"},
                "handling_path": "mod/page",
                "component_fingerprint": {"controlled_dom_signature": "sig-page-10"},
                "updated_at": "2026-04-06T10:03:00Z",
            },
        ],
    }
    client.post("/assets/upsert", json=first_payload)

    second_response = client.post(
        "/assets/upsert",
        json={
            "run_id": run_id,
            "crawl_snapshot": {
                "entry_locator": "https://courses.example.com/course/view.php?id=42",
                "started_at": "2026-04-06T10:00:00Z",
                "completed_at": "2026-04-06T10:08:00Z",
                "visited_locators": [
                    "https://courses.example.com/mod/page/view.php?id=10",
                    "https://courses.example.com/mod/url/view.php?id=15",
                ],
                "excluded_locators": [],
                "snapshot_metadata": {"asset_count": 1, "pass": 2},
            },
            "assets": [
                {
                    "asset_id": "asset-page-10",
                    "asset_type": "course_module_page",
                    "source_system": "moodle",
                    "locator": "https://courses.example.com/mod/page/view.php?id=10",
                    "scope_status": "in_scope",
                    "layer": "course_module",
                    "shared_key": "shared-page-10",
                    "owner_team": "updated-team",
                    "auth_context": {"role": "instructor"},
                    "handling_path": "mod/page",
                    "component_fingerprint": {"controlled_dom_signature": "sig-page-10-v2"},
                    "updated_at": "2026-04-06T10:08:00Z",
                },
            ],
        },
    )

    assert second_response.status_code == 201
    body = second_response.json()
    assert len(body["assets"]) == 1
    assert body["assets"][0]["owner_team"] == "updated-team"
    assert body["assets"][0]["auth_context"] == {"role": "instructor"}
    assert body["assets"][0]["component_fingerprint"] == {"controlled_dom_signature": "sig-page-10-v2"}
    assert body["crawl_snapshot"]["completed_at"] == "2026-04-06T10:08:00Z"
    assert body["crawl_snapshot"]["snapshot_metadata"] == {"asset_count": 1, "pass": 2}


def test_post_assets_upsert_rejects_out_of_scope_without_reason(client: TestClient) -> None:
    run_id = build_run(client)

    response = client.post(
        "/assets/upsert",
        json={
            "run_id": run_id,
            "crawl_snapshot": {
                "entry_locator": "https://courses.example.com/course/view.php?id=42",
                "started_at": "2026-04-06T10:00:00Z",
                "completed_at": "2026-04-06T10:05:00Z",
                "visited_locators": [],
                "excluded_locators": [],
                "snapshot_metadata": {},
            },
            "assets": [
                {
                    "asset_id": "asset-forum-88",
                    "asset_type": "unsupported_module",
                    "source_system": "moodle",
                    "locator": "https://courses.example.com/mod/forum/view.php?id=88",
                    "scope_status": "out_of_scope",
                    "layer": "course_module",
                    "shared_key": "shared-forum-88",
                    "owner_team": None,
                    "auth_context": {"role": "learner"},
                    "handling_path": "mod/forum",
                    "component_fingerprint": {},
                    "updated_at": "2026-04-06T10:05:00Z",
                },
            ],
        },
    )

    assert response.status_code == 422
    assert "scope_reason is required" in response.text
