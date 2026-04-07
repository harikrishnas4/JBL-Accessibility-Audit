from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from jbl_audit_api.db import models
from jbl_audit_api.repositories.defects import DefectRepository
from jbl_audit_api.repositories.findings import FindingRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.schemas.findings import RawFindingCreateRequest
from jbl_audit_api.services.findings import FindingService
from jbl_audit_api.services.normalization import NormalizationService


def _create_run(client: TestClient) -> str:
    response = client.post(
        "/runs",
        json={
            "course_url_or_name": "JBL Dedup Validation Course",
            "auth_metadata": {"method": "placeholder"},
        },
    )
    return response.json()["run_id"]


def _seed_classified_asset(
    client: TestClient,
    *,
    run_id: str,
    asset_id: str,
    locator: str,
    layer: models.AssetLayer,
    handling_path: models.AssetHandlingPath,
    shared_key: str | None,
    owner_team: str = "content",
) -> None:
    now = datetime.now(UTC)
    with client.app.state.session_factory() as session:
        asset = models.Asset(
            run_id=run_id,
            asset_id=asset_id,
            crawl_snapshot_id=None,
            asset_type="web_page",
            source_system="moodle",
            locator=locator,
            scope_status=models.AssetScopeStatus.in_scope,
            scope_reason=None,
            layer=layer.value,
            shared_key=shared_key,
            owner_team=owner_team,
            auth_context={"role": "learner"},
            handling_path=handling_path.value,
            component_fingerprint={"stable_css_selector": f"main#{asset_id}"},
            created_at=now,
            updated_at=now,
        )
        classification = models.AssetClassification(
            classification_id=str(uuid.uuid4()),
            run_id=run_id,
            asset_id=asset_id,
            layer=layer,
            handling_path=handling_path,
            shared_key=shared_key,
            owner_team=owner_team,
            third_party=False,
            third_party_evidence=None,
            auth_context={"role": "learner"},
            exclusion_reason=None,
            created_at=now,
            updated_at=now,
        )
        asset.classification_record = classification
        session.add(asset)
        session.commit()


def _persist_finding(
    client: TestClient,
    *,
    run_id: str,
    asset_id: str,
    result_type: models.RawFindingResultType,
    rule_id: str,
    wcag_sc: str,
    severity: str | None,
    message: str,
    target_fingerprint: str,
    resolution_state: str = "new",
    raw_payload: dict | None = None,
) -> None:
    observed_at = datetime.now(UTC)
    with client.app.state.session_factory() as session:
        service = FindingService(
            FindingRepository(session),
            RunRepository(session),
            NormalizationService(DefectRepository(session), RunRepository(session)),
        )
        service.persist_scan_results(
            run_id,
            asset_id,
            [
                RawFindingCreateRequest(
                    result_type=result_type,
                    rule_id=rule_id,
                    wcag_sc=wcag_sc,
                    resolution_state=resolution_state,
                    severity=severity,
                    message=message,
                    target_fingerprint=target_fingerprint,
                    raw_payload=raw_payload or {"origin": "automated"},
                    observed_at=observed_at,
                ),
            ],
        )
        session.commit()


def test_signature_merge_behavior_deduplicates_shared_component_failures(client: TestClient) -> None:
    run_id = _create_run(client)
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-page-1",
        locator="https://example.com/mod/page/view.php?id=11",
        layer=models.AssetLayer.content,
        handling_path=models.AssetHandlingPath.automated,
        shared_key="shared:lesson-header",
    )
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-page-2",
        locator="https://example.com/mod/page/view.php?id=12",
        layer=models.AssetLayer.content,
        handling_path=models.AssetHandlingPath.automated,
        shared_key="shared:lesson-header",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-page-1",
        result_type=models.RawFindingResultType.violation,
        rule_id="image-alt",
        wcag_sc="1.1.1",
        severity="serious",
        message="Images must have alternate text.",
        target_fingerprint="img.hero",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-page-2",
        result_type=models.RawFindingResultType.violation,
        rule_id="image-alt",
        wcag_sc="1.1.1",
        severity="serious",
        message="Images must have alternate text.",
        target_fingerprint="img.hero",
    )

    response = client.get("/defects", params={"run_id": run_id})

    assert response.status_code == 200
    body = response.json()
    assert body["defect_count"] == 1
    defect = body["defects"][0]
    assert defect["issue_id"].startswith("CS-")
    assert defect["impacted_asset_count"] == 2
    assert defect["shared_key"] == "shared:lesson-header"
    assert {item["asset_id"] for item in defect["components"]} == {"asset-page-1", "asset-page-2"}


def test_defects_output_includes_linked_third_party_evidence(client: TestClient) -> None:
    run_id = _create_run(client)
    observed_at = datetime(2026, 4, 7, 13, 0, tzinfo=UTC)

    upsert_response = client.post(
        "/assets/upsert",
        json={
            "run_id": run_id,
            "crawl_snapshot": {
                "entry_locator": "https://courses.example.com/course/view.php?id=777",
                "started_at": observed_at.isoformat(),
                "completed_at": observed_at.isoformat(),
                "visited_locators": ["https://courses.example.com/course/view.php?id=777"],
                "excluded_locators": [],
                "snapshot_metadata": {"visited_page_count": 1},
            },
            "assets": [
                {
                    "asset_id": "asset-third-party-defect-1",
                    "asset_type": "third_party_embed",
                    "source_system": "human.biodigital.com",
                    "locator": "https://human.biodigital.com/widget?be=777",
                    "scope_status": "in_scope",
                    "layer": "embedded_content",
                    "shared_key": "third_party:biodigital-widget",
                    "owner_team": None,
                    "auth_context": {"role": "learner"},
                    "handling_path": "iframe:biodigital",
                    "component_fingerprint": {
                        "stable_css_selector": "iframe#biodigital-defect",
                        "template_id": "biodigital-embed",
                        "bundle_name": "widget",
                        "controlled_dom_signature": "sig-biodigital-defect",
                    },
                    "updated_at": observed_at.isoformat(),
                },
            ],
        },
    )

    assert upsert_response.status_code == 201

    response = client.post(
        f"/runs/{run_id}/assets/asset-third-party-defect-1/findings",
        json={
            "findings": [
                {
                    "result_type": "violation",
                    "rule_id": "frame-title",
                    "wcag_sc": "2.4.1",
                    "resolution_state": "new",
                    "severity": "serious",
                    "message": "Embedded frame needs an accessible title.",
                    "target_fingerprint": "iframe.biodigital-launch",
                    "raw_payload": {"origin": "automated"},
                    "observed_at": observed_at.isoformat(),
                    "evidence_artifacts": [],
                },
            ],
        },
    )

    assert response.status_code == 201

    defects_response = client.get("/defects", params={"run_id": run_id})

    assert defects_response.status_code == 200
    body = defects_response.json()
    assert body["defect_count"] == 1
    defect = body["defects"][0]
    assert defect["third_party_evidence"]["provider_name"] == "human.biodigital.com"
    assert defect["third_party_evidence"]["domain"] == "human.biodigital.com"
    assert defect["third_party_evidence"]["status"] == "cross_origin_blocked"
    assert defect["third_party_evidence"]["evidence_type"] == "VPAT_requested"


def test_prefix_assignment_covers_gp_cp_cs_and_mr(client: TestClient) -> None:
    run_id = _create_run(client)
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-platform",
        locator="https://example.com/theme/styles.css",
        layer=models.AssetLayer.platform,
        handling_path=models.AssetHandlingPath.automated,
        shared_key="platform:theme",
        owner_team="platform",
    )
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-component",
        locator="https://example.com/mod/page/view.php?id=21",
        layer=models.AssetLayer.component,
        handling_path=models.AssetHandlingPath.automated_plus_manual,
        shared_key="component:quiz-widget",
    )
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-content",
        locator="https://example.com/mod/page/view.php?id=22",
        layer=models.AssetLayer.content,
        handling_path=models.AssetHandlingPath.automated,
        shared_key="content:lesson-page",
    )
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-manual-origin",
        locator="https://example.com/mod/page/view.php?id=23",
        layer=models.AssetLayer.content,
        handling_path=models.AssetHandlingPath.automated,
        shared_key="content:manual-origin",
    )

    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-platform",
        result_type=models.RawFindingResultType.violation,
        rule_id="landmark-one-main",
        wcag_sc="1.3.1",
        severity="moderate",
        message="Document should have one main landmark.",
        target_fingerprint="body",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-component",
        result_type=models.RawFindingResultType.violation,
        rule_id="aria-required-parent",
        wcag_sc="1.3.1",
        severity="serious",
        message="Required ARIA parent role missing.",
        target_fingerprint="[role='option']",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-content",
        result_type=models.RawFindingResultType.violation,
        rule_id="button-name",
        wcag_sc="4.1.2",
        severity="critical",
        message="Buttons must have discernible text.",
        target_fingerprint="button.next",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-manual-origin",
        result_type=models.RawFindingResultType.violation,
        rule_id="focus-order-semantics",
        wcag_sc="2.4.3",
        severity="moderate",
        message="Manual review found incorrect focus order.",
        target_fingerprint=".drag-drop-widget",
        raw_payload={"origin": "manual_review"},
    )

    response = client.get("/defects", params={"run_id": run_id})

    assert response.status_code == 200
    defects_by_rule = {item["rule_id"]: item for item in response.json()["defects"]}
    assert defects_by_rule["landmark-one-main"]["issue_id"].startswith("GP-")
    assert defects_by_rule["aria-required-parent"]["issue_id"].startswith("CP-")
    assert defects_by_rule["button-name"]["issue_id"].startswith("CS-")
    assert defects_by_rule["focus-order-semantics"]["issue_id"].startswith("MR-")


def test_task_creation_covers_manual_review_blocked_manual_only_and_p1_at_validation(client: TestClient) -> None:
    run_id = _create_run(client)
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-manual-only",
        locator="https://cdn-media.jblearning.com/course/media/lecture-1.mp4",
        layer=models.AssetLayer.media,
        handling_path=models.AssetHandlingPath.manual_only,
        shared_key="media:lecture-1",
    )
    _seed_classified_asset(
        client,
        run_id=run_id,
        asset_id="asset-automated",
        locator="https://example.com/mod/quiz/view.php?id=42",
        layer=models.AssetLayer.content,
        handling_path=models.AssetHandlingPath.automated,
        shared_key="content:quiz-42",
    )

    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-automated",
        result_type=models.RawFindingResultType.incomplete,
        rule_id="color-contrast",
        wcag_sc="1.4.3",
        severity="moderate",
        message="Contrast could not be verified automatically.",
        target_fingerprint=".question-text",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-automated",
        result_type=models.RawFindingResultType.violation,
        rule_id="frame-title",
        wcag_sc="2.4.1",
        severity="serious",
        message="Embedded frame access was blocked.",
        target_fingerprint="iframe.lti-launch",
        resolution_state="blocked",
    )
    _persist_finding(
        client,
        run_id=run_id,
        asset_id="asset-automated",
        result_type=models.RawFindingResultType.violation,
        rule_id="button-name",
        wcag_sc="4.1.2",
        severity="critical",
        message="Buttons must have discernible text.",
        target_fingerprint="button.submit",
    )

    with client.app.state.session_factory() as session:
        tasks = session.scalars(
            select(models.ManualReviewTask)
            .where(models.ManualReviewTask.run_id == run_id)
            .order_by(models.ManualReviewTask.reason),
        ).all()
        defects = session.scalars(select(models.Defect).where(models.Defect.run_id == run_id)).all()

    assert len(defects) == 1
    assert defects[0].priority == models.DefectPriority.P1
    reasons = {task.reason for task in tasks}
    assert reasons == {
        "blocked",
        "manual_only_asset",
        "needs_manual_review",
        "p1_at_validation",
    }
    task_types_by_reason = {task.reason: task.task_type.value for task in tasks}
    assert task_types_by_reason["manual_only_asset"] == "asset_review"
    assert task_types_by_reason["needs_manual_review"] == "finding_review"
    assert task_types_by_reason["blocked"] == "finding_review"
    assert task_types_by_reason["p1_at_validation"] == "at_validation"
