from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import uuid
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from jbl_audit_api.core.exceptions import ServiceError
from jbl_audit_api.integrations.docproc import (
    CanonicalSchemaType,
    ConfidenceTier,
    ManifestParseResult,
    ManifestParser,
    SchemaAssignment,
    SchemaInferenceEngine,
    SchemaMap,
    WorkbookInventory,
)
from jbl_audit_api.repositories.schemas import SchemaRegistryRepository
from jbl_audit_api.schemas.schemas import (
    SchemaConfidenceSummaryResponse,
    SchemaInferResponse,
    SchemaMappingResponse,
    SchemaRegistryEntryResponse,
)


class SchemaRegistryService:
    def __init__(self, repository: SchemaRegistryRepository) -> None:
        self.repository = repository
        self.engine = SchemaInferenceEngine()
        self.parser = ManifestParser()

    def infer_workbook(
        self,
        workbook_path: Path,
        *,
        persist_registry: bool,
        reuse_registry: bool,
    ) -> SchemaInferResponse:
        inventory = self._inventory_workbook(workbook_path)
        fingerprint = self._fingerprint_inventory(inventory)

        reused_from_registry = False
        persisted_to_registry = False
        record = self.repository.get_by_fingerprint(fingerprint) if reuse_registry else None
        if record is not None:
            schema_map = self._deserialize_schema_map(record.schema_payload["schema_map"])
            reused_from_registry = True
        else:
            schema_map, _ = self._infer_schema_map(workbook_path)

        parse_result = self._parse_manifest(workbook_path, schema_map)
        if persist_registry:
            self._persist_schema_map(fingerprint=fingerprint, schema_map=schema_map, parse_result=parse_result)
            persisted_to_registry = True

        return SchemaInferResponse(
            fingerprint=fingerprint,
            canonical_types_found=[schema_type.value for schema_type in parse_result.canonical_types_found],
            confidence_summary=self._build_confidence_summary(schema_map),
            fallback_flags=list(parse_result.fallback_flags),
            mappings=[self._to_mapping_response(assignment) for assignment in schema_map.assignments],
            reused_from_registry=reused_from_registry,
            persisted_to_registry=persisted_to_registry,
        )

    def list_registry(self) -> list[SchemaRegistryEntryResponse]:
        entries = self.repository.list_entries()
        return [
            SchemaRegistryEntryResponse(
                schema_registry_entry_id=entry.schema_registry_entry_id,
                fingerprint=entry.fingerprint or "",
                schema_name=entry.schema_name,
                schema_version=entry.schema_version,
                canonical_types_found=entry.schema_payload.get("canonical_types_found", []),
                mappings=[
                    SchemaMappingResponse(**mapping)
                    for mapping in entry.schema_payload.get("mappings", [])
                ],
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                metadata=entry.schema_payload,
            )
            for entry in entries
            if entry.fingerprint
        ]

    def _inventory_workbook(self, workbook_path: Path) -> WorkbookInventory:
        try:
            return self.engine.inventory_workbook(workbook_path)
        except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
            raise ServiceError("invalid workbook input") from exc

    def _infer_schema_map(self, workbook_path: Path) -> tuple[SchemaMap, object]:
        try:
            return self.engine.infer(workbook_path)
        except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
            raise ServiceError("invalid workbook input") from exc

    def _parse_manifest(self, workbook_path: Path, schema_map: SchemaMap) -> ManifestParseResult:
        try:
            return self.parser.parse(workbook_path, schema_map)
        except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
            raise ServiceError("invalid workbook input") from exc

    def _fingerprint_inventory(self, inventory: WorkbookInventory) -> str:
        payload = {
            "sheets": [
                {
                    "sheet_name": sheet.sheet_name,
                    "column_count": sheet.column_count,
                    "headers": [candidate.normalized_values for candidate in sheet.header_candidates],
                }
                for sheet in inventory.sheets
            ]
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _persist_schema_map(
        self,
        *,
        fingerprint: str,
        schema_map: SchemaMap,
        parse_result: ManifestParseResult | None,
    ) -> None:
        now = datetime.now(UTC)
        payload = {
            "schema_registry_entry_id": str(uuid.uuid4()),
            "fingerprint": fingerprint,
            "schema_map": self._serialize_schema_map(schema_map),
            "canonical_types_found": [
                assignment.schema_type.value for assignment in schema_map.assignments
            ],
            "fallback_flags": list(parse_result.fallback_flags) if parse_result else [],
            "mappings": [self._mapping_payload(assignment) for assignment in schema_map.assignments],
            "confidence_summary": self._build_confidence_summary(schema_map).model_dump(),
        }
        self.repository.upsert(
            fingerprint=fingerprint,
            schema_name="manifest_schema_map",
            schema_version="v1",
            schema_payload=payload,
            now=now,
        )

    def _serialize_schema_map(self, schema_map: SchemaMap) -> dict:
        return {
            "assignments": [self._assignment_payload(assignment) for assignment in schema_map.assignments],
            "unmatched_sheets": list(schema_map.unmatched_sheets),
        }

    def _deserialize_schema_map(self, payload: dict) -> SchemaMap:
        return SchemaMap(
            assignments=tuple(
                SchemaAssignment(
                    schema_type=CanonicalSchemaType(item["schema_type"]),
                    sheet_name=item["sheet_name"],
                    confidence=ConfidenceTier(item["confidence"]),
                    matched_header_row=item["matched_header_row"],
                    matched_headers=tuple(item["matched_headers"]),
                    pattern_hits=tuple(item["pattern_hits"]),
                    score_breakdown=self._deserialize_score_breakdown(item["score_breakdown"]),
                )
                for item in payload["assignments"]
            ),
            unmatched_sheets=tuple(payload["unmatched_sheets"]),
        )

    def _deserialize_score_breakdown(self, payload: dict) -> object:
        from jbl_audit_api.integrations.docproc import ScoreBreakdown

        return ScoreBreakdown(
            sheet_name_score=payload["sheet_name_score"],
            header_overlap_score=payload["header_overlap_score"],
            data_pattern_score=payload["data_pattern_score"],
            total_score=payload["total_score"],
        )

    def _assignment_payload(self, assignment: SchemaAssignment) -> dict:
        return {
            "schema_type": assignment.schema_type.value,
            "sheet_name": assignment.sheet_name,
            "confidence": assignment.confidence.value,
            "matched_header_row": assignment.matched_header_row,
            "matched_headers": list(assignment.matched_headers),
            "pattern_hits": list(assignment.pattern_hits),
            "score_breakdown": {
                "sheet_name_score": assignment.score_breakdown.sheet_name_score,
                "header_overlap_score": assignment.score_breakdown.header_overlap_score,
                "data_pattern_score": assignment.score_breakdown.data_pattern_score,
                "total_score": assignment.score_breakdown.total_score,
            },
        }

    def _mapping_payload(self, assignment: SchemaAssignment) -> dict:
        return self._to_mapping_response(assignment).model_dump()

    def _to_mapping_response(self, assignment: SchemaAssignment) -> SchemaMappingResponse:
        return SchemaMappingResponse(
            schema_type=assignment.schema_type.value,
            sheet_name=assignment.sheet_name,
            confidence=assignment.confidence.value,
            matched_header_row=assignment.matched_header_row,
            matched_headers=list(assignment.matched_headers),
            pattern_hits=list(assignment.pattern_hits),
            score_breakdown={
                "sheet_name_score": assignment.score_breakdown.sheet_name_score,
                "header_overlap_score": assignment.score_breakdown.header_overlap_score,
                "data_pattern_score": assignment.score_breakdown.data_pattern_score,
                "total_score": assignment.score_breakdown.total_score,
            },
        )

    def _build_confidence_summary(self, schema_map: SchemaMap) -> SchemaConfidenceSummaryResponse:
        counts = {
            ConfidenceTier.high.value: 0,
            ConfidenceTier.medium.value: 0,
            ConfidenceTier.low.value: 0,
            ConfidenceTier.none.value: 0,
        }
        for assignment in schema_map.assignments:
            counts[assignment.confidence.value] += 1
        counts[ConfidenceTier.none.value] = len(CanonicalSchemaType) - len(schema_map.assignments)
        return SchemaConfidenceSummaryResponse(
            high=counts[ConfidenceTier.high.value],
            medium=counts[ConfidenceTier.medium.value],
            low=counts[ConfidenceTier.low.value],
            none=counts[ConfidenceTier.none.value],
        )
