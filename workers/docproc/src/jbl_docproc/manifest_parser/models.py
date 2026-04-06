from __future__ import annotations

from dataclasses import dataclass

from jbl_docproc.schema_inference.models import CanonicalSchemaType


@dataclass(slots=True, frozen=True)
class CanonicalRecord:
    row_index: int
    values: dict[str, str]


@dataclass(slots=True, frozen=True)
class CanonicalDataset:
    schema_type: CanonicalSchemaType
    sheet_name: str
    matched_header_row: int | None
    column_mapping: dict[str, str]
    records: tuple[CanonicalRecord, ...]


@dataclass(slots=True, frozen=True)
class ManifestParseResult:
    datasets: tuple[CanonicalDataset, ...]
    fallback_flags: tuple[str, ...]

    @property
    def canonical_types_found(self) -> tuple[CanonicalSchemaType, ...]:
        return tuple(dataset.schema_type for dataset in self.datasets)

    def get(self, schema_type: CanonicalSchemaType) -> CanonicalDataset | None:
        for dataset in self.datasets:
            if dataset.schema_type == schema_type:
                return dataset
        return None
