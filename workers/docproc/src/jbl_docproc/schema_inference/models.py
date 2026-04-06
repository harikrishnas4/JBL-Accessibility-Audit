from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CanonicalSchemaType(str, Enum):
    chapter_toc = "chapter_toc"
    asset_type_layout = "asset_type_layout"
    topic_ordering = "topic_ordering"
    embed_registry = "embed_registry"
    label_map = "label_map"
    document_url_map = "document_url_map"
    media_categories = "media_categories"


class ConfidenceTier(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    none = "none"


@dataclass(slots=True, frozen=True)
class HeaderCandidate:
    row_index: int
    raw_values: tuple[str, ...]
    normalized_values: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class SampleRow:
    row_index: int
    values: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class SheetInventory:
    sheet_name: str
    row_count: int
    column_count: int
    header_candidates: tuple[HeaderCandidate, ...]
    sample_rows: tuple[SampleRow, ...]


@dataclass(slots=True, frozen=True)
class WorkbookInventory:
    workbook_path: Path
    sheet_names: tuple[str, ...]
    sheets: tuple[SheetInventory, ...]


@dataclass(slots=True, frozen=True)
class ScoreBreakdown:
    sheet_name_score: float
    header_overlap_score: float
    data_pattern_score: float
    total_score: float


@dataclass(slots=True, frozen=True)
class SchemaAssignment:
    schema_type: CanonicalSchemaType
    sheet_name: str
    confidence: ConfidenceTier
    matched_header_row: int | None
    matched_headers: tuple[str, ...]
    pattern_hits: tuple[str, ...]
    score_breakdown: ScoreBreakdown


@dataclass(slots=True, frozen=True)
class SchemaMap:
    assignments: tuple[SchemaAssignment, ...]
    unmatched_sheets: tuple[str, ...]

    def get(self, schema_type: CanonicalSchemaType) -> SchemaAssignment | None:
        for assignment in self.assignments:
            if assignment.schema_type == schema_type:
                return assignment
        return None


@dataclass(slots=True, frozen=True)
class RegistryRecord:
    record_key: str
    schema_type: CanonicalSchemaType
    metadata: dict[str, str]


@dataclass(slots=True, frozen=True)
class SheetInference:
    sheet_name: str
    schema_type: CanonicalSchemaType | None
    confidence: ConfidenceTier
    matched_header_row: int | None
    matched_headers: tuple[str, ...]
    pattern_hits: tuple[str, ...]
    score_breakdown: ScoreBreakdown


@dataclass(slots=True, frozen=True)
class InferenceReport:
    workbook_inventory: WorkbookInventory
    schema_map: SchemaMap
    sheet_inferences: tuple[SheetInference, ...]
    registry_records: tuple[RegistryRecord, ...]
