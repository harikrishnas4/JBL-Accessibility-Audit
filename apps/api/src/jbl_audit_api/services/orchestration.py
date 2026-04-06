from __future__ import annotations

from datetime import UTC, datetime
import uuid

from jbl_audit_api.core.exceptions import NotFoundError
from jbl_audit_api.db.models import (
    Asset,
    AssetClassification,
    AuditRun,
    AuditRunStage,
    AuditRunStatus,
    RunPlan,
    RunPlanStatus,
    ScanBatch,
    ScanBatchStatus,
)
from jbl_audit_api.repositories.orchestration import OrchestrationRepository
from jbl_audit_api.services.orchestration_dispatcher import (
    LocalInProcessDispatcher,
    LocalTaskDispatcher,
    dispatch_batch,
)
from jbl_audit_api.services.orchestration_planner import (
    BatchPlanner,
    BatchPlanningResult,
    ClassifiedAssetContext,
    DEFAULT_RETRY_POLICY,
    VIEWPORT_MATRIX,
)


class OrchestrationService:
    def __init__(
        self,
        repository: OrchestrationRepository,
        planner: BatchPlanner | None = None,
        dispatcher: LocalTaskDispatcher | None = None,
    ) -> None:
        self.repository = repository
        self.planner = planner or BatchPlanner()
        self.dispatcher = dispatcher or LocalInProcessDispatcher()

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
            crawl_snapshot_metadata=run_context.crawl_snapshot.snapshot_metadata if run_context.crawl_snapshot else None,
        )

        persisted_batches = self._persist_batches(run_context, run_plan, planning, now)
        run_plan.dispatcher_name = self.dispatcher.name
        run_plan.viewport_matrix = list(self._viewport_matrix())
        run_plan.retry_policy = self._retry_policy()
        run_plan.scan_batch_count = sum(1 for batch in persisted_batches if batch.status == ScanBatchStatus.dispatched)
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

        run_context.current_stage = AuditRunStage.orchestration
        run_context.status = AuditRunStatus.in_progress
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
            outcome = dispatch_batch(self.dispatcher, planned_batch)
            batches.append(
                ScanBatch(
                    scan_batch_id=str(uuid.uuid4()),
                    run_plan_id=run_plan.run_plan_id,
                    run_id=run_context.run_id,
                    batch_key=planned_batch.batch_key,
                    batch_type=planned_batch.batch_type,
                    status=outcome.status,
                    chapter_key=planned_batch.chapter_key,
                    shared_key=planned_batch.shared_key,
                    asset_ids=list(planned_batch.asset_ids),
                    viewport_matrix=list(planned_batch.viewport_matrix),
                    retry_policy=dict(planned_batch.retry_policy),
                    task_contract=planned_batch.task_contract,
                    dispatcher_metadata=outcome.dispatcher_metadata,
                    created_at=now,
                    updated_at=now,
                ),
            )

        self.repository.save_run_plan(run_plan)
        self.repository.replace_batches(run_plan, batches)
        return batches

    def _classified_assets(self, assets: list[Asset]) -> list[ClassifiedAssetContext]:
        return [
            ClassifiedAssetContext(asset=asset, classification=asset.classification_record)
            for asset in assets
            if asset.classification_record is not None
        ]

    def _resolve_run_plan_status(self, batches: list[ScanBatch]) -> RunPlanStatus:
        if not batches:
            return RunPlanStatus.planned
        if any(batch.status == ScanBatchStatus.dispatched for batch in batches):
            return RunPlanStatus.dispatched
        if any(batch.status == ScanBatchStatus.manual_pending for batch in batches):
            return RunPlanStatus.manual_pending
        return RunPlanStatus.planned

    def _viewport_matrix(self) -> tuple[dict[str, int | str], ...]:
        return VIEWPORT_MATRIX

    def _retry_policy(self) -> dict:
        return dict(DEFAULT_RETRY_POLICY)
