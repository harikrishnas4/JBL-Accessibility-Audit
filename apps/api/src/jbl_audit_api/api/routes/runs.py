from __future__ import annotations

from fastapi import APIRouter, Depends, status

from jbl_audit_api.core.dependencies import get_finding_service, get_run_service
from jbl_audit_api.schemas.findings import RunFindingsResponse
from jbl_audit_api.schemas.runs import AuditInputCreateRequest, AuditRunDetailResponse, AuditRunSummaryResponse
from jbl_audit_api.services.findings import FindingService
from jbl_audit_api.services.runs import RunService

router = APIRouter(tags=["runs"])


@router.post("/runs", response_model=AuditRunSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: AuditInputCreateRequest,
    service: RunService = Depends(get_run_service),
) -> AuditRunSummaryResponse:
    return AuditRunSummaryResponse.model_validate(service.create_run(payload))


@router.get("/runs/{id}", response_model=AuditRunDetailResponse)
def get_run(id: str, service: RunService = Depends(get_run_service)) -> AuditRunDetailResponse:
    return AuditRunDetailResponse.model_validate(service.get_run(id))


@router.get("/runs/{id}/findings", response_model=RunFindingsResponse)
def get_run_findings(
    id: str,
    service: FindingService = Depends(get_finding_service),
) -> RunFindingsResponse:
    return RunFindingsResponse.model_validate(service.get_run_findings(id))
