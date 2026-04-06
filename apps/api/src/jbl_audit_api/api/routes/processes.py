from __future__ import annotations

from fastapi import APIRouter, Depends, status

from jbl_audit_api.core.dependencies import get_process_service
from jbl_audit_api.schemas.processes import ProcessFlowResponse, ProcessUpsertRequest, ProcessUpsertResponse
from jbl_audit_api.services.processes import ProcessService

router = APIRouter(tags=["processes"])


@router.post("/processes/upsert", response_model=ProcessUpsertResponse, status_code=status.HTTP_201_CREATED)
def upsert_processes(
    payload: ProcessUpsertRequest,
    service: ProcessService = Depends(get_process_service),
) -> ProcessUpsertResponse:
    flows = service.upsert_processes(payload)
    return ProcessUpsertResponse(
        run_id=payload.run_id,
        flows=[ProcessFlowResponse.model_validate(flow) for flow in flows],
    )
