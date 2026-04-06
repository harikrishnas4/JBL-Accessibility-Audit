from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from jbl_audit_api.db.models import ScanBatchStatus, ScanBatchType
from jbl_audit_api.services.orchestration_planner import PlannedBatch


@dataclass(slots=True, frozen=True)
class DispatchOutcome:
    status: ScanBatchStatus
    dispatcher_metadata: dict


class LocalTaskDispatcher(Protocol):
    name: str

    def dispatch_scan_batch(self, batch: PlannedBatch) -> DispatchOutcome:
        ...

    def dispatch_manual_batch(self, batch: PlannedBatch) -> DispatchOutcome:
        ...


class LocalInProcessDispatcher:
    name = "local_in_process"

    def dispatch_scan_batch(self, batch: PlannedBatch) -> DispatchOutcome:
        return DispatchOutcome(
            status=ScanBatchStatus.dispatched,
            dispatcher_metadata={
                "dispatcher": self.name,
                "dispatched_at": datetime.now(UTC).isoformat(),
                "dispatch_mode": "in_process_stub",
                "contract_type": batch.task_contract.get("contract_type"),
                "asset_count": len(batch.asset_ids),
                "viewport_count": len(batch.viewport_matrix),
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


def dispatch_batch(dispatcher: LocalTaskDispatcher, batch: PlannedBatch) -> DispatchOutcome:
    if batch.batch_type == ScanBatchType.scan_worker:
        return dispatcher.dispatch_scan_batch(batch)
    return dispatcher.dispatch_manual_batch(batch)
