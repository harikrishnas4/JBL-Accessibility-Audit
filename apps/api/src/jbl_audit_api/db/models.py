from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jbl_audit_api.db.base import Base


class AuditRunStatus(str, Enum):
    queued = "queued"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class AuditRunStage(str, Enum):
    intake = "intake"
    orchestration = "orchestration"
    completed = "completed"
    failed = "failed"


class AuditRunMode(str, Enum):
    manifest_full = "manifest/full"
    partial = "partial"
    crawler_only = "crawler_only"


class AuthProfileValidationStatus(str, Enum):
    pending = "pending"
    validated = "validated"
    failed = "failed"


class AssetScopeStatus(str, Enum):
    in_scope = "in_scope"
    out_of_scope = "out_of_scope"


class AssetLayer(str, Enum):
    platform = "platform"
    course_shell = "course_shell"
    content = "content"
    component = "component"
    document = "document"
    media = "media"
    third_party = "third_party"


class AssetHandlingPath(str, Enum):
    automated = "automated"
    automated_plus_manual = "automated_plus_manual"
    manual_only = "manual_only"
    evidence_only = "evidence_only"
    excluded = "excluded"


class ProcessFlowType(str, Enum):
    learner_default = "learner_default"
    quiz_flow = "quiz_flow"
    lti_flow = "lti_flow"


class ProcessFlowStepStatus(str, Enum):
    present = "present"
    missing = "missing"


class RunPlanStatus(str, Enum):
    awaiting_assets = "awaiting_assets"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    manual_pending = "manual_pending"


class ScanBatchStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    manual_pending = "manual_pending"


class ScanBatchType(str, Enum):
    scan_worker = "scan_worker"
    manual_review_stub = "manual_review_stub"


class RawFindingResultType(str, Enum):
    violation = "violation"
    pass_ = "pass"
    incomplete = "incomplete"
    inapplicable = "inapplicable"


class EvidenceArtifactType(str, Enum):
    screenshot = "screenshot"
    trace = "trace"
    dom_snapshot_reference = "dom_snapshot_reference"


class FindingState(str, Enum):
    pass_ = "pass"
    fail = "fail"
    needs_manual_review = "needs_manual_review"
    inapplicable = "inapplicable"
    blocked = "blocked"


class DefectPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ManualReviewTaskType(str, Enum):
    finding_review = "finding_review"
    asset_review = "asset_review"
    at_validation = "at_validation"


class ManualReviewTaskStatus(str, Enum):
    pending = "pending"


class AuditRun(Base):
    __tablename__ = "audit_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[AuditRunStatus] = mapped_column(
        SqlEnum(AuditRunStatus, name="audit_run_status_enum", native_enum=False),
        nullable=False,
    )
    current_stage: Mapped[AuditRunStage] = mapped_column(
        SqlEnum(AuditRunStage, name="audit_run_stage_enum", native_enum=False),
        nullable=False,
    )
    mode: Mapped[AuditRunMode] = mapped_column(
        SqlEnum(AuditRunMode, name="audit_run_mode_enum", native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_input: Mapped["AuditInput"] = relationship(
        back_populates="audit_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    schema_registry_entries: Mapped[list["SchemaRegistryEntry"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    report_records: Mapped[list["ReportRecord"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    auth_profiles: Mapped[list["AuthProfile"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    crawl_snapshot: Mapped["CrawlSnapshot | None"] = relationship(
        back_populates="audit_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    assets: Mapped[list["Asset"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    asset_classifications: Mapped[list["AssetClassification"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
        overlaps="asset,classification_record",
    )
    process_flows: Mapped[list["ProcessFlow"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    process_flow_steps: Mapped[list["ProcessFlowStep"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
        overlaps="steps,process_flow",
    )
    run_plan: Mapped["RunPlan | None"] = relationship(
        back_populates="audit_run",
        uselist=False,
        cascade="all, delete-orphan",
    )
    raw_findings: Mapped[list["RawFinding"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    evidence_artifacts: Mapped[list["EvidenceArtifact"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
        overlaps="raw_finding,evidence_artifacts",
    )
    defects: Mapped[list["Defect"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
    )
    manual_review_tasks: Mapped[list["ManualReviewTask"]] = relationship(
        back_populates="audit_run",
        cascade="all, delete-orphan",
        overlaps="asset,manual_review_tasks",
    )


class AuditInput(Base):
    __tablename__ = "audit_inputs"

    input_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    course_url_or_name: Mapped[str] = mapped_column(String(2048), nullable=False)
    auth_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    manifest_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="audit_input")


class SchemaRegistryEntry(Base):
    __tablename__ = "schema_registry_entries"

    schema_registry_entry_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun | None] = relationship(back_populates="schema_registry_entries")


class ReportRecord(Base):
    __tablename__ = "report_records"

    report_record_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    report_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="report_records")


class ThirdPartyEvidence(Base):
    __tablename__ = "third_party_evidence"
    __table_args__ = (
        UniqueConstraint("provider_key", name="uq_third_party_evidence_provider_key"),
    )

    third_party_evidence_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    linked_shared_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    provider_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    asset_classifications: Mapped[list["AssetClassification"]] = relationship(
        back_populates="third_party_evidence",
    )


class AuthProfile(Base):
    __tablename__ = "auth_profiles"

    auth_profile_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    auth_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    session_state_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    validation_status: Mapped[AuthProfileValidationStatus] = mapped_column(
        SqlEnum(AuthProfileValidationStatus, name="auth_profile_validation_status_enum", native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="auth_profiles")


class CrawlSnapshot(Base):
    __tablename__ = "crawl_snapshots"

    crawl_snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    entry_locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    visited_locators: Mapped[list[dict] | list[str]] = mapped_column(JSON, nullable=False, default=list)
    excluded_locators: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    snapshot_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="crawl_snapshot")
    assets: Mapped[list["Asset"]] = relationship(back_populates="crawl_snapshot")


class Asset(Base):
    __tablename__ = "assets"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    asset_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    crawl_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("crawl_snapshots.crawl_snapshot_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_system: Mapped[str] = mapped_column(String(255), nullable=False)
    locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    scope_status: Mapped[AssetScopeStatus] = mapped_column(
        SqlEnum(AssetScopeStatus, name="asset_scope_status_enum", native_enum=False),
        nullable=False,
    )
    scope_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    layer: Mapped[str] = mapped_column(String(128), nullable=False)
    shared_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    owner_team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    handling_path: Mapped[str] = mapped_column(String(255), nullable=False)
    component_fingerprint: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="assets")
    crawl_snapshot: Mapped[CrawlSnapshot | None] = relationship(back_populates="assets")
    classification_record: Mapped["AssetClassification | None"] = relationship(
        back_populates="asset",
        uselist=False,
        cascade="all, delete-orphan",
        overlaps="asset_classifications,audit_run",
    )
    process_flow_steps: Mapped[list["ProcessFlowStep"]] = relationship(
        back_populates="asset",
        overlaps="process_flow,audit_run,process_flow_steps",
    )
    raw_findings: Mapped[list["RawFinding"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        overlaps="audit_run,raw_findings",
    )
    defect_components: Mapped[list["DefectComponent"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    manual_review_tasks: Mapped[list["ManualReviewTask"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        overlaps="audit_run,manual_review_tasks",
    )


class AssetClassification(Base):
    __tablename__ = "asset_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("run_id", "asset_id", name="uq_asset_classifications_run_asset"),
    )

    classification_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    layer: Mapped[AssetLayer] = mapped_column(
        SqlEnum(AssetLayer, name="asset_layer_enum", native_enum=False),
        nullable=False,
    )
    handling_path: Mapped[AssetHandlingPath] = mapped_column(
        SqlEnum(AssetHandlingPath, name="asset_handling_path_enum", native_enum=False),
        nullable=False,
    )
    shared_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    owner_team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    third_party: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    third_party_evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("third_party_evidence.third_party_evidence_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    auth_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    exclusion_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(
        back_populates="asset_classifications",
        overlaps="classification_record,asset",
    )
    asset: Mapped[Asset] = relationship(
        back_populates="classification_record",
        overlaps="asset_classifications,audit_run",
    )
    third_party_evidence: Mapped[ThirdPartyEvidence | None] = relationship(
        back_populates="asset_classifications",
    )


class ProcessFlow(Base):
    __tablename__ = "process_flows"

    process_flow_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flow_type: Mapped[ProcessFlowType] = mapped_column(
        SqlEnum(ProcessFlowType, name="process_flow_type_enum", native_enum=False),
        nullable=False,
    )
    flow_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    entry_locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    flow_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="process_flows")
    steps: Mapped[list["ProcessFlowStep"]] = relationship(
        back_populates="process_flow",
        cascade="all, delete-orphan",
        order_by="ProcessFlowStep.step_order",
    )


class ProcessFlowStep(Base):
    __tablename__ = "process_flow_steps"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("process_flow_id", "step_order", name="uq_process_flow_steps_flow_order"),
    )

    process_flow_step_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    process_flow_id: Mapped[str] = mapped_column(
        ForeignKey("process_flows.process_flow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    step_order: Mapped[int] = mapped_column(nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    step_status: Mapped[ProcessFlowStepStatus] = mapped_column(
        SqlEnum(ProcessFlowStepStatus, name="process_flow_step_status_enum", native_enum=False),
        nullable=False,
    )
    locator: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    process_flow: Mapped[ProcessFlow] = relationship(back_populates="steps")
    audit_run: Mapped[AuditRun] = relationship(back_populates="process_flow_steps", overlaps="steps,process_flow")
    asset: Mapped[Asset | None] = relationship(
        back_populates="process_flow_steps",
        overlaps="process_flow,audit_run,process_flows,process_flow_steps",
    )


class RunPlan(Base):
    __tablename__ = "run_plans"

    run_plan_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[RunPlanStatus] = mapped_column(
        SqlEnum(RunPlanStatus, name="run_plan_status_enum", native_enum=False),
        nullable=False,
    )
    dispatcher_name: Mapped[str] = mapped_column(String(128), nullable=False)
    viewport_matrix: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    retry_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    scan_batch_count: Mapped[int] = mapped_column(nullable=False, default=0)
    manual_task_count: Mapped[int] = mapped_column(nullable=False, default=0)
    orchestration_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="run_plan")
    scan_batches: Mapped[list["ScanBatch"]] = relationship(
        back_populates="run_plan",
        cascade="all, delete-orphan",
        order_by="ScanBatch.batch_key",
    )


class ScanBatch(Base):
    __tablename__ = "scan_batches"
    __table_args__ = (
        UniqueConstraint("run_plan_id", "batch_key", name="uq_scan_batches_plan_batch_key"),
    )

    scan_batch_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_plan_id: Mapped[str] = mapped_column(
        ForeignKey("run_plans.run_plan_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_key: Mapped[str] = mapped_column(String(255), nullable=False)
    batch_type: Mapped[ScanBatchType] = mapped_column(
        SqlEnum(ScanBatchType, name="scan_batch_type_enum", native_enum=False),
        nullable=False,
    )
    status: Mapped[ScanBatchStatus] = mapped_column(
        SqlEnum(ScanBatchStatus, name="scan_batch_status_enum", native_enum=False),
        nullable=False,
    )
    chapter_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    shared_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    viewport_matrix: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    retry_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    task_contract: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dispatcher_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run_plan: Mapped[RunPlan] = relationship(back_populates="scan_batches")
    audit_run: Mapped[AuditRun] = relationship(overlaps="asset,defect_components")


class RawFinding(Base):
    __tablename__ = "raw_findings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
    )

    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    result_type: Mapped[RawFindingResultType] = mapped_column(
        SqlEnum(RawFindingResultType, name="raw_finding_result_type_enum", native_enum=False),
        nullable=False,
    )
    rule_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    wcag_sc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution_state: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(String(4096), nullable=False)
    target_fingerprint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="raw_findings")
    asset: Mapped[Asset] = relationship(
        back_populates="raw_findings",
        overlaps="audit_run,raw_findings",
    )
    evidence_artifacts: Mapped[list["EvidenceArtifact"]] = relationship(
        back_populates="raw_finding",
        cascade="all, delete-orphan",
        order_by="EvidenceArtifact.captured_at",
    )


class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifacts"

    evidence_artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finding_id: Mapped[str] = mapped_column(
        ForeignKey("raw_findings.finding_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    artifact_type: Mapped[EvidenceArtifactType] = mapped_column(
        SqlEnum(EvidenceArtifactType, name="evidence_artifact_type_enum", native_enum=False),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    artifact_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    raw_finding: Mapped[RawFinding] = relationship(back_populates="evidence_artifacts")
    audit_run: Mapped[AuditRun] = relationship(
        back_populates="evidence_artifacts",
        overlaps="raw_finding,evidence_artifacts",
    )


class Defect(Base):
    __tablename__ = "defects"
    __table_args__ = (
        UniqueConstraint("run_id", "defect_signature", name="uq_defects_run_signature"),
    )

    defect_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    defect_signature: Mapped[str] = mapped_column(String(2048), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    wcag_sc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    finding_state: Mapped[FindingState] = mapped_column(
        SqlEnum(FindingState, name="finding_state_enum", native_enum=False),
        nullable=False,
    )
    priority: Mapped[DefectPriority] = mapped_column(
        SqlEnum(DefectPriority, name="defect_priority_enum", native_enum=False),
        nullable=False,
    )
    layer: Mapped[AssetLayer] = mapped_column(
        SqlEnum(AssetLayer, name="asset_layer_enum", native_enum=False),
        nullable=False,
    )
    owner_team: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shared_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    target_fingerprint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    message_key: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(4096), nullable=False)
    finding_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    impacted_asset_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(back_populates="defects")
    components: Mapped[list["DefectComponent"]] = relationship(
        back_populates="defect",
        cascade="all, delete-orphan",
        order_by="DefectComponent.asset_id",
    )
    manual_review_tasks: Mapped[list["ManualReviewTask"]] = relationship(
        back_populates="defect",
        cascade="all, delete-orphan",
    )

    @property
    def third_party_evidence(self) -> ThirdPartyEvidence | None:
        for component in self.components:
            asset = component.asset
            if asset is None or asset.classification_record is None:
                continue
            if asset.classification_record.third_party_evidence is not None:
                return asset.classification_record.third_party_evidence
        return None


class DefectComponent(Base):
    __tablename__ = "defect_components"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("defect_id", "asset_id", name="uq_defect_components_defect_asset"),
    )

    defect_component_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    defect_id: Mapped[str] = mapped_column(
        ForeignKey("defects.defect_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str] = mapped_column(String(128), nullable=False)
    finding_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_findings.finding_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shared_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    locator: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    defect: Mapped[Defect] = relationship(back_populates="components")
    audit_run: Mapped[AuditRun] = relationship(overlaps="asset,defect_components")
    asset: Mapped[Asset] = relationship(back_populates="defect_components", overlaps="audit_run,defect_components")
    raw_finding: Mapped[RawFinding | None] = relationship()


class ManualReviewTask(Base):
    __tablename__ = "manual_review_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "asset_id"],
            ["assets.run_id", "assets.asset_id"],
            ondelete="CASCADE",
        ),
    )

    manual_review_task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("audit_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    finding_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_findings.finding_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    defect_id: Mapped[str | None] = mapped_column(
        ForeignKey("defects.defect_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[ManualReviewTaskType] = mapped_column(
        SqlEnum(ManualReviewTaskType, name="manual_review_task_type_enum", native_enum=False),
        nullable=False,
    )
    status: Mapped[ManualReviewTaskStatus] = mapped_column(
        SqlEnum(ManualReviewTaskStatus, name="manual_review_task_status_enum", native_enum=False),
        nullable=False,
    )
    priority: Mapped[DefectPriority | None] = mapped_column(
        SqlEnum(DefectPriority, name="defect_priority_enum", native_enum=False),
        nullable=True,
    )
    source_state: Mapped[FindingState | None] = mapped_column(
        SqlEnum(FindingState, name="finding_state_enum", native_enum=False),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    task_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    audit_run: Mapped[AuditRun] = relationship(
        back_populates="manual_review_tasks",
        overlaps="asset,manual_review_tasks",
    )
    asset: Mapped[Asset | None] = relationship(
        back_populates="manual_review_tasks",
        overlaps="audit_run,manual_review_tasks",
    )
    raw_finding: Mapped[RawFinding | None] = relationship()
    defect: Mapped[Defect | None] = relationship(back_populates="manual_review_tasks")


__all__ = [
    "Defect",
    "DefectComponent",
    "DefectPriority",
    "EvidenceArtifact",
    "EvidenceArtifactType",
    "FindingState",
    "Asset",
    "AssetClassification",
    "AssetHandlingPath",
    "AssetLayer",
    "AssetScopeStatus",
    "AuditInput",
    "AuthProfile",
    "AuthProfileValidationStatus",
    "AuditRun",
    "AuditRunMode",
    "AuditRunStage",
    "AuditRunStatus",
    "Base",
    "CrawlSnapshot",
    "ManualReviewTask",
    "ManualReviewTaskStatus",
    "ManualReviewTaskType",
    "ProcessFlow",
    "ProcessFlowStep",
    "ProcessFlowStepStatus",
    "ProcessFlowType",
    "RawFinding",
    "RawFindingResultType",
    "ReportRecord",
    "RunPlan",
    "RunPlanStatus",
    "ScanBatch",
    "ScanBatchStatus",
    "ScanBatchType",
    "SchemaRegistryEntry",
    "ThirdPartyEvidence",
]
