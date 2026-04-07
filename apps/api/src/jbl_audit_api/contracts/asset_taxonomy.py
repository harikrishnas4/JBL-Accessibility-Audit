from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def _taxonomy_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        candidate = parent / "packages" / "contracts" / "asset-taxonomy.json"
        if candidate.exists():
            return candidate
    raise RuntimeError("Unable to locate packages/contracts/asset-taxonomy.json")


@lru_cache(maxsize=1)
def _load_taxonomy_document() -> dict[str, object]:
    return json.loads(_taxonomy_path().read_text(encoding="utf-8"))


def _load_canonical_asset_types() -> tuple[str, ...]:
    values = _load_taxonomy_document().get("canonical_asset_types", [])
    if not isinstance(values, list):
        raise RuntimeError("canonical_asset_types must be a list in packages/contracts/asset-taxonomy.json")
    return tuple(str(value) for value in values)


CANONICAL_ASSET_TYPES: tuple[str, ...] = _load_canonical_asset_types()
CANONICAL_ASSET_TYPE_SET: frozenset[str] = frozenset(CANONICAL_ASSET_TYPES)


def validate_canonical_asset_type(value: str) -> str:
    if value not in CANONICAL_ASSET_TYPE_SET:
        allowed = ", ".join(CANONICAL_ASSET_TYPES)
        raise ValueError(f"asset_type must be one of: {allowed}")
    return value
