from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from jbl_audit_api.db.models import ScanBatchStatus, ScanBatchType
from jbl_audit_api.services.orchestration_execution import (
    FindingResultSink,
    Tier1BatchExecutor,
)
from jbl_audit_api.services.orchestration_planner import PlannedBatch


@dataclass(slots=True, frozen=True)
class DispatchOutcome:
    status: ScanBatchStatus
    dispatcher_metadata: dict


class LocalTaskDispatcher(Protocol):
    name: str

    def dispatch_scan_batch(
        self,
        run_id: str,
        batch: PlannedBatch,
        *,
        session_state_path: str | None = None,
    ) -> DispatchOutcome:
        ...

    def dispatch_manual_batch(self, batch: PlannedBatch) -> DispatchOutcome:
        ...


class LocalInProcessDispatcher:
    name = "local_in_process"

    def __init__(
        self,
        executor: Tier1BatchExecutor,
        result_sink: FindingResultSink,
    ) -> None:
        self.executor = executor
        self.result_sink = result_sink

    def dispatch_scan_batch(
        self,
        run_id: str,
        batch: PlannedBatch,
        *,
        session_state_path: str | None = None,
    ) -> DispatchOutcome:
        started_at = datetime.now(UTC).isoformat()
        execution = self.executor.execute_batch(
            run_id,
            batch,
            session_state_path=session_state_path,
        )
        persisted_assets: list[dict] = []
        total_persisted_findings = 0
        total_evidence_artifacts = 0
        for asset_result in execution.asset_results:
            if asset_result.findings:
                persisted = self.result_sink.ingest(
                    run_id,
                    asset_result.asset_id,
                    list(asset_result.findings),
                    asset_result.scan_metadata,
                )
            else:
                persisted = {
                    "run_id": run_id,
                    "asset_id": asset_result.asset_id,
                    "persisted_finding_count": 0,
                    "evidence_artifact_count": 0,
                    "result_counts": {
                        "violation": 0,
                        "pass": 0,
                        "incomplete": 0,
                        "inapplicable": 0,
                    },
                    "scan_metadata": asset_result.scan_metadata,
                }
            total_persisted_findings += int(persisted["persisted_finding_count"])
            total_evidence_artifacts += int(persisted["evidence_artifact_count"])
            persisted_assets.append(persisted)

        status = ScanBatchStatus.completed if not execution.failures else ScanBatchStatus.failed
        return DispatchOutcome(
            status=status,
            dispatcher_metadata={
                "dispatcher": self.name,
                "started_at": started_at,
                "completed_at": datetime.now(UTC).isoformat(),
                "dispatch_mode": "in_process_scan_execution",
                "contract_type": batch.task_contract.get("contract_type"),
                "asset_count": len(batch.asset_ids),
                "viewport_count": len(batch.viewport_matrix),
                "session_state_path": session_state_path,
                "persisted_assets": persisted_assets,
                "persisted_finding_count": total_persisted_findings,
                "evidence_artifact_count": total_evidence_artifacts,
                "execution_summary": execution.summary,
                "failures": [
                    {
                        "asset_id": failure.asset_id,
                        "asset_type": failure.asset_type,
                        "error": failure.error,
                        "viewport": failure.viewport,
                    }
                    for failure in execution.failures
                ],
            },
        )

    def dispatch_manual_batch(self, batch: PlannedBatch) -> DispatchOutcome:
        return DispatchOutcome(
            status=ScanBatchStatus.manual_pending,
            dispatcher_metadata={
                "dispatcher": self.name,
                "dispatched_at": datetime.now(UTC).isoformat(),
                "dispatch_mode": "manual_task_stub",
                "contract_type": batch.task_contract.get("contract_type"),
                "asset_count": len(batch.asset_ids),
            },
        )


def dispatch_batch(
    dispatcher: LocalTaskDispatcher,
    run_id: str,
    batch: PlannedBatch,
    *,
    session_state_path: str | None = None,
) -> DispatchOutcome:
    if batch.batch_type == ScanBatchType.scan_worker:
        return dispatcher.dispatch_scan_batch(run_id, batch, session_state_path=session_state_path)
    return dispatcher.dispatch_manual_batch(batch)
