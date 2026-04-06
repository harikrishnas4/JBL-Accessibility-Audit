from __future__ import annotations

from fastapi.testclient import TestClient


def build_run(client: TestClient, *, manifest_metadata: dict | None = None) -> str:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://courses.example.com/course/view.php?id=55",
            "auth_metadata": {"method": "session-state", "auth_context": "learner"},
            "manifest_metadata": manifest_metadata,
        },
    )
    assert response.status_code == 201
    return response.json()["run_id"]


def build_asset(
    *,
    asset_id: str,
    asset_type: str,
    locator: str,
    source_system: str = "moodle",
    scope_status: str = "in_scope",
    shared_key: str | None = None,
    owner_team: str | None = None,
    component_fingerprint: dict | None = None,
) -> dict:
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "source_system": source_system,
        "locator": locator,
        "scope_status": scope_status,
        "layer": "course_module",
        "shared_key": shared_key,
        "owner_team": owner_team,
        "auth_context": {"role": "learner"},
        "handling_path": "mod/page",
        "component_fingerprint": component_fingerprint
        or {
            "stable_css_selector": f"a#{asset_id}",
            "template_id": "course-module-link",
            "bundle_name": "view.php",
            "controlled_dom_signature": f"sig-{asset_id}",
        },
        "updated_at": "2026-04-07T03:00:00Z",
    }


def upsert_assets(
    client: TestClient,
    run_id: str,
    *,
    assets: list[dict],
    manifest_context: dict | None = None,
    snapshot_metadata: dict | None = None,
) -> None:
    payload = {
        "run_id": run_id,
        "crawl_snapshot": {
            "entry_locator": "https://courses.example.com/course/view.php?id=55",
            "started_at": "2026-04-07T03:00:00Z",
            "completed_at": "2026-04-07T03:05:00Z",
            "visited_locators": ["https://courses.example.com/course/view.php?id=55"],
            "excluded_locators": [],
            "snapshot_metadata": snapshot_metadata or {"asset_count": len(assets)},
        },
        "assets": assets,
    }
    if manifest_context is not None:
        payload["manifest_context"] = manifest_context
    response = client.post("/assets/upsert", json=payload)
    assert response.status_code == 201


def test_run_creation_bootstraps_empty_orchestration_plan(client: TestClient) -> None:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://courses.example.com/course/view.php?id=55",
            "auth_metadata": {"method": "session-state"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["current_stage"] == "intake"
    assert body["run_plan"]["status"] == "awaiting_assets"
    assert body["run_plan"]["dispatcher_name"] == "local_in_process"
    assert body["run_plan"]["scan_batches"] == []
    assert body["run_plan"]["viewport_matrix"] == [
        {"name": "desktop", "width": 1280, "height": 800},
        {"name": "tablet", "width": 768, "height": 1024},
        {"name": "mobile", "width": 375, "height": 667},
    ]


def test_orchestrator_groups_scan_batches_by_chapter_and_shared_key(client: TestClient) -> None:
    run_id = build_run(
        client,
        manifest_metadata={
            "chapter_by_locator": {
                "https://courses.example.com/mod/page/view.php?id=10": "ch-1",
                "https://courses.example.com/mod/page/view.php?id=11": "ch-1",
            },
        },
    )
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-page-10",
                asset_type="course_page",
                locator="https://courses.example.com/mod/page/view.php?id=10",
                shared_key="component:lesson-card",
            ),
            build_asset(
                asset_id="asset-page-11",
                asset_type="course_page",
                locator="https://courses.example.com/mod/page/view.php?id=11",
                shared_key="component:lesson-card",
            ),
        ],
    )

    response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["current_stage"] == "orchestration"
    assert body["run_plan"]["status"] == "dispatched"
    assert body["run_plan"]["scan_batch_count"] == 1
    assert body["run_plan"]["manual_task_count"] == 0
    assert body["run_plan"]["orchestration_metadata"]["batch_count"] == 1
    batch = body["run_plan"]["scan_batches"][0]
    assert batch["batch_type"] == "scan_worker"
    assert batch["status"] == "dispatched"
    assert batch["chapter_key"] == "ch-1"
    assert batch["shared_key"] == "component:lesson-card"
    assert batch["asset_ids"] == ["asset-page-10", "asset-page-11"]
    assert batch["viewport_matrix"] == [
        {"name": "desktop", "width": 1280, "height": 800},
        {"name": "tablet", "width": 768, "height": 1024},
        {"name": "mobile", "width": 375, "height": 667},
    ]
    assert batch["retry_policy"] == {"strategy": "fixed", "max_attempts": 2, "backoff_seconds": 30}
    assert batch["task_contract"]["contract_type"] == "scan_worker_contract_v1"
    assert len(batch["task_contract"]["assets"]) == 2


def test_orchestrator_routes_manual_only_assets_to_manual_stub_and_updates_status(client: TestClient) -> None:
    run_id = build_run(client)
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-video-1",
                asset_type="cdn_media_asset",
                locator="https://cdn-media.jblearning.com/assets/lecture-1.mp4",
                source_system="cdn-media.jblearning.com",
            ),
        ],
    )

    response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["current_stage"] == "orchestration"
    assert body["run_plan"]["status"] == "manual_pending"
    assert body["run_plan"]["scan_batch_count"] == 0
    assert body["run_plan"]["manual_task_count"] == 1
    batch = body["run_plan"]["scan_batches"][0]
    assert batch["batch_type"] == "manual_review_stub"
    assert batch["status"] == "manual_pending"
    assert batch["viewport_matrix"] == []
    assert batch["task_contract"]["contract_type"] == "manual_task_stub_v1"
    assert batch["dispatcher_metadata"]["dispatch_mode"] == "manual_task_stub"
