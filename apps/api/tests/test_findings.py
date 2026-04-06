from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from jbl_audit_api.db import models
from jbl_audit_api.repositories.defects import DefectRepository
from jbl_audit_api.repositories.findings import FindingRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.schemas.findings import EvidenceArtifactCreateRequest, RawFindingCreateRequest
from jbl_audit_api.services.findings import FindingService
from jbl_audit_api.services.normalization import NormalizationService


def _seed_asset(client: TestClient, run_id: str, asset_id: str) -> None:
    now = datetime.now(UTC)
    with client.app.state.session_factory() as session:
        session.add(
            models.Asset(
                run_id=run_id,
                asset_id=asset_id,
                crawl_snapshot_id=None,
                asset_type="web_page",
                source_system="moodle",
                locator="https://example.com/course/page-1",
                scope_status=models.AssetScopeStatus.in_scope,
                scope_reason=None,
                layer="content",
                shared_key="shared:page-1",
                owner_team="content",
                auth_context={"role": "learner"},
                handling_path="automated",
                component_fingerprint={"stable_css_selector": "main"},
                created_at=now,
                updated_at=now,
            ),
        )
        session.commit()


def _persist_findings(client: TestClient, run_id: str, asset_id: str) -> None:
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
                    result_type=models.RawFindingResultType.violation,
                    rule_id="image-alt",
                    wcag_sc="1.1.1",
                    resolution_state="new",
                    severity="critical",
                    message="Images must have alternate text.",
                    target_fingerprint="img.hero",
                    raw_payload={"source": "axe"},
                    observed_at=observed_at,
                    evidence_artifacts=[
                        EvidenceArtifactCreateRequest(
                            artifact_type=models.EvidenceArtifactType.screenshot,
                            storage_path="var/evidence/run-1/asset-1/failure.png",
                            artifact_metadata={"viewport": "desktop"},
                            captured_at=observed_at,
                        ),
                        EvidenceArtifactCreateRequest(
                            artifact_type=models.EvidenceArtifactType.trace,
                            storage_path="var/evidence/run-1/asset-1/failure.zip",
                            artifact_metadata={"viewport": "desktop"},
                            captured_at=observed_at,
                        ),
                    ],
                ),
                RawFindingCreateRequest(
                    result_type=models.RawFindingResultType.pass_,
                    rule_id="page-has-heading-one",
                    wcag_sc="1.3.1",
                    resolution_state="new",
                    severity=None,
                    message="Page has a heading level one.",
                    target_fingerprint="h1",
                    raw_payload={"source": "axe"},
                    observed_at=observed_at,
                    evidence_artifacts=[
                        EvidenceArtifactCreateRequest(
                            artifact_type=models.EvidenceArtifactType.dom_snapshot_reference,
                            storage_path="var/evidence/run-1/asset-1/dom.html",
                            artifact_metadata={"content_type": "text/html"},
                            captured_at=observed_at,
                        ),
                    ],
                ),
            ],
        )
        session.commit()


def test_get_run_findings_returns_persisted_findings_and_evidence(client: TestClient) -> None:
    create_response = client.post(
        "/runs",
        json={
            "course_url_or_name": "Accessibility Sample Course",
            "auth_metadata": {"method": "placeholder"},
        },
    )
    run_id = create_response.json()["run_id"]
    _seed_asset(client, run_id, "asset-1")
    _persist_findings(client, run_id, "asset-1")

    response = client.get(f"/runs/{run_id}/findings")

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == run_id
    assert body["finding_count"] == 2
    assert body["result_counts"] == {
        "violation": 1,
        "pass": 1,
        "incomplete": 0,
        "inapplicable": 0,
    }
    violation = next(item for item in body["findings"] if item["result_type"] == "violation")
    assert violation["asset_id"] == "asset-1"
    assert violation["rule_id"] == "image-alt"
    assert violation["wcag_sc"] == "1.1.1"
    assert [item["artifact_type"] for item in violation["evidence_artifacts"]] == [
        "screenshot",
        "trace",
    ]


def test_get_run_findings_returns_404_for_unknown_run(client: TestClient) -> None:
    response = client.get("/runs/does-not-exist/findings")

    assert response.status_code == 404
    assert response.json() == {"detail": "run 'does-not-exist' does not exist"}
