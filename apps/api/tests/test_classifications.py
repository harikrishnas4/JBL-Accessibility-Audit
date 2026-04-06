from __future__ import annotations

from sqlalchemy import select
from fastapi.testclient import TestClient

from jbl_audit_api.db.models import AssetClassification


def build_run(client: TestClient) -> str:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "https://courses.example.com/course/view.php?id=7",
            "auth_metadata": {"method": "session-state", "auth_context": "learner"},
        },
    )
    return response.json()["run_id"]


def build_asset(
    *,
    asset_id: str,
    asset_type: str,
    locator: str,
    source_system: str = "moodle",
    scope_status: str = "in_scope",
    scope_reason: str | None = None,
    layer: str = "course_module",
    shared_key: str | None = None,
    owner_team: str | None = None,
    auth_context: dict | None = None,
    handling_path: str = "mod/page",
    component_fingerprint: dict | None = None,
) -> dict:
    payload = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "source_system": source_system,
        "locator": locator,
        "scope_status": scope_status,
        "layer": layer,
        "shared_key": shared_key,
        "owner_team": owner_team,
        "auth_context": auth_context or {"role": "learner"},
        "handling_path": handling_path,
        "component_fingerprint": component_fingerprint
        or {
            "stable_css_selector": f"a#{asset_id}",
            "template_id": "course-module-link",
            "bundle_name": "view.php",
            "controlled_dom_signature": f"sig-{asset_id}",
        },
        "updated_at": "2026-04-07T00:10:00Z",
    }
    if scope_reason is not None:
        payload["scope_reason"] = scope_reason
    return payload


def build_upsert_payload(run_id: str, assets: list[dict], manifest_context: dict | None = None) -> dict:
    payload = {
        "run_id": run_id,
        "crawl_snapshot": {
            "entry_locator": "https://courses.example.com/course/view.php?id=7",
            "started_at": "2026-04-07T00:00:00Z",
            "completed_at": "2026-04-07T00:05:00Z",
            "visited_locators": ["https://courses.example.com/course/view.php?id=7"],
            "excluded_locators": [],
            "snapshot_metadata": {"asset_count": len(assets)},
        },
        "assets": assets,
    }
    if manifest_context is not None:
        payload["manifest_context"] = manifest_context
    return payload


def test_manifest_driven_classification_overrides_heuristics(client: TestClient) -> None:
    run_id = build_run(client)
    response = client.post(
        "/assets/upsert",
        json=build_upsert_payload(
            run_id,
            assets=[
                build_asset(
                    asset_id="asset-widget-1",
                    asset_type="course_page",
                    locator="https://courses.example.com/mod/page/view.php?id=91",
                    shared_key="inventory-placeholder",
                    owner_team="instructional-design",
                    component_fingerprint={
                        "stable_css_selector": "div[data-template-id='drag-drop-widget']",
                        "template_id": "drag-drop-widget",
                        "bundle_name": "lesson-widget.js",
                        "controlled_dom_signature": "sig-widget-1",
                    },
                ),
            ],
            manifest_context={
                "datasets": [
                    {
                        "schema_type": "asset_type_layout",
                        "records": [
                            {
                                "asset_type": "interactive",
                                "layout": "carousel",
                                "template": "drag-drop-widget",
                            },
                        ],
                    },
                ],
            },
        ),
    )

    assert response.status_code == 201
    classification = response.json()["classifications"][0]
    assert classification["asset_id"] == "asset-widget-1"
    assert classification["layer"] == "component"
    assert classification["handling_path"] == "manual_only"
    assert classification["shared_key"] == "component:drag drop widget"
    assert classification["owner_team"] == "instructional-design"
    assert classification["third_party"] is False


def test_crawler_only_degraded_classification_uses_heuristics(client: TestClient) -> None:
    run_id = build_run(client)
    response = client.post(
        "/assets/upsert",
        json=build_upsert_payload(
            run_id,
            assets=[
                build_asset(
                    asset_id="asset-page-1",
                    asset_type="course_page",
                    locator="https://courses.example.com/mod/page/view.php?id=10",
                    shared_key="inventory-page-key",
                    owner_team=None,
                ),
            ],
        ),
    )

    assert response.status_code == 201
    classification = response.json()["classifications"][0]
    assert classification["layer"] == "content"
    assert classification["handling_path"] == "automated"
    assert classification["shared_key"] == "inventory-page-key"
    assert classification["owner_team"] == "content"


def test_third_party_routing_marks_layer_and_evidence_placeholder(client: TestClient) -> None:
    run_id = build_run(client)
    response = client.post(
        "/assets/upsert",
        json=build_upsert_payload(
            run_id,
            assets=[
                build_asset(
                    asset_id="asset-lti-1",
                    asset_type="course_lti",
                    locator="https://vendor.example.com/lti/launch?id=44",
                    source_system="vendor.example.com",
                    layer="course_module",
                    handling_path="mod/lti",
                ),
            ],
        ),
    )

    assert response.status_code == 201
    classification = response.json()["classifications"][0]
    assert classification["layer"] == "third_party"
    assert classification["handling_path"] == "evidence_only"
    assert classification["third_party"] is True
    assert classification["third_party_evidence"] == f"evidence://third-party/{run_id}/asset-lti-1"
    assert classification["shared_key"] == "third_party:vendor.example.com"


def test_manual_only_assignment_and_reason_persistence(client: TestClient) -> None:
    run_id = build_run(client)
    response = client.post(
        "/assets/upsert",
        json=build_upsert_payload(
            run_id,
            assets=[
                build_asset(
                    asset_id="asset-video-1",
                    asset_type="cdn_media_asset",
                    locator="https://cdn-media.jblearning.com/assets/lecture-1.mp4",
                    source_system="cdn-media.jblearning.com",
                    layer="embedded_media",
                    handling_path="video-player",
                ),
                build_asset(
                    asset_id="asset-cross-origin-1",
                    asset_type="unsupported_embed",
                    locator="https://cross-origin.example.com/embed/blocked",
                    source_system="cross-origin.example.com",
                    scope_status="out_of_scope",
                    scope_reason="cross_origin_blocked",
                    layer="embedded_content",
                    handling_path="iframe:unsupported",
                ),
            ],
        ),
    )

    assert response.status_code == 201
    classifications = {item["asset_id"]: item for item in response.json()["classifications"]}
    assert classifications["asset-video-1"]["layer"] == "media"
    assert classifications["asset-video-1"]["handling_path"] == "manual_only"
    assert classifications["asset-cross-origin-1"]["layer"] == "third_party"
    assert classifications["asset-cross-origin-1"]["handling_path"] == "excluded"
    assert classifications["asset-cross-origin-1"]["exclusion_reason"] == "cross_origin_blocked"

    with client.app.state.session_factory() as session:
        persisted = session.scalars(
            select(AssetClassification).where(AssetClassification.run_id == run_id).order_by(AssetClassification.asset_id),
        ).all()

    assert len(persisted) == 2
    persisted_by_asset = {record.asset_id: record for record in persisted}
    assert persisted_by_asset["asset-video-1"].handling_path.value == "manual_only"
    assert persisted_by_asset["asset-cross-origin-1"].exclusion_reason == "cross_origin_blocked"
