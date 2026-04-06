from __future__ import annotations

from dataclasses import dataclass
import re

from jbl_docproc.schema_inference.models import CanonicalSchemaType


@dataclass(slots=True, frozen=True)
class SchemaDefinition:
    schema_type: CanonicalSchemaType
    sheet_name_aliases: tuple[str, ...]
    header_aliases: dict[str, tuple[str, ...]]
    data_patterns: dict[str, re.Pattern[str]]


SCHEMA_DEFINITIONS: tuple[SchemaDefinition, ...] = (
    SchemaDefinition(
        schema_type=CanonicalSchemaType.chapter_toc,
        sheet_name_aliases=("chapter_toc", "chapter toc", "toc", "chapters"),
        header_aliases={
            "chapter_id": ("chapter_id", "chapter id", "chapter code"),
            "chapter_title": ("chapter_title", "chapter title", "title"),
            "chapter_order": ("chapter_order", "chapter order", "order", "sequence"),
        },
        data_patterns={
            "chapter_code": re.compile(r"\bch(?:apter)?[-_\s]?\d+\b", re.IGNORECASE),
            "chapter_order": re.compile(r"^\d{1,3}$"),
        },
    ),
    SchemaDefinition(
        schema_type=CanonicalSchemaType.asset_type_layout,
        sheet_name_aliases=("asset_type_layout", "asset layout", "asset types", "layout"),
        header_aliases={
            "asset_type": ("asset_type", "asset type", "content type"),
            "layout": ("layout", "page layout", "template layout"),
            "template": ("template", "template_name", "template name"),
        },
        data_patterns={
            "asset_type": re.compile(r"\b(video|article|quiz|interactive|document)\b", re.IGNORECASE),
            "layout": re.compile(r"\b(grid|carousel|stack|two column|single column)\b", re.IGNORECASE),
        },
    ),
    SchemaDefinition(
        schema_type=CanonicalSchemaType.topic_ordering,
        sheet_name_aliases=("topic_ordering", "topic order", "topic sequence", "ordering"),
        header_aliases={
            "topic_id": ("topic_id", "topic id", "topic code"),
            "topic_name": ("topic_name", "topic name", "topic"),
            "order": ("order", "sort order", "sequence"),
        },
        data_patterns={
            "topic_code": re.compile(r"\btop(?:ic)?[-_\s]?\d+\b", re.IGNORECASE),
            "topic_order": re.compile(r"^\d{1,3}$"),
        },
    ),
    SchemaDefinition(
        schema_type=CanonicalSchemaType.embed_registry,
        sheet_name_aliases=("embed_registry", "embed registry", "embeds", "iframe registry"),
        header_aliases={
            "embed_id": ("embed_id", "embed id", "embed code"),
            "embed_type": ("embed_type", "embed type", "provider"),
            "embed_url": ("embed_url", "embed url", "url", "iframe url"),
        },
        data_patterns={
            "embed_provider": re.compile(r"\b(youtube|vimeo|iframe|wistia)\b", re.IGNORECASE),
            "embed_url": re.compile(r"^https?://", re.IGNORECASE),
        },
    ),
    SchemaDefinition(
        schema_type=CanonicalSchemaType.label_map,
        sheet_name_aliases=("label_map", "label map", "labels", "label mapping"),
        header_aliases={
            "source_label": ("source_label", "source label", "label"),
            "canonical_label": ("canonical_label", "canonical label", "normalized label"),
            "locale": ("locale", "language", "lang"),
        },
        data_patterns={
            "locale": re.compile(r"^[a-z]{2}(?:-[A-Z]{2})?$"),
            "label_slug": re.compile(r"^[a-z0-9]+(?:[_\-\s][a-z0-9]+)+$", re.IGNORECASE),
        },
    ),
    SchemaDefinition(
        schema_type=CanonicalSchemaType.document_url_map,
        sheet_name_aliases=("document_url_map", "document urls", "url map", "documents"),
        header_aliases={
            "document_id": ("document_id", "document id", "doc id"),
            "document_title": ("document_title", "document title", "title"),
            "document_url": ("document_url", "document url", "url"),
        },
        data_patterns={
            "document_url": re.compile(r"^https?://", re.IGNORECASE),
            "document_asset": re.compile(r"\.(?:pdf|docx?|pptx?)$", re.IGNORECASE),
        },
    ),
    SchemaDefinition(
        schema_type=CanonicalSchemaType.media_categories,
        sheet_name_aliases=("media_categories", "media categories", "media", "categories"),
        header_aliases={
            "media_id": ("media_id", "media id", "asset id"),
            "media_type": ("media_type", "media type", "type"),
            "category": ("category", "media category", "group"),
        },
        data_patterns={
            "media_type": re.compile(r"\b(video|audio|image|document|interactive)\b", re.IGNORECASE),
            "category": re.compile(r"\b(core|supplemental|hero|thumbnail|support)\b", re.IGNORECASE),
        },
    ),
)
