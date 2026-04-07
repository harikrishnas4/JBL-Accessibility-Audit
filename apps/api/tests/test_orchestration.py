from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jbl_audit_api.core.dependencies import get_tier1_batch_executor
from jbl_audit_api.schemas.findings import EvidenceArtifactCreateRequest, RawFindingCreateRequest
from jbl_audit_api.services.orchestration_execution import (
    Tier1AssetExecutionFailure,
    Tier1AssetExecutionSuccess,
    Tier1BatchExecutionResult,
)


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


class ConfigurableBatchExecutor:
    def __init__(
        self,
        *,
        fail_asset_ids: set[str] | None = None,
        include_findings: bool = False,
    ) -> None:
        self.fail_asset_ids = fail_asset_ids or set()
        self.include_findings = include_findings

    def execute_batch(self, run_id: str, batch, *, session_state_path: str | None = None) -> Tier1BatchExecutionResult:
        asset_results: list[Tier1AssetExecutionSuccess] = []
        failures: list[Tier1AssetExecutionFailure] = []
        observed_at = datetime(2026, 4, 7, 12, 0, tzinfo=UTC)

        for asset in batch.task_contract["assets"]:
            asset_id = asset["asset_id"]
            if asset_id in self.fail_asset_ids:
                failures.append(
                    Tier1AssetExecutionFailure(
                        asset_id=asset_id,
                        asset_type=asset["asset_type"],
                        error="simulated scan failure",
                        viewport="desktop",
                    ),
                )
                continue

            findings = ()
            if self.include_findings:
                findings = (
                    RawFindingCreateRequest(
                        result_type="violation",
                        rule_id="image-alt",
                        wcag_sc="1.1.1",
                        resolution_state="new",
                        severity="critical",
                        message="Images must have alternate text.",
                        target_fingerprint=f"img.{asset_id}",
                        raw_payload={"source": "fake-tier1"},
                        observed_at=observed_at,
                        evidence_artifacts=[
                            EvidenceArtifactCreateRequest(
                                artifact_type="screenshot",
                                storage_path=f"var/evidence/{run_id}/{asset_id}/failure.png",
                                artifact_metadata={"viewport": "desktop"},
                                captured_at=observed_at,
                            ),
                        ],
                    ),
                )

            asset_results.append(
                Tier1AssetExecutionSuccess(
                    asset_id=asset_id,
                    findings=findings,
                    scan_metadata={
                        "executor": "configurable_test_executor",
                        "viewports": [viewport["name"] for viewport in batch.viewport_matrix],
                        "session_state_path": session_state_path,
                    },
                ),
            )

        return Tier1BatchExecutionResult(
            asset_results=tuple(asset_results),
            failures=tuple(failures),
            summary={
                "attempted_asset_count": len(batch.task_contract["assets"]),
                "successful_asset_count": len(asset_results),
                "failed_asset_count": len(failures),
                "finding_count": sum(len(item.findings) for item in asset_results),
            },
        )


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
                asset_type="web_page",
                locator="https://courses.example.com/mod/page/view.php?id=10",
                shared_key="component:lesson-card",
            ),
            build_asset(
                asset_id="asset-page-11",
                asset_type="web_page",
                locator="https://courses.example.com/mod/page/view.php?id=11",
                shared_key="component:lesson-card",
            ),
        ],
    )

    response = client.get(f"/runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["current_stage"] == "completed"
    assert body["run_plan"]["status"] == "completed"
    assert body["run_plan"]["scan_batch_count"] == 1
    assert body["run_plan"]["manual_task_count"] == 0
    assert body["run_plan"]["orchestration_metadata"]["batch_count"] == 1
    batch = body["run_plan"]["scan_batches"][0]
    assert batch["batch_type"] == "scan_worker"
    assert batch["status"] == "completed"
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
    assert batch["dispatcher_metadata"]["dispatch_mode"] == "in_process_scan_execution"
    assert batch["dispatcher_metadata"]["execution_summary"]["successful_asset_count"] == 2


def test_orchestrator_routes_manual_only_assets_to_manual_stub_and_updates_status(client: TestClient) -> None:
    run_id = build_run(client)
    upsert_assets(
        client,
        run_id,
        assets=[
            build_asset(
                asset_id="asset-video-1",
                asset_type="media_video",
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


def test_orchestrator_creates_findings_after_successful_dispatch(client: TestClient) -> None:
    client.app.dependency_overrides[get_tier1_batch_executor] = lambda: ConfigurableBatchExecutor(include_findings=True)
    try:
        run_id = build_run(client)
        upsert_assets(
            client,
            run_id,
            assets=[
                build_asset(
                    asset_id="asset-page-21",
                    asset_type="web_page",
                    locator="https://courses.example.com/mod/page/view.php?id=21",
                    shared_key="page-21",
                ),
            ],
        )

        run_response = client.get(f"/runs/{run_id}")
        assert run_response.status_code == 200
        run_body = run_response.json()
        assert run_body["status"] == "completed"
        assert run_body["current_stage"] == "completed"
        assert run_body["run_plan"]["status"] == "completed"
        assert run_body["run_plan"]["scan_batches"][0]["status"] == "completed"

        findings_response = client.get(f"/runs/{run_id}/findings")
        assert findings_response.status_code == 200
        findings_body = findings_response.json()
        assert findings_body["finding_count"] == 1
        assert findings_body["result_counts"] == {
            "violation": 1,
            "pass": 0,
            "incomplete": 0,
            "inapplicable": 0,
        }
        assert findings_body["findings"][0]["asset_id"] == "asset-page-21"
    finally:
        client.app.dependency_overrides.pop(get_tier1_batch_executor, None)


def test_orchestrator_marks_batch_failed_on_partial_asset_failure(client: TestClient) -> None:
    client.app.dependency_overrides[get_tier1_batch_executor] = lambda: ConfigurableBatchExecutor(
        include_findings=True,
        fail_asset_ids={"asset-page-31"},
    )
    try:
        run_id = build_run(
            client,
            manifest_metadata={
                "chapter_by_locator": {
                    "https://courses.example.com/mod/page/view.php?id=30": "ch-3",
                    "https://courses.example.com/mod/page/view.php?id=31": "ch-3",
                },
            },
        )
        upsert_assets(
            client,
            run_id,
            assets=[
                build_asset(
                    asset_id="asset-page-30",
                    asset_type="web_page",
                    locator="https://courses.example.com/mod/page/view.php?id=30",
                    shared_key="component:lesson-card",
                ),
                build_asset(
                    asset_id="asset-page-31",
                    asset_type="web_page",
                    locator="https://courses.example.com/mod/page/view.php?id=31",
                    shared_key="component:lesson-card",
                ),
            ],
        )

        run_response = client.get(f"/runs/{run_id}")
        assert run_response.status_code == 200
        run_body = run_response.json()
        assert run_body["status"] == "failed"
        assert run_body["current_stage"] == "failed"
        assert run_body["run_plan"]["status"] == "failed"
        batch = run_body["run_plan"]["scan_batches"][0]
        assert batch["status"] == "failed"
        assert batch["dispatcher_metadata"]["execution_summary"]["successful_asset_count"] == 1
        assert batch["dispatcher_metadata"]["execution_summary"]["failed_asset_count"] == 1
        assert batch["dispatcher_metadata"]["failures"] == [
            {
                "asset_id": "asset-page-31",
                "asset_type": "web_page",
                "error": "simulated scan failure",
                "viewport": "desktop",
            },
        ]

        findings_response = client.get(f"/runs/{run_id}/findings")
        assert findings_response.status_code == 200
        findings_body = findings_response.json()
        assert findings_body["finding_count"] == 1
        assert findings_body["findings"][0]["asset_id"] == "asset-page-30"
    finally:
        client.app.dependency_overrides.pop(get_tier1_batch_executor, None)
