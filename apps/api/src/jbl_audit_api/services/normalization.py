from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import uuid

from jbl_audit_api.core.exceptions import NotFoundError
from jbl_audit_api.db.models import (
    Asset,
    AssetHandlingPath,
    AssetLayer,
    Defect,
    DefectComponent,
    DefectPriority,
    FindingState,
    RawFinding,
    RawFindingResultType,
)
from jbl_audit_api.repositories.defects import DefectRepository
from jbl_audit_api.repositories.runs import RunRepository
from jbl_audit_api.services.manual_review import ManualReviewService
from jbl_audit_api.services.reporting import ReportingService


PRIORITY_BY_SEVERITY = {
    "critical": DefectPriority.P1,
    "serious": DefectPriority.P2,
    "moderate": DefectPriority.P3,
    "minor": DefectPriority.P4,
    "high": DefectPriority.P1,
    "medium": DefectPriority.P2,
    "low": DefectPriority.P3,
}


@dataclass(slots=True)
class DefectAggregate:
    signature: str
    issue_id: str
    rule_id: str
    wcag_sc: str | None
    priority: DefectPriority
    layer: AssetLayer
    owner_team: str | None
    shared_key: str | None
    target_fingerprint: str | None
    message_key: str
    message: str
    finding_origin: str
    asset_ids: set[str] = field(default_factory=set)
    components: list[DefectComponent] = field(default_factory=list)


class NormalizationService:
    def __init__(
        self,
        repository: DefectRepository,
        run_repository: RunRepository,
        manual_review_service: ManualReviewService | None = None,
        report_service: ReportingService | None = None,
    ) -> None:
        self.repository = repository
        self.run_repository = run_repository
        self.manual_review_service = manual_review_service or ManualReviewService()
        self.report_service = report_service

    def sync_run(self, run_id: str) -> tuple[list[Defect], list]:
        if self.run_repository.get(run_id) is None:
            raise NotFoundError(f"run '{run_id}' does not exist")

        assets = self.repository.list_assets_for_run(run_id)
        findings = self.repository.list_raw_findings_for_run(run_id)
        defects, finding_entries = self._build_defects(run_id, findings)
        manual_review_tasks = self.manual_review_service.build_tasks(run_id, assets, finding_entries, defects)
        self.repository.replace_run_outputs(run_id, defects, manual_review_tasks)
        if self.report_service is not None:
            self.report_service.generate_excel_report(run_id)
        return defects, manual_review_tasks

    def list_defects(self, run_id: str | None = None) -> dict:
        defects = self.repository.list_defects(run_id)
        return {
            "defect_count": len(defects),
            "defects": defects,
        }

    def _build_defects(
        self,
        run_id: str,
        findings: list[RawFinding],
    ) -> tuple[list[Defect], list[tuple[RawFinding, FindingState, DefectPriority | None]]]:
        now = datetime.now(UTC)
        aggregates: dict[str, DefectAggregate] = {}
        finding_entries: list[tuple[RawFinding, FindingState, DefectPriority | None]] = []

        for finding in findings:
            asset = finding.asset
            classification = asset.classification_record if asset is not None else None
            finding_state = determine_finding_state(finding)
            priority = map_priority(finding.severity)
            finding_entries.append((finding, finding_state, priority))

            if finding_state != FindingState.fail or asset is None:
                continue

            layer = resolve_layer(asset)
            shared_key = resolve_shared_key(asset)
            owner_team = resolve_owner_team(asset)
            message_key = build_message_key(finding.message)
            signature = build_defect_signature(
                rule_id=finding.rule_id,
                wcag_sc=finding.wcag_sc,
                shared_key=shared_key,
                target_fingerprint=finding.target_fingerprint,
                message_key=message_key,
            )
            finding_origin = resolve_finding_origin(finding)
            prefix = determine_issue_prefix(layer, shared_key, finding_origin)
            aggregate = aggregates.get(signature)
            if aggregate is None:
                aggregate = DefectAggregate(
                    signature=signature,
                    issue_id=build_issue_id(prefix, signature),
                    rule_id=finding.rule_id,
                    wcag_sc=finding.wcag_sc,
                    priority=priority,
                    layer=layer,
                    owner_team=owner_team,
                    shared_key=shared_key,
                    target_fingerprint=finding.target_fingerprint,
                    message_key=message_key,
                    message=finding.message,
                    finding_origin=finding_origin,
                )
                aggregates[signature] = aggregate
            else:
                if priority.value < aggregate.priority.value:
                    aggregate.priority = priority
                if aggregate.owner_team is None and owner_team is not None:
                    aggregate.owner_team = owner_team

            if asset.asset_id not in aggregate.asset_ids:
                aggregate.asset_ids.add(asset.asset_id)
                aggregate.components.append(
                    DefectComponent(
                        defect_component_id=str(uuid.uuid4()),
                        run_id=run_id,
                        asset_id=asset.asset_id,
                        finding_id=finding.finding_id,
                        shared_key=shared_key,
                        locator=asset.locator,
                        created_at=now,
                    ),
                )

        defects: list[Defect] = []
        for aggregate in aggregates.values():
            defect_id = str(uuid.uuid4())
            defect = Defect(
                defect_id=defect_id,
                run_id=run_id,
                issue_id=aggregate.issue_id,
                defect_signature=aggregate.signature,
                rule_id=aggregate.rule_id,
                wcag_sc=aggregate.wcag_sc,
                finding_state=FindingState.fail,
                priority=aggregate.priority,
                layer=aggregate.layer,
                owner_team=aggregate.owner_team,
                shared_key=aggregate.shared_key,
                target_fingerprint=aggregate.target_fingerprint,
                message_key=aggregate.message_key,
                message=aggregate.message,
                finding_origin=aggregate.finding_origin,
                impacted_asset_count=len(aggregate.asset_ids),
                created_at=now,
                updated_at=now,
            )
            for component in aggregate.components:
                component.defect_id = defect_id
            defect.components = aggregate.components
            defects.append(defect)

        defects.sort(key=lambda item: (item.issue_id, item.defect_id))
        return defects, finding_entries


def determine_finding_state(finding: RawFinding) -> FindingState:
    explicit_state = str(finding.raw_payload.get("finding_state") or "").strip().lower()
    if explicit_state:
        for state in FindingState:
            if state.value == explicit_state:
                return state

    resolution_state = finding.resolution_state.strip().lower()
    if resolution_state == FindingState.blocked.value:
        return FindingState.blocked
    if resolution_state == FindingState.needs_manual_review.value:
        return FindingState.needs_manual_review

    if finding.result_type == RawFindingResultType.violation:
        return FindingState.fail
    if finding.result_type == RawFindingResultType.pass_:
        return FindingState.pass_
    if finding.result_type == RawFindingResultType.incomplete:
        return FindingState.needs_manual_review
    return FindingState.inapplicable


def map_priority(severity: str | None) -> DefectPriority:
    normalized = (severity or "").strip().lower()
    return PRIORITY_BY_SEVERITY.get(normalized, DefectPriority.P4)


def build_message_key(message: str) -> str:
    normalized = " ".join(message.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_defect_signature(
    *,
    rule_id: str,
    wcag_sc: str | None,
    shared_key: str | None,
    target_fingerprint: str | None,
    message_key: str,
) -> str:
    return "|".join(
        [
            rule_id.strip().lower(),
            (wcag_sc or "").strip().lower(),
            (shared_key or "").strip().lower(),
            (target_fingerprint or "").strip().lower(),
            message_key,
        ],
    )


def resolve_finding_origin(finding: RawFinding) -> str:
    origin = str(finding.raw_payload.get("origin") or "automated").strip().lower()
    return origin or "automated"


def determine_issue_prefix(layer: AssetLayer, shared_key: str | None, finding_origin: str) -> str:
    if finding_origin == "manual_review":
        return "MR"
    if layer in {AssetLayer.platform, AssetLayer.course_shell}:
        return "GP"
    if layer == AssetLayer.component and shared_key:
        return "CP"
    return "CS"


def build_issue_id(prefix: str, signature: str) -> str:
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def resolve_layer(asset: Asset) -> AssetLayer:
    classification = asset.classification_record
    if classification is not None:
        return classification.layer
    try:
        return AssetLayer(asset.layer)
    except ValueError:
        return AssetLayer.content


def resolve_shared_key(asset: Asset) -> str | None:
    classification = asset.classification_record
    if classification is not None:
        return classification.shared_key
    return asset.shared_key


def resolve_owner_team(asset: Asset) -> str | None:
    classification = asset.classification_record
    if classification is not None:
        return classification.owner_team
    return asset.owner_team
