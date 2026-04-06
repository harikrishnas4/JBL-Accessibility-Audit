from __future__ import annotations

from pathlib import Path
import sys


MONOREPO_ROOT = Path(__file__).resolve().parents[5]
DOCPROC_SRC = MONOREPO_ROOT / "workers" / "docproc" / "src"

if str(DOCPROC_SRC) not in sys.path:
    sys.path.insert(0, str(DOCPROC_SRC))

from jbl_docproc.manifest_parser.models import ManifestParseResult  # noqa: E402
from jbl_docproc.manifest_parser.parser import ManifestParser  # noqa: E402
from jbl_docproc.schema_inference.engine import SchemaInferenceEngine  # noqa: E402
from jbl_docproc.schema_inference.models import (  # noqa: E402
    CanonicalSchemaType,
    ConfidenceTier,
    InferenceReport,
    SchemaAssignment,
    SchemaMap,
    ScoreBreakdown,
    WorkbookInventory,
)

__all__ = [
    "CanonicalSchemaType",
    "ConfidenceTier",
    "InferenceReport",
    "ManifestParseResult",
    "ManifestParser",
    "SchemaAssignment",
    "SchemaInferenceEngine",
    "SchemaMap",
    "ScoreBreakdown",
    "WorkbookInventory",
]
