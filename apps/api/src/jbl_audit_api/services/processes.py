from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

from jbl_audit_api.core.exceptions import NotFoundError, ServiceError
from jbl_audit_api.db.models import (
    Asset,
    AssetClassification,
    ProcessFlow,
    ProcessFlowStep,
    ProcessFlowStepStatus,
    ProcessFlowType,
)
from jbl_audit_api.repositories.processes import ProcessRepository
from jbl_audit_api.schemas.processes import (
    CrawlGraphEdgeRequest,
    CrawlGraphNodeRequest,
    ProcessUpsertRequest,
)

STANDARD_STEP_KEYS = ("sign-in", "dashboard", "launch", "navigate", "attempt", "submit", "review")


@dataclass(slots=True, frozen=True)
class ClassifiedAsset:
    asset: Asset
    classification: AssetClassification


@dataclass(slots=True, frozen=True)
class StepBlueprint:
    step_key: str
    status: ProcessFlowStepStatus
    asset_id: str | None
    locator: str | None
    note: str | None = None


@dataclass(slots=True, frozen=True)
class GraphContext:
    entry_locator: str
    nodes: tuple[CrawlGraphNodeRequest, ...]
    edges: tuple[CrawlGraphEdgeRequest, ...]

    def first_node(self, *page_types: str) -> CrawlGraphNodeRequest | None:
        lowered = {page_type.lower() for page_type in page_types}
        for node in self.nodes:
            if (node.page_type or "").lower() in lowered:
                return node
        return None

    def first_node_matching(self, predicate: callable) -> CrawlGraphNodeRequest | None:
        for node in self.nodes:
            if predicate(node):
                return node
        return None

    def first_edge(self, *transition_types: str) -> CrawlGraphEdgeRequest | None:
        lowered = {transition_type.lower() for transition_type in transition_types}
        for edge in self.edges:
            if edge.transition_type.lower() in lowered:
                return edge
        return None

    def edges_to(self, locator: str) -> list[CrawlGraphEdgeRequest]:
        normalized = normalize_url(locator)
        return [edge for edge in self.edges if normalize_url(edge.to_locator) == normalized]


class ProcessService:
    def __init__(self, repository: ProcessRepository) -> None:
        self.repository = repository

    def upsert_processes(self, payload: ProcessUpsertRequest) -> list[ProcessFlow]:
        run_context = self.repository.get_run_context(payload.run_id)
        if run_context is None:
            raise NotFoundError(f"run '{payload.run_id}' does not exist")

        classified_assets = [
            ClassifiedAsset(asset=asset, classification=asset.classification_record)
            for asset in run_context.assets
            if asset.classification_record is not None
        ]
        if not classified_assets:
            raise ServiceError(f"run '{payload.run_id}' has no classified assets")

        graph = GraphContext(
            entry_locator=payload.crawl_graph.entry_locator,
            nodes=tuple(payload.crawl_graph.nodes),
            edges=tuple(payload.crawl_graph.edges),
        )
        auth_context = (
            payload.auth_context
            if payload.auth_context is not None
            else classified_assets[0].classification.auth_context
        )

        flows = [self._build_default_flow(payload.run_id, auth_context, graph, classified_assets)]

        quiz_assets = [item for item in classified_assets if self._is_quiz_asset(item)]
        if quiz_assets:
            flows.append(self._build_quiz_flow(payload.run_id, auth_context, graph, quiz_assets[0]))

        lti_assets = [item for item in classified_assets if self._is_lti_asset(item)]
        if lti_assets:
            flows.append(self._build_lti_flow(payload.run_id, auth_context, graph, lti_assets[0], classified_assets))

        self.repository.replace_flows_for_run(payload.run_id, flows)
        return self.repository.list_flows_for_run(payload.run_id)

    def _build_default_flow(
        self,
        run_id: str,
        auth_context: dict,
        graph: GraphContext,
        assets: list[ClassifiedAsset],
    ) -> ProcessFlow:
        target_asset = self._select_default_asset(assets)
        biodigital_note = self._biodigital_note(assets, graph)
        steps = [
            self._build_sign_in_step(auth_context, graph),
            self._build_dashboard_step(graph),
            self._build_launch_step(graph, target_asset),
            self._build_navigate_step(graph, target_asset, fallback_asset=target_asset, note=biodigital_note),
            self._build_attempt_step(graph, target_asset),
            self._build_submit_step(graph, target_asset),
            self._build_review_step(graph, target_asset),
        ]
        return self._assemble_flow(
            run_id=run_id,
            flow_type=ProcessFlowType.learner_default,
            flow_name="Learner Default Flow",
            auth_context=auth_context,
            entry_locator=graph.entry_locator,
            steps=steps,
            flow_metadata={
                "source_asset_id": target_asset.asset.asset_id if target_asset else None,
                "missing_steps": [step.step_key for step in steps if step.status == ProcessFlowStepStatus.missing],
            },
        )

    def _build_quiz_flow(
        self,
        run_id: str,
        auth_context: dict,
        graph: GraphContext,
        quiz_asset: ClassifiedAsset,
    ) -> ProcessFlow:
        review_node = self._review_node(graph, quiz_asset)
        submit_edge = self._submit_edge(graph, quiz_asset)
        steps = [
            self._build_sign_in_step(auth_context, graph),
            self._build_dashboard_step(graph),
            self._build_launch_step(graph, quiz_asset),
            self._build_navigate_step(graph, quiz_asset, fallback_asset=quiz_asset),
            self._present_step("attempt", quiz_asset),
            self._build_submit_step(
                graph,
                quiz_asset,
                preferred_locator=(
                    submit_edge.to_locator if submit_edge else review_node.locator if review_node else None
                ),
                preferred_note=submit_edge.note if submit_edge and submit_edge.note else (
                    "Submit inferred from transition to review or result page." if review_node else None
                ),
                default_present=review_node is not None,
            ),
            self._build_review_step(
                graph,
                quiz_asset,
                preferred_node=review_node,
            ),
        ]
        return self._assemble_flow(
            run_id=run_id,
            flow_type=ProcessFlowType.quiz_flow,
            flow_name="Quiz Attempt Flow",
            auth_context=auth_context,
            entry_locator=graph.entry_locator,
            steps=steps,
            flow_metadata={
                "source_asset_id": quiz_asset.asset.asset_id,
                "missing_steps": [step.step_key for step in steps if step.status == ProcessFlowStepStatus.missing],
            },
        )

    def _build_lti_flow(
        self,
        run_id: str,
        auth_context: dict,
        graph: GraphContext,
        lti_asset: ClassifiedAsset,
        assets: list[ClassifiedAsset],
    ) -> ProcessFlow:
        third_party_target = self._biodigital_asset(assets) or self._third_party_asset(assets)
        navigate_note = self._biodigital_note(assets, graph)
        steps = [
            self._build_sign_in_step(auth_context, graph),
            self._build_dashboard_step(graph),
            self._present_step("launch", lti_asset),
            self._build_navigate_step(
                graph,
                third_party_target or lti_asset,
                fallback_asset=lti_asset,
                note=navigate_note,
            ),
            self._missing_step("attempt"),
            self._missing_step("submit"),
            self._build_review_step(graph, third_party_target or lti_asset),
        ]
        return self._assemble_flow(
            run_id=run_id,
            flow_type=ProcessFlowType.lti_flow,
            flow_name="LTI Launch Flow",
            auth_context=auth_context,
            entry_locator=graph.entry_locator,
            steps=steps,
            flow_metadata={
                "source_asset_id": lti_asset.asset.asset_id,
                "third_party_asset_id": third_party_target.asset.asset_id if third_party_target else None,
                "missing_steps": [step.step_key for step in steps if step.status == ProcessFlowStepStatus.missing],
            },
        )

    def _assemble_flow(
        self,
        *,
        run_id: str,
        flow_type: ProcessFlowType,
        flow_name: str,
        auth_context: dict,
        entry_locator: str,
        steps: list[StepBlueprint],
        flow_metadata: dict,
    ) -> ProcessFlow:
        now = datetime.now(UTC)
        flow = ProcessFlow(
            process_flow_id=str(uuid.uuid4()),
            run_id=run_id,
            flow_type=flow_type,
            flow_name=flow_name,
            auth_context=auth_context,
            entry_locator=entry_locator,
            flow_metadata=flow_metadata,
            created_at=now,
            updated_at=now,
        )
        flow.steps = [
            ProcessFlowStep(
                process_flow_step_id=str(uuid.uuid4()),
                process_flow_id=flow.process_flow_id,
                run_id=run_id,
                asset_id=step.asset_id,
                step_order=index,
                step_key=step.step_key,
                step_status=step.status,
                locator=step.locator,
                note=step.note,
                created_at=now,
                updated_at=now,
            )
            for index, step in enumerate(steps, start=1)
        ]
        return flow

    def _build_sign_in_step(self, auth_context: dict, graph: GraphContext) -> StepBlueprint:
        node = graph.first_node("sign-in", "signin", "login")
        if node is not None:
            return StepBlueprint(
                step_key="sign-in",
                status=ProcessFlowStepStatus.present,
                asset_id=node.asset_id,
                locator=node.locator,
                note=node.title,
            )
        if auth_context:
            return StepBlueprint(
                step_key="sign-in",
                status=ProcessFlowStepStatus.present,
                asset_id=None,
                locator=graph.entry_locator,
                note="Sign-in inferred from authenticated crawl context.",
            )
        return self._missing_step("sign-in")

    def _build_dashboard_step(self, graph: GraphContext) -> StepBlueprint:
        node = graph.first_node("dashboard") or graph.first_node_matching(
            lambda item: any(token in normalize_url(item.locator) for token in ("/dashboard", "/my/"))
        )
        if node is None:
            return self._missing_step("dashboard")
        return StepBlueprint(
            step_key="dashboard",
            status=ProcessFlowStepStatus.present,
            asset_id=node.asset_id,
            locator=node.locator,
            note=node.title,
        )

    def _build_launch_step(
        self,
        graph: GraphContext,
        target_asset: ClassifiedAsset | None,
    ) -> StepBlueprint:
        node = graph.first_node("launch") or graph.first_node_matching(
            lambda item: normalize_url(item.locator) == normalize_url(graph.entry_locator)
        )
        if node is not None:
            return StepBlueprint(
                step_key="launch",
                status=ProcessFlowStepStatus.present,
                asset_id=(
                    node.asset_id
                    or (target_asset.asset.asset_id if target_asset and node.asset_id is None else None)
                ),
                locator=node.locator,
                note=node.title,
            )
        if target_asset is not None:
            return self._present_step("launch", target_asset)
        return self._missing_step("launch")

    def _build_navigate_step(
        self,
        graph: GraphContext,
        preferred_asset: ClassifiedAsset | None,
        *,
        fallback_asset: ClassifiedAsset | None,
        note: str | None = None,
    ) -> StepBlueprint:
        if preferred_asset is not None:
            node = self._graph_node_for_asset(graph, preferred_asset)
            if node is not None:
                return StepBlueprint(
                    step_key="navigate",
                    status=ProcessFlowStepStatus.present,
                    asset_id=preferred_asset.asset.asset_id,
                    locator=node.locator,
                    note=note or node.title,
                )
            return StepBlueprint(
                step_key="navigate",
                status=ProcessFlowStepStatus.present,
                asset_id=preferred_asset.asset.asset_id,
                locator=preferred_asset.asset.locator,
                note=note,
            )

        if fallback_asset is not None:
            return StepBlueprint(
                step_key="navigate",
                status=ProcessFlowStepStatus.present,
                asset_id=fallback_asset.asset.asset_id,
                locator=fallback_asset.asset.locator,
                note=note,
            )

        node = graph.first_node("navigate", "content")
        if node is None:
            return self._missing_step("navigate")
        return StepBlueprint(
            step_key="navigate",
            status=ProcessFlowStepStatus.present,
            asset_id=node.asset_id,
            locator=node.locator,
            note=note or node.title,
        )

    def _build_attempt_step(self, graph: GraphContext, target_asset: ClassifiedAsset | None) -> StepBlueprint:
        node = graph.first_node("attempt")
        if node is not None:
            return StepBlueprint(
                step_key="attempt",
                status=ProcessFlowStepStatus.present,
                asset_id=node.asset_id or (target_asset.asset.asset_id if target_asset else None),
                locator=node.locator,
                note=node.title,
            )
        if target_asset is not None and (
            "quiz" in normalize_token(target_asset.asset.asset_type)
            or target_asset.classification.handling_path.value == "manual_only"
        ):
            return self._present_step("attempt", target_asset)
        return self._missing_step("attempt")

    def _build_submit_step(
        self,
        graph: GraphContext,
        target_asset: ClassifiedAsset | None,
        *,
        preferred_locator: str | None = None,
        preferred_note: str | None = None,
        default_present: bool = False,
    ) -> StepBlueprint:
        edge = graph.first_edge("submit")
        if edge is not None:
            return StepBlueprint(
                step_key="submit",
                status=ProcessFlowStepStatus.present,
                asset_id=target_asset.asset.asset_id if target_asset else None,
                locator=edge.to_locator,
                note=edge.note,
            )
        if preferred_locator is not None and default_present:
            return StepBlueprint(
                step_key="submit",
                status=ProcessFlowStepStatus.present,
                asset_id=target_asset.asset.asset_id if target_asset else None,
                locator=preferred_locator,
                note=preferred_note,
            )
        node = graph.first_node("submit")
        if node is not None:
            return StepBlueprint(
                step_key="submit",
                status=ProcessFlowStepStatus.present,
                asset_id=node.asset_id or (target_asset.asset.asset_id if target_asset else None),
                locator=node.locator,
                note=node.title,
            )
        return self._missing_step("submit")

    def _build_review_step(
        self,
        graph: GraphContext,
        target_asset: ClassifiedAsset | None,
        *,
        preferred_node: CrawlGraphNodeRequest | None = None,
    ) -> StepBlueprint:
        node = preferred_node or self._review_node(graph, target_asset)
        if node is not None:
            return StepBlueprint(
                step_key="review",
                status=ProcessFlowStepStatus.present,
                asset_id=node.asset_id or (target_asset.asset.asset_id if target_asset else None),
                locator=node.locator,
                note=node.title or node.metadata.get("note"),
            )
        return self._missing_step("review")

    def _present_step(self, step_key: str, asset: ClassifiedAsset) -> StepBlueprint:
        return StepBlueprint(
            step_key=step_key,
            status=ProcessFlowStepStatus.present,
            asset_id=asset.asset.asset_id,
            locator=asset.asset.locator,
            note=None,
        )

    def _missing_step(self, step_key: str) -> StepBlueprint:
        return StepBlueprint(
            step_key=step_key,
            status=ProcessFlowStepStatus.missing,
            asset_id=None,
            locator=None,
            note=None,
        )

    def _select_default_asset(self, assets: list[ClassifiedAsset]) -> ClassifiedAsset | None:
        preferred = [
            item
            for item in assets
            if not self._is_quiz_asset(item)
            and not self._is_lti_asset(item)
            and item.classification.exclusion_reason is None
        ]
        candidates = preferred or assets
        if not candidates:
            return None
        return sorted(
            candidates,
            key=lambda item: (
                item.classification.layer.value,
                item.asset.locator,
            ),
        )[0]

    def _is_quiz_asset(self, item: ClassifiedAsset) -> bool:
        text = " ".join((item.asset.asset_type, item.asset.locator, item.asset.handling_path)).lower()
        return "quiz" in text or "/mod/quiz/" in item.asset.locator.lower()

    def _is_lti_asset(self, item: ClassifiedAsset) -> bool:
        text = " ".join((item.asset.asset_type, item.asset.locator, item.asset.handling_path)).lower()
        return "lti" in text or "/mod/lti/" in item.asset.locator.lower()

    def _graph_node_for_asset(self, graph: GraphContext, asset: ClassifiedAsset) -> CrawlGraphNodeRequest | None:
        asset_locator = normalize_url(asset.asset.locator)
        for node in graph.nodes:
            if node.asset_id == asset.asset.asset_id or normalize_url(node.locator) == asset_locator:
                return node
        return None

    def _review_node(
        self,
        graph: GraphContext,
        target_asset: ClassifiedAsset | None,
    ) -> CrawlGraphNodeRequest | None:
        explicit = graph.first_node("review", "result", "results")
        if explicit is not None:
            return explicit
        if target_asset is not None:
            target_locator = normalize_url(target_asset.asset.locator)
            for node in graph.nodes:
                normalized = normalize_url(node.locator)
                if any(token in normalized for token in ("/review", "/result", "/results", "/summary")):
                    if node.asset_id == target_asset.asset.asset_id or node.asset_id is None:
                        return node
                    if normalize_url(target_asset.asset.locator) == target_locator:
                        return node
        return None

    def _submit_edge(
        self,
        graph: GraphContext,
        target_asset: ClassifiedAsset | None,
    ) -> CrawlGraphEdgeRequest | None:
        for edge in graph.edges:
            if edge.transition_type.lower() == "submit":
                return edge
        if target_asset is None:
            return None
        target_locator = normalize_url(target_asset.asset.locator)
        for edge in graph.edges:
            if normalize_url(edge.from_locator) == target_locator and any(
                token in normalize_url(edge.to_locator) for token in ("/review", "/result", "/results", "/summary")
            ):
                return edge
        return None

    def _biodigital_asset(self, assets: list[ClassifiedAsset]) -> ClassifiedAsset | None:
        for item in assets:
            if "human.biodigital.com" in (urlsplit(item.asset.locator).hostname or ""):
                return item
        return None

    def _third_party_asset(self, assets: list[ClassifiedAsset]) -> ClassifiedAsset | None:
        for item in assets:
            if item.classification.third_party:
                return item
        return None

    def _biodigital_note(self, assets: list[ClassifiedAsset], graph: GraphContext) -> str | None:
        if self._biodigital_asset(assets) is not None:
            return "BioDigital encountered across a cross-origin boundary; deeper traversal remains evidence-only."
        for node in graph.nodes:
            if "human.biodigital.com" in (urlsplit(node.locator).hostname or ""):
                return "BioDigital encountered across a cross-origin boundary; deeper traversal remains evidence-only."
        return None


def normalize_url(locator: str | None) -> str:
    if not locator:
        return ""
    parts = urlsplit(locator)
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path}?{parts.query}".rstrip("?")


def normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())
