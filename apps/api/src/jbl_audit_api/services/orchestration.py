from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from jbl_audit_api.core.exceptions import NotFoundError, ServiceError
from jbl_audit_api.db.models import (
    Asset,
    AuditRun,
    AuditRunStage,
    AuditRunStatus,
    RunPlan,
    RunPlanStatus,
    ScanBatch,
    ScanBatchStatus,
    ScanBatchType,
)
from jbl_audit_api.repositories.orchestration import OrchestrationRepository
from jbl_audit_api.services.orchestration_dispatcher import (
    LocalTaskDispatcher,
    dispatch_batch,
)
from jbl_audit_api.services.orchestration_execution import latest_session_state_path
from jbl_audit_api.services.orchestration_planner import (
    DEFAULT_RETRY_POLICY,
    VIEWPORT_MATRIX,
    BatchPlanner,
    BatchPlanningResult,
    ClassifiedAssetContext,
    PlannedBatch,
)

if TYPE_CHECKING:
    from jbl_audit_api.services.orchestration_dispatcher import DispatchOutcome


class OrchestrationService:
    def __init__(
        self,
        repository: OrchestrationRepository,
        planner: BatchPlanner | None = None,
        dispatcher: LocalTaskDispatcher | None = None,
    ) -> None:
        self.repository = repository
        self.planner = planner or BatchPlanner()
        if dispatcher is None:
            raise ValueError("OrchestrationService requires a dispatcher instance.")
        self.dispatcher = dispatcher

    def initialize_run_plan(self, run_id: str) -> RunPlan:
        run_context = self.repository.get_run_context(run_id)
        if run_context is None:
            raise NotFoundError(f"run '{run_id}' does not exist")
        return self._apply_plan(run_context)

    def refresh_run_plan(self, run_id: str) -> RunPlan:
        run_context = self.repository.get_run_context(run_id)
        if run_context is None:
            raise NotFoundError(f"run '{run_id}' does not exist")
        return self._apply_plan(run_context)

    def _apply_plan(self, run_context: AuditRun) -> RunPlan:
        now = datetime.now(UTC)
        run_plan = run_context.run_plan or RunPlan(
            run_plan_id=str(uuid.uuid4()),
            run_id=run_context.run_id,
            status=RunPlanStatus.awaiting_assets,
            dispatcher_name=self.dispatcher.name,
            viewport_matrix=list(self._viewport_matrix()),
            retry_policy=self._retry_policy(),
            scan_batch_count=0,
            manual_task_count=0,
            orchestration_metadata={},
            created_at=now,
            updated_at=now,
        )
        if run_context.run_plan is None:
            run_context.run_plan = run_plan

        classified_assets = self._classified_assets(run_context.assets)
        if not classified_assets:
            run_plan.dispatcher_name = self.dispatcher.name
            run_plan.status = RunPlanStatus.awaiting_assets
            run_plan.viewport_matrix = list(self._viewport_matrix())
            run_plan.retry_policy = self._retry_policy()
            run_plan.scan_batch_count = 0
            run_plan.manual_task_count = 0
            run_plan.orchestration_metadata = {
                "batch_count": 0,
                "excluded_asset_ids": [],
                "scan_asset_ids": [],
                "manual_asset_ids": [],
            }
            run_plan.updated_at = now
            run_context.current_stage = AuditRunStage.intake
            run_context.status = AuditRunStatus.queued
            self.repository.save_run_plan(run_plan)
            self.repository.replace_batches(run_plan, [])
            return run_plan

        planning = self.planner.plan(
            classified_assets,
            manifest_metadata=run_context.audit_input.manifest_metadata if run_context.audit_input else None,
            crawl_snapshot_metadata=(
                run_context.crawl_snapshot.snapshot_metadata if run_context.crawl_snapshot else None
            ),
        )

        persisted_batches = self._persist_batches(run_context, run_plan, planning, now)
        persisted_batches = self._execute_batches(run_context, run_plan, persisted_batches)
        run_plan.dispatcher_name = self.dispatcher.name
        run_plan.viewport_matrix = list(self._viewport_matrix())
        run_plan.retry_policy = self._retry_policy()
        run_plan.scan_batch_count = sum(
            1 for batch in persisted_batches if batch.batch_type == ScanBatchType.scan_worker
        )
        run_plan.manual_task_count = sum(
            len(batch.asset_ids) for batch in persisted_batches if batch.status == ScanBatchStatus.manual_pending
        )
        run_plan.status = self._resolve_run_plan_status(persisted_batches)
        run_plan.orchestration_metadata = {
            "batch_count": len(persisted_batches),
            "excluded_asset_ids": list(planning.excluded_asset_ids),
            "scan_asset_ids": list(planning.scan_asset_ids),
            "manual_asset_ids": list(planning.manual_asset_ids),
        }
        run_plan.updated_at = now

        self._apply_run_rollup(run_context, run_plan)
        self.repository.save_run_plan(run_plan)
        return run_plan

    def _persist_batches(
        self,
        run_context: AuditRun,
        run_plan: RunPlan,
        planning: BatchPlanningResult,
        now: datetime,
    ) -> list[ScanBatch]:
        batches: list[ScanBatch] = []
        for planned_batch in planning.planned_batches:
            manual_outcome = (
                dispatch_batch(self.dispatcher, run_context.run_id, planned_batch)
                if planned_batch.batch_type == ScanBatchType.manual_review_stub
                else None
            )
            batches.append(
                ScanBatch(
                    scan_batch_id=str(uuid.uuid4()),
                    run_plan_id=run_plan.run_plan_id,
                    run_id=run_context.run_id,
                    batch_key=planned_batch.batch_key,
                    batch_type=planned_batch.batch_type,
                    status=(
                        manual_outcome.status if manual_outcome is not None else ScanBatchStatus.queued
                    ),
                    chapter_key=planned_batch.chapter_key,
                    shared_key=planned_batch.shared_key,
                    asset_ids=list(planned_batch.asset_ids),
                    viewport_matrix=list(planned_batch.viewport_matrix),
                    retry_policy=dict(planned_batch.retry_policy),
                    task_contract=planned_batch.task_contract,
                    dispatcher_metadata={
                        **(
                            manual_outcome.dispatcher_metadata
                            if manual_outcome is not None
                            else {
                                "dispatcher": self.dispatcher.name,
                                "queued_at": now.isoformat(),
                                "contract_type": planned_batch.task_contract.get("contract_type"),
                            }
                        ),
                    },
                    created_at=now,
                    updated_at=now,
                ),
            )

        self.repository.save_run_plan(run_plan)
        self.repository.replace_batches(run_plan, batches)
        return batches

    def _execute_batches(
        self,
        run_context: AuditRun,
        run_plan: RunPlan,
        batches: list[ScanBatch],
    ) -> list[ScanBatch]:
        session_state_path = latest_session_state_path(run_context.auth_profiles)
        for batch in batches:
            if batch.batch_type != ScanBatchType.scan_worker:
                continue

            batch.status = ScanBatchStatus.running
            batch.dispatcher_metadata = {
                **batch.dispatcher_metadata,
                "running_at": datetime.now(UTC).isoformat(),
            }
            batch.updated_at = datetime.now(UTC)
            self.repository.save_run_plan(run_plan)

            planned_batch = self._planned_batch_from_scan_batch(batch)
            try:
                outcome = dispatch_batch(
                    self.dispatcher,
                    run_context.run_id,
                    planned_batch,
                    session_state_path=session_state_path,
                )
            except ServiceError as exc:
                outcome = self._failed_dispatch_outcome(exc)
            batch.status = outcome.status
            batch.dispatcher_metadata = {
                **batch.dispatcher_metadata,
                **outcome.dispatcher_metadata,
            }
            batch.updated_at = datetime.now(UTC)

        self.repository.save_run_plan(run_plan)
        return list(run_plan.scan_batches)

    def _classified_assets(self, assets: list[Asset]) -> list[ClassifiedAssetContext]:
        return [
            ClassifiedAssetContext(asset=asset, classification=asset.classification_record)
            for asset in assets
            if asset.classification_record is not None
        ]

    def _resolve_run_plan_status(self, batches: list[ScanBatch]) -> RunPlanStatus:
        if not batches:
            return RunPlanStatus.completed
        if any(batch.status == ScanBatchStatus.failed for batch in batches):
            return RunPlanStatus.failed
        if any(batch.status == ScanBatchStatus.running for batch in batches):
            return RunPlanStatus.running
        if any(batch.status == ScanBatchStatus.queued for batch in batches):
            return RunPlanStatus.queued
        if any(batch.status == ScanBatchStatus.manual_pending for batch in batches):
            return RunPlanStatus.manual_pending
        return RunPlanStatus.completed

    def _apply_run_rollup(self, run_context: AuditRun, run_plan: RunPlan) -> None:
        if run_plan.status == RunPlanStatus.awaiting_assets:
            run_context.current_stage = AuditRunStage.intake
            run_context.status = AuditRunStatus.queued
            return
        if run_plan.status == RunPlanStatus.failed:
            run_context.current_stage = AuditRunStage.failed
            run_context.status = AuditRunStatus.failed
            return
        if run_plan.status == RunPlanStatus.completed:
            run_context.current_stage = AuditRunStage.completed
            run_context.status = AuditRunStatus.completed
            return
        run_context.current_stage = AuditRunStage.orchestration
        run_context.status = AuditRunStatus.in_progress

    def _planned_batch_from_scan_batch(self, batch: ScanBatch) -> PlannedBatch:
        return PlannedBatch(
            batch_key=batch.batch_key,
            batch_type=batch.batch_type,
            chapter_key=batch.chapter_key,
            shared_key=batch.shared_key,
            asset_ids=tuple(batch.asset_ids),
            viewport_matrix=tuple(batch.viewport_matrix),
            retry_policy=dict(batch.retry_policy),
            task_contract=batch.task_contract,
        )

    def _failed_dispatch_outcome(self, error: ServiceError) -> "DispatchOutcome":
        from jbl_audit_api.services.orchestration_dispatcher import DispatchOutcome

        return DispatchOutcome(
            status=ScanBatchStatus.failed,
            dispatcher_metadata={
                "dispatcher": self.dispatcher.name,
                "dispatch_mode": "in_process_scan_execution",
                "error": error.message,
                "failed_at": datetime.now(UTC).isoformat(),
            },
        )

    def _viewport_matrix(self) -> tuple[dict[str, int | str], ...]:
        return VIEWPORT_MATRIX

    def _retry_policy(self) -> dict:
        return dict(DEFAULT_RETRY_POLICY)
