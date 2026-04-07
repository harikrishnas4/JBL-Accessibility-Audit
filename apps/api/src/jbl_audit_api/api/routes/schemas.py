from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from jbl_audit_api.core.dependencies import get_schema_registry_service
from jbl_audit_api.schemas.schemas import SchemaInferResponse, SchemaRegistryEntryResponse
from jbl_audit_api.services.schemas import SchemaRegistryService

router = APIRouter(tags=["schemas"])


@router.post("/schemas/infer", response_model=SchemaInferResponse)
async def infer_schema(
    workbook: UploadFile = File(...),
    persist_registry: bool = Form(False),
    reuse_registry: bool = Form(True),
    service: SchemaRegistryService = Depends(get_schema_registry_service),
) -> SchemaInferResponse:
    suffix = Path(workbook.filename or "manifest.xlsx").suffix or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = Path(tmp.name)
        tmp.write(await workbook.read())
    try:
        return service.infer_workbook(
            temp_path,
            persist_registry=persist_registry,
            reuse_registry=reuse_registry,
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.get("/schemas/registry", response_model=list[SchemaRegistryEntryResponse])
def list_schema_registry(
    service: SchemaRegistryService = Depends(get_schema_registry_service),
) -> list[SchemaRegistryEntryResponse]:
    return service.list_registry()
