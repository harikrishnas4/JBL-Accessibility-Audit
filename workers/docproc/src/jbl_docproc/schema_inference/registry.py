from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from jbl_docproc.schema_inference.models import InferenceReport, RegistryRecord, WorkbookInventory


class SchemaRegistryRepository(Protocol):
    def lookup(self, workbook_inventory: WorkbookInventory) -> Sequence[RegistryRecord]:
        ...

    def save(self, report: InferenceReport) -> None:
        ...


class NullSchemaRegistryRepository:
    def lookup(self, workbook_inventory: WorkbookInventory) -> Sequence[RegistryRecord]:
        return ()

    def save(self, report: InferenceReport) -> None:
        return None
