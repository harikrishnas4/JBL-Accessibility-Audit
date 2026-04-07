from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

from jbl_audit_api.core.config import Settings
from jbl_audit_api.core.exceptions import ServiceError
from jbl_audit_api.schemas.findings import AssetFindingsIngestRequest, RawFindingCreateRequest
from jbl_audit_api.services.findings import FindingService
from jbl_audit_api.services.orchestration_planner import PlannedBatch

TIER1_SUPPORTED_ASSET_TYPES = frozenset({"web_page", "component", "lti_launch", "quiz_page"})


@dataclass(slots=True, frozen=True)
class Tier1AssetExecutionSuccess:
    asset_id: str
    findings: tuple[RawFindingCreateRequest, ...]
    scan_metadata: dict[str, Any]


@dataclass(slots=True, frozen=True)
class Tier1AssetExecutionFailure:
    asset_id: str
    asset_type: str
    error: str
    viewport: str | None = None


@dataclass(slots=True, frozen=True)
class Tier1BatchExecutionResult:
    asset_results: tuple[Tier1AssetExecutionSuccess, ...]
    failures: tuple[Tier1AssetExecutionFailure, ...]
    summary: dict[str, Any]


class Tier1BatchExecutor(Protocol):
    def execute_batch(
        self,
        run_id: str,
        batch: PlannedBatch,
        *,
        session_state_path: str | None = None,
    ) -> Tier1BatchExecutionResult:
        ...


class FindingResultSink(Protocol):
    def ingest(
        self,
        run_id: str,
        asset_id: str,
        findings: list[RawFindingCreateRequest],
        scan_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class FindingServiceResultSink:
    def __init__(self, finding_service: FindingService) -> None:
        self.finding_service = finding_service

    def ingest(
        self,
        run_id: str,
        asset_id: str,
        findings: list[RawFindingCreateRequest],
        scan_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return self.finding_service.ingest_asset_findings(
            run_id,
            asset_id,
            AssetFindingsIngestRequest(findings=findings, scan_metadata=scan_metadata),
        )


class DeterministicNoopTier1BatchExecutor:
    def execute_batch(
        self,
        run_id: str,
        batch: PlannedBatch,
        *,
        session_state_path: str | None = None,
    ) -> Tier1BatchExecutionResult:
        asset_results = []
        for asset in batch.task_contract.get("assets", []):
            asset_id = str(asset.get("asset_id", ""))
            if not asset_id:
                continue
            asset_results.append(
                Tier1AssetExecutionSuccess(
                    asset_id=asset_id,
                    findings=(),
                    scan_metadata={
                        "executor": "deterministic_noop",
                        "viewports": [viewport.get("name") for viewport in batch.viewport_matrix],
                        "session_state_path": session_state_path,
                    },
                ),
            )
        return Tier1BatchExecutionResult(
            asset_results=tuple(asset_results),
            failures=(),
            summary={
                "attempted_asset_count": len(batch.task_contract.get("assets", [])),
                "successful_asset_count": len(asset_results),
                "failed_asset_count": 0,
                "finding_count": 0,
            },
        )


class LocalBrowserWorkerBatchExecutor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def execute_batch(
        self,
        run_id: str,
        batch: PlannedBatch,
        *,
        session_state_path: str | None = None,
    ) -> Tier1BatchExecutionResult:
        if not self.settings.browser_worker_entrypoint.exists():
            raise ServiceError(
                "Browser worker entrypoint is missing. Build the browser worker before dispatching local Tier 1 scans.",
                status_code=500,
            )

        payload = {
            "run_id": run_id,
            "assets": batch.task_contract.get("assets", []),
            "viewports": list(batch.viewport_matrix),
            "storage_state_path": session_state_path,
            "evidence_root_dir": str(self.settings.evidence_root_dir),
        }
        try:
            process = subprocess.run(
                [
                    self.settings.node_executable,
                    str(self.settings.browser_worker_entrypoint),
                ],
                cwd=self.settings.browser_worker_dir,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=self.settings.browser_worker_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ServiceError(
                (
                    "Browser worker batch execution timed out after "
                    f"{self.settings.browser_worker_timeout_seconds} seconds."
                ),
                status_code=500,
            ) from exc
        except OSError as exc:
            raise ServiceError(
                f"Browser worker could not be launched with '{self.settings.node_executable}'.",
                status_code=500,
            ) from exc
        if process.returncode != 0:
            stderr = process.stderr.strip() or process.stdout.strip() or "unknown browser worker failure"
            raise ServiceError(f"Browser worker batch execution failed: {stderr}", status_code=500)

        try:
            response = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise ServiceError(
                "Browser worker returned invalid JSON for Tier 1 batch execution.",
                status_code=500,
            ) from exc

        asset_results = tuple(
            Tier1AssetExecutionSuccess(
                asset_id=str(item["asset_id"]),
                findings=tuple(RawFindingCreateRequest.model_validate(finding) for finding in item.get("findings", [])),
                scan_metadata=dict(item.get("scan_metadata", {})),
            )
            for item in response.get("asset_results", [])
        )
        failures = tuple(
            Tier1AssetExecutionFailure(
                asset_id=str(item.get("asset_id", "")),
                asset_type=str(item.get("asset_type", "")),
                error=str(item.get("error", "unknown error")),
                viewport=item.get("viewport"),
            )
            for item in response.get("failures", [])
        )
        return Tier1BatchExecutionResult(
            asset_results=asset_results,
            failures=failures,
            summary=dict(response.get("summary", {})),
        )


def latest_session_state_path(auth_profiles: list[Any]) -> str | None:
    latest = max(auth_profiles, key=lambda item: item.created_at, default=None)
    if latest is None:
        return None
    return latest.session_state_path


def is_tier1_supported_asset_type(value: str) -> bool:
    return value in TIER1_SUPPORTED_ASSET_TYPES
