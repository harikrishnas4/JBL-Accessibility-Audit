from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import uuid

from jbl_audit_api.core.exceptions import NotFoundError
from jbl_audit_api.db.models import EvidenceArtifact, RawFinding, RawFindingResultType
from jbl_audit_api.repositories.findings import FindingRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.schemas.findings import RawFindingCreateRequest
from jbl_audit_api.services.normalization import NormalizationService


class FindingService:
    def __init__(
        self,
        repository: FindingRepository,
        run_repository: RunRepository,
        normalization_service: NormalizationService,
    ) -> None:
        self.repository = repository
        self.run_repository = run_repository
        self.normalization_service = normalization_service

    def persist_scan_results(
        self,
        run_id: str,
        asset_id: str,
        findings: list[RawFindingCreateRequest],
    ) -> list[RawFinding]:
        if self.run_repository.get(run_id) is None:
            raise NotFoundError(f"run '{run_id}' does not exist")
        if self.repository.get_asset(run_id, asset_id) is None:
            raise NotFoundError(f"asset '{asset_id}' does not exist for run '{run_id}'")

        now = datetime.now(UTC)
        finding_models: list[RawFinding] = []
        for item in findings:
            finding = RawFinding(
                finding_id=str(uuid.uuid4()),
                run_id=run_id,
                asset_id=asset_id,
                result_type=item.result_type,
                rule_id=item.rule_id,
                wcag_sc=item.wcag_sc,
                resolution_state=item.resolution_state,
                severity=item.severity,
                message=item.message,
                target_fingerprint=item.target_fingerprint,
                raw_payload=item.raw_payload,
                observed_at=item.observed_at,
                created_at=now,
                updated_at=now,
            )
            finding.evidence_artifacts = [
                EvidenceArtifact(
                    evidence_artifact_id=str(uuid.uuid4()),
                    run_id=run_id,
                    asset_id=asset_id,
                    artifact_type=artifact.artifact_type,
                    storage_path=artifact.storage_path,
                    artifact_metadata=artifact.artifact_metadata,
                    captured_at=artifact.captured_at,
                )
                for artifact in item.evidence_artifacts
            ]
            finding_models.append(finding)

        persisted = self.repository.save_findings(finding_models)
        self.normalization_service.sync_run(run_id)
        return persisted

    def get_run_findings(self, run_id: str) -> dict:
        if self.run_repository.get(run_id) is None:
            raise NotFoundError(f"run '{run_id}' does not exist")

        findings = self.repository.list_findings_for_run(run_id)
        result_counts = Counter({result.value: 0 for result in RawFindingResultType})
        result_counts.update(finding.result_type.value for finding in findings)
        return {
            "run_id": run_id,
            "finding_count": len(findings),
            "result_counts": dict(result_counts),
            "findings": findings,
        }
