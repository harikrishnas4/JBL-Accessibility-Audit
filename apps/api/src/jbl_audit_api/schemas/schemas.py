from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SchemaConfidenceSummaryResponse(BaseModel):
    high: int
    medium: int
    low: int
    none: int


class SchemaMappingResponse(BaseModel):
    schema_type: str
    sheet_name: str
    confidence: str
    matched_header_row: int | None
    matched_headers: list[str]
    pattern_hits: list[str]
    score_breakdown: dict[str, float]


class SchemaInferResponse(BaseModel):
    fingerprint: str
    canonical_types_found: list[str]
    confidence_summary: SchemaConfidenceSummaryResponse
    fallback_flags: list[str]
    mappings: list[SchemaMappingResponse]
    reused_from_registry: bool
    persisted_to_registry: bool


class SchemaRegistryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    schema_registry_entry_id: str
    fingerprint: str
    schema_name: str
    schema_version: str
    canonical_types_found: list[str]
    mappings: list[SchemaMappingResponse]
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
