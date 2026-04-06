"""Document processing worker package."""

from jbl_docproc.manifest_parser.models import CanonicalDataset, CanonicalRecord, ManifestParseResult
from jbl_docproc.manifest_parser.parser import ManifestParser
from jbl_docproc.schema_inference.engine import SchemaInferenceEngine
from jbl_docproc.schema_inference.models import (
    CanonicalSchemaType,
    ConfidenceTier,
    InferenceReport,
    SchemaMap,
    WorkbookInventory,
)

__version__ = "0.1.0"

__all__ = [
    "CanonicalSchemaType",
    "CanonicalDataset",
    "CanonicalRecord",
    "ConfidenceTier",
    "InferenceReport",
    "ManifestParseResult",
    "ManifestParser",
    "SchemaInferenceEngine",
    "SchemaMap",
    "WorkbookInventory",
    "__version__",
]
