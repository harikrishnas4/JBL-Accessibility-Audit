from __future__ import annotations

from datetime import UTC, datetime
import uuid

from jbl_audit_api.db.models import (
    Asset,
    AssetHandlingPath,
    Defect,
    DefectPriority,
    FindingState,
    ManualReviewTask,
    ManualReviewTaskStatus,
    ManualReviewTaskType,
    RawFinding,
)


class ManualReviewService:
    def build_tasks(
        self,
        run_id: str,
        assets: list[Asset],
        finding_entries: list[tuple[RawFinding, FindingState, DefectPriority | None]],
        defects: list[Defect],
    ) -> list[ManualReviewTask]:
        now = datetime.now(UTC)
        tasks: list[ManualReviewTask] = []

        for asset in assets:
            classification = asset.classification_record
            if classification is None or classification.handling_path != AssetHandlingPath.manual_only:
                continue
            tasks.append(
                ManualReviewTask(
                    manual_review_task_id=str(uuid.uuid4()),
                    run_id=run_id,
                    asset_id=asset.asset_id,
                    finding_id=None,
                    defect_id=None,
                    task_type=ManualReviewTaskType.asset_review,
                    status=ManualReviewTaskStatus.pending,
                    priority=None,
                    source_state=None,
                    reason="manual_only_asset",
                    task_metadata={
                        "locator": asset.locator,
                        "layer": classification.layer.value,
                        "shared_key": classification.shared_key,
                        "owner_team": classification.owner_team,
                    },
                    created_at=now,
                    updated_at=now,
                ),
            )

        for finding, finding_state, priority in finding_entries:
            if finding_state not in {FindingState.needs_manual_review, FindingState.blocked}:
                continue
            tasks.append(
                ManualReviewTask(
                    manual_review_task_id=str(uuid.uuid4()),
                    run_id=run_id,
                    asset_id=finding.asset_id,
                    finding_id=finding.finding_id,
                    defect_id=None,
                    task_type=ManualReviewTaskType.finding_review,
                    status=ManualReviewTaskStatus.pending,
                    priority=priority,
                    source_state=finding_state,
                    reason=finding_state.value,
                    task_metadata={
                        "rule_id": finding.rule_id,
                        "wcag_sc": finding.wcag_sc,
                        "message": finding.message,
                        "target_fingerprint": finding.target_fingerprint,
                        "origin": finding.raw_payload.get("origin", "automated"),
                    },
                    created_at=now,
                    updated_at=now,
                ),
            )

        for defect in defects:
            if defect.priority != DefectPriority.P1:
                continue
            tasks.append(
                ManualReviewTask(
                    manual_review_task_id=str(uuid.uuid4()),
                    run_id=run_id,
                    asset_id=None,
                    finding_id=None,
                    defect_id=defect.defect_id,
                    task_type=ManualReviewTaskType.at_validation,
                    status=ManualReviewTaskStatus.pending,
                    priority=DefectPriority.P1,
                    source_state=FindingState.fail,
                    reason="p1_at_validation",
                    task_metadata={
                        "issue_id": defect.issue_id,
                        "rule_id": defect.rule_id,
                        "wcag_sc": defect.wcag_sc,
                        "impacted_asset_count": defect.impacted_asset_count,
                        "owner_team": defect.owner_team,
                    },
                    created_at=now,
                    updated_at=now,
                ),
            )

        return tasks
