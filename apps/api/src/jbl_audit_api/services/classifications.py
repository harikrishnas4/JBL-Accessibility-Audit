from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit, urlunsplit
import uuid

from jbl_audit_api.db.models import Asset, AssetClassification, AssetHandlingPath, AssetLayer, AssetScopeStatus
from jbl_audit_api.integrations.docproc import CanonicalSchemaType
from jbl_audit_api.repositories.classifications import AssetClassificationRepository
from jbl_audit_api.schemas.classifications import ManifestClassificationContextRequest


DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}
TIMED_MEDIA_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".mov", ".wav", ".webm", ".vtt"}
IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
MANUAL_ONLY_KEYWORDS = (
    "drag",
    "drop",
    "carousel",
    "slider",
    "widget",
    "interactive",
    "timeline",
    "hotspot",
    "simulation",
)
BLOCKED_REASON_PATTERN = re.compile(r"(blocked|cross[-_ ]origin|crossorigin|captcha|auth)", re.IGNORECASE)
FIRST_PARTY_HOSTS = {"cdn-media.jblearning.com", "courses.example.com"}
FIRST_PARTY_SOURCE_SYSTEMS = {"moodle", "cdn-media.jblearning.com"}
THIRD_PARTY_HOSTS = {"human.biodigital.com"}


@dataclass(slots=True, frozen=True)
class ClassificationDecision:
    layer: AssetLayer
    handling_path: AssetHandlingPath
    shared_key: str | None
    owner_team: str | None
    third_party: bool
    third_party_evidence: str | None
    auth_context: dict
    exclusion_reason: str | None


@dataclass(slots=True, frozen=True)
class ManifestIndexes:
    document_by_url: dict[str, dict[str, str]]
    embed_by_url: dict[str, dict[str, str]]
    asset_layout_records: tuple[dict[str, str], ...]
    media_records: tuple[dict[str, str], ...]

    @classmethod
    def from_context(cls, context: ManifestClassificationContextRequest | None) -> "ManifestIndexes":
        document_by_url: dict[str, dict[str, str]] = {}
        embed_by_url: dict[str, dict[str, str]] = {}
        asset_layout_records: list[dict[str, str]] = []
        media_records: list[dict[str, str]] = []
        if context is None:
            return cls({}, {}, (), ())

        for dataset in context.datasets:
            if dataset.schema_type == CanonicalSchemaType.document_url_map:
                for record in dataset.records:
                    locator = normalize_url(record.get("document_url"))
                    if locator:
                        document_by_url[locator] = record
            elif dataset.schema_type == CanonicalSchemaType.embed_registry:
                for record in dataset.records:
                    locator = normalize_url(record.get("embed_url"))
                    if locator:
                        embed_by_url[locator] = record
            elif dataset.schema_type == CanonicalSchemaType.asset_type_layout:
                asset_layout_records.extend(dataset.records)
            elif dataset.schema_type == CanonicalSchemaType.media_categories:
                media_records.extend(dataset.records)

        return cls(
            document_by_url=document_by_url,
            embed_by_url=embed_by_url,
            asset_layout_records=tuple(asset_layout_records),
            media_records=tuple(media_records),
        )


class AssetClassificationService:
    def __init__(self, repository: AssetClassificationRepository) -> None:
        self.repository = repository

    def classify_assets(
        self,
        run_id: str,
        assets: list[Asset],
        manifest_context: ManifestClassificationContextRequest | None,
    ) -> list[AssetClassification]:
        now = datetime.now(UTC)
        manifest_indexes = ManifestIndexes.from_context(manifest_context)
        existing_by_asset_id = {
            classification.asset_id: classification
            for classification in self.repository.list_for_run_by_asset_ids(
                run_id,
                [asset.asset_id for asset in assets],
            )
        }

        classifications_to_save: list[AssetClassification] = []
        for asset in assets:
            decision = self._classify_asset(run_id, asset, manifest_indexes)
            classification = existing_by_asset_id.get(asset.asset_id)
            if classification is None:
                classification = AssetClassification(
                    classification_id=str(uuid.uuid4()),
                    run_id=run_id,
                    asset_id=asset.asset_id,
                    created_at=now,
                )
            classification.layer = decision.layer
            classification.handling_path = decision.handling_path
            classification.shared_key = decision.shared_key
            classification.owner_team = decision.owner_team
            classification.third_party = decision.third_party
            classification.third_party_evidence = decision.third_party_evidence
            classification.auth_context = decision.auth_context
            classification.exclusion_reason = decision.exclusion_reason
            classification.updated_at = now
            classifications_to_save.append(classification)

        self.repository.save(classifications_to_save)
        return self.repository.list_for_run(run_id)

    def _classify_asset(self, run_id: str, asset: Asset, manifest_indexes: ManifestIndexes) -> ClassificationDecision:
        exclusion_reason = asset.scope_reason if asset.scope_status == AssetScopeStatus.out_of_scope else None
        blocked_reason = exclusion_reason if exclusion_reason and BLOCKED_REASON_PATTERN.search(exclusion_reason) else None

        manifest_document = manifest_indexes.document_by_url.get(normalize_url(asset.locator))
        manifest_embed = manifest_indexes.embed_by_url.get(normalize_url(asset.locator))
        manifest_layout = self._match_asset_layout(asset, manifest_indexes.asset_layout_records)
        manifest_media = self._match_media_record(asset, manifest_indexes.media_records)

        if asset.scope_status == AssetScopeStatus.out_of_scope:
            layer = self._infer_excluded_layer(asset)
            shared_key = self._resolve_shared_key(
                asset,
                layer=layer,
                manifest_document=manifest_document,
                manifest_embed=manifest_embed,
                manifest_layout=manifest_layout,
                manifest_media=manifest_media,
            )
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=layer,
                handling_path=AssetHandlingPath.excluded,
                shared_key=shared_key,
                exclusion_reason=blocked_reason or exclusion_reason,
            )

        if manifest_embed is not None:
            shared_key = self._build_manifest_embed_key(asset, manifest_embed)
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.third_party if self._is_third_party_asset(asset) else AssetLayer.component,
                handling_path=AssetHandlingPath.evidence_only
                if self._is_third_party_asset(asset)
                else AssetHandlingPath.automated_plus_manual,
                shared_key=shared_key,
                exclusion_reason=None,
            )

        if manifest_document is not None:
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.document,
                handling_path=AssetHandlingPath.automated_plus_manual,
                shared_key=self._build_manifest_document_key(asset, manifest_document),
                exclusion_reason=None,
            )

        if manifest_media is not None:
            manifest_media_type = normalize_token(manifest_media.get("media_type"))
            if manifest_media_type in {"video", "audio"}:
                return self._build_decision(
                    run_id=run_id,
                    asset=asset,
                    layer=AssetLayer.media,
                    handling_path=AssetHandlingPath.manual_only,
                    shared_key=self._build_manifest_media_key(asset, manifest_media),
                    exclusion_reason=None,
                )
            if manifest_media_type == "document":
                return self._build_decision(
                    run_id=run_id,
                    asset=asset,
                    layer=AssetLayer.document,
                    handling_path=AssetHandlingPath.automated_plus_manual,
                    shared_key=self._build_manifest_media_key(asset, manifest_media),
                    exclusion_reason=None,
                )
            if manifest_media_type == "interactive":
                return self._build_decision(
                    run_id=run_id,
                    asset=asset,
                    layer=AssetLayer.component,
                    handling_path=AssetHandlingPath.manual_only,
                    shared_key=self._build_manifest_media_key(asset, manifest_media),
                    exclusion_reason=None,
                )
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.media,
                handling_path=AssetHandlingPath.automated_plus_manual,
                shared_key=self._build_manifest_media_key(asset, manifest_media),
                exclusion_reason=None,
            )

        if manifest_layout is not None:
            layout_text = " ".join(
                normalize_token(manifest_layout.get(field_name))
                for field_name in ("asset_type", "layout", "template")
            )
            layer = self._infer_layout_layer(asset, layout_text)
            handling_path = (
                AssetHandlingPath.manual_only
                if self._requires_manual_review(asset, layout_text)
                else AssetHandlingPath.automated_plus_manual
            )
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=layer,
                handling_path=handling_path,
                shared_key=self._build_manifest_layout_key(asset, manifest_layout, layer),
                exclusion_reason=None,
            )

        return self._heuristic_decision(run_id, asset, blocked_reason)

    def _heuristic_decision(
        self,
        run_id: str,
        asset: Asset,
        blocked_reason: str | None,
    ) -> ClassificationDecision:
        extension = locator_extension(asset.locator)
        joined_text = " ".join(
            normalize_token(value)
            for value in (
                asset.asset_type,
                asset.source_system,
                asset.locator,
                asset.component_fingerprint.get("template_id", ""),
                asset.component_fingerprint.get("bundle_name", ""),
                asset.component_fingerprint.get("stable_css_selector", ""),
            )
        )

        if self._is_third_party_launch(asset):
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.third_party,
                handling_path=AssetHandlingPath.evidence_only,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.third_party),
                exclusion_reason=blocked_reason,
            )

        if extension in DOCUMENT_EXTENSIONS or "pdf_document" in joined_text:
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.document,
                handling_path=AssetHandlingPath.automated_plus_manual,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.document),
                exclusion_reason=blocked_reason,
            )

        if extension in TIMED_MEDIA_EXTENSIONS or "biodigital" in joined_text:
            layer = AssetLayer.third_party if "biodigital" in joined_text else AssetLayer.media
            handling_path = AssetHandlingPath.evidence_only if layer == AssetLayer.third_party else AssetHandlingPath.manual_only
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=layer,
                handling_path=handling_path,
                shared_key=self._resolve_shared_key(asset, layer=layer),
                exclusion_reason=blocked_reason,
            )

        if any(keyword in joined_text for keyword in MANUAL_ONLY_KEYWORDS):
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.component,
                handling_path=AssetHandlingPath.manual_only,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.component),
                exclusion_reason=blocked_reason,
            )

        if any(fragment in asset.locator for fragment in ("/theme/", "/lib/", ".js", ".css")):
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.platform,
                handling_path=AssetHandlingPath.automated,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.platform),
                exclusion_reason=blocked_reason,
            )

        if "/course/" in asset.locator and "/mod/" not in asset.locator:
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.course_shell,
                handling_path=AssetHandlingPath.automated,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.course_shell),
                exclusion_reason=blocked_reason,
            )

        if extension in IMAGE_EXTENSIONS:
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.media,
                handling_path=AssetHandlingPath.automated_plus_manual,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.media),
                exclusion_reason=blocked_reason,
            )

        if any(fragment in asset.locator for fragment in ("/mod/page/", "/mod/url/", "/mod/quiz/")):
            return self._build_decision(
                run_id=run_id,
                asset=asset,
                layer=AssetLayer.content,
                handling_path=AssetHandlingPath.automated,
                shared_key=self._resolve_shared_key(asset, layer=AssetLayer.content),
                exclusion_reason=blocked_reason,
            )

        return self._build_decision(
            run_id=run_id,
            asset=asset,
            layer=AssetLayer.component,
            handling_path=AssetHandlingPath.automated_plus_manual,
            shared_key=self._resolve_shared_key(asset, layer=AssetLayer.component),
            exclusion_reason=blocked_reason,
        )

    def _build_decision(
        self,
        *,
        run_id: str,
        asset: Asset,
        layer: AssetLayer,
        handling_path: AssetHandlingPath,
        shared_key: str | None,
        exclusion_reason: str | None,
    ) -> ClassificationDecision:
        third_party = layer == AssetLayer.third_party
        return ClassificationDecision(
            layer=layer,
            handling_path=handling_path,
            shared_key=shared_key,
            owner_team=asset.owner_team or default_owner_team(layer),
            third_party=third_party,
            third_party_evidence=f"evidence://third-party/{run_id}/{asset.asset_id}" if third_party else None,
            auth_context=asset.auth_context,
            exclusion_reason=exclusion_reason,
        )

    def _infer_excluded_layer(self, asset: Asset) -> AssetLayer:
        if self._is_third_party_launch(asset) or self._is_third_party_asset(asset):
            return AssetLayer.third_party
        extension = locator_extension(asset.locator)
        if extension in DOCUMENT_EXTENSIONS:
            return AssetLayer.document
        if extension in TIMED_MEDIA_EXTENSIONS or extension in IMAGE_EXTENSIONS:
            return AssetLayer.media
        if any(fragment in asset.locator for fragment in ("/mod/page/", "/mod/url/", "/mod/quiz/")):
            return AssetLayer.content
        return AssetLayer.component

    def _infer_layout_layer(self, asset: Asset, layout_text: str) -> AssetLayer:
        if "document" in layout_text:
            return AssetLayer.document
        if any(keyword in layout_text for keyword in ("video", "audio", "image")):
            return AssetLayer.media
        if "interactive" in layout_text or "widget" in layout_text:
            return AssetLayer.component
        if self._is_third_party_launch(asset):
            return AssetLayer.third_party
        return AssetLayer.content

    def _requires_manual_review(self, asset: Asset, text: str) -> bool:
        return self._is_timed_media(asset) or any(keyword in text for keyword in MANUAL_ONLY_KEYWORDS)

    def _is_timed_media(self, asset: Asset) -> bool:
        return locator_extension(asset.locator) in TIMED_MEDIA_EXTENSIONS

    def _is_third_party_launch(self, asset: Asset) -> bool:
        asset_type = normalize_token(asset.asset_type)
        locator_host = normalize_host(asset.locator)
        return (
            "lti" in asset_type
            or "biodigital" in asset_type
            or locator_host in THIRD_PARTY_HOSTS
        )

    def _is_third_party_asset(self, asset: Asset) -> bool:
        host = normalize_host(asset.locator)
        if asset.source_system in FIRST_PARTY_SOURCE_SYSTEMS:
            return False
        return bool(host and host not in FIRST_PARTY_HOSTS and host != "moodle")

    def _match_asset_layout(self, asset: Asset, records: tuple[dict[str, str], ...]) -> dict[str, str] | None:
        template_id = normalize_token(asset.component_fingerprint.get("template_id"))
        bundle_name = normalize_token(asset.component_fingerprint.get("bundle_name"))
        raw_text = " ".join(
            normalize_token(item)
            for item in (asset.asset_type, asset.locator, template_id, bundle_name)
        )
        for record in records:
            template = normalize_token(record.get("template"))
            if template and (template in template_id or template in bundle_name):
                return record
        for record in records:
            asset_type = normalize_token(record.get("asset_type"))
            if asset_type and asset_type in raw_text:
                return record
        return None

    def _match_media_record(self, asset: Asset, records: tuple[dict[str, str], ...]) -> dict[str, str] | None:
        basename = normalize_token(PurePosixPath(urlsplit(asset.locator).path).name)
        asset_tokens = " ".join(
            normalize_token(item)
            for item in (asset.asset_id, asset.shared_key or "", basename, asset.asset_type)
        )
        inferred_media_type = infer_media_type(asset)
        for record in records:
            media_id = normalize_token(record.get("media_id"))
            if media_id and media_id in asset_tokens:
                return record
        for record in records:
            media_type = normalize_token(record.get("media_type"))
            if media_type and media_type == inferred_media_type:
                return record
        return None

    def _resolve_shared_key(
        self,
        asset: Asset,
        *,
        layer: AssetLayer,
        manifest_document: dict[str, str] | None = None,
        manifest_embed: dict[str, str] | None = None,
        manifest_layout: dict[str, str] | None = None,
        manifest_media: dict[str, str] | None = None,
    ) -> str | None:
        if manifest_document is not None:
            return self._build_manifest_document_key(asset, manifest_document)
        if manifest_embed is not None:
            return self._build_manifest_embed_key(asset, manifest_embed)
        if manifest_media is not None:
            return self._build_manifest_media_key(asset, manifest_media)
        if manifest_layout is not None:
            return self._build_manifest_layout_key(asset, manifest_layout, layer)
        if asset.shared_key:
            return asset.shared_key

        template_id = normalize_token(asset.component_fingerprint.get("template_id"))
        if layer == AssetLayer.component and template_id:
            return f"component:{template_id}"

        host = normalize_host(asset.locator)
        basename = normalize_token(PurePosixPath(urlsplit(asset.locator).path).name)
        if layer == AssetLayer.third_party and host:
            return f"third_party:{host}"
        if layer == AssetLayer.document and basename:
            return f"document:{basename}"
        if layer == AssetLayer.media and basename:
            return f"media:{basename}"

        fingerprint_payload = {
            "layer": layer.value,
            "locator": normalize_url(asset.locator),
            "selector": asset.component_fingerprint.get("stable_css_selector"),
            "signature": asset.component_fingerprint.get("controlled_dom_signature"),
        }
        digest = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        return f"{layer.value}:{digest}"

    def _build_manifest_document_key(self, asset: Asset, record: dict[str, str]) -> str:
        document_id = normalize_token(record.get("document_id"))
        if document_id:
            return f"document:{document_id}"
        return self._resolve_shared_key(asset, layer=AssetLayer.document)

    def _build_manifest_embed_key(self, asset: Asset, record: dict[str, str]) -> str:
        embed_id = normalize_token(record.get("embed_id"))
        if embed_id:
            return f"embed:{embed_id}"
        return self._resolve_shared_key(asset, layer=AssetLayer.third_party)

    def _build_manifest_media_key(self, asset: Asset, record: dict[str, str]) -> str:
        media_id = normalize_token(record.get("media_id"))
        if media_id:
            return f"media:{media_id}"
        return self._resolve_shared_key(asset, layer=AssetLayer.media)

    def _build_manifest_layout_key(self, asset: Asset, record: dict[str, str], layer: AssetLayer) -> str:
        template = normalize_token(record.get("template"))
        if template:
            prefix = "component" if layer == AssetLayer.component else "shared"
            return f"{prefix}:{template}"
        return self._resolve_shared_key(asset, layer=layer)


def normalize_token(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def normalize_url(value: str | None) -> str:
    if not value:
        return ""
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    return urlunsplit((scheme, netloc, parts.path, parts.query, ""))


def normalize_host(value: str | None) -> str:
    normalized = normalize_url(value)
    if not normalized:
        return ""
    return urlsplit(normalized).hostname or ""


def locator_extension(locator: str) -> str:
    path = PurePosixPath(urlsplit(locator).path)
    return path.suffix.lower()


def infer_media_type(asset: Asset) -> str:
    extension = locator_extension(asset.locator)
    if extension in TIMED_MEDIA_EXTENSIONS:
        return "video" if extension in {".mp4", ".mov", ".webm", ".vtt"} else "audio"
    if extension in DOCUMENT_EXTENSIONS:
        return "document"
    if extension in IMAGE_EXTENSIONS:
        return "image"
    if "interactive" in normalize_token(asset.asset_type):
        return "interactive"
    return ""


def default_owner_team(layer: AssetLayer) -> str:
    if layer in {AssetLayer.platform, AssetLayer.course_shell}:
        return "platform"
    if layer == AssetLayer.third_party:
        return "vendor"
    return "content"
