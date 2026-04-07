import { createRequire } from "node:module";

export type CanonicalAssetType =
  | "web_page"
  | "component"
  | "document_pdf"
  | "media_video"
  | "third_party_embed"
  | "lti_launch"
  | "quiz_page";

export type Tier1ScannableAssetType = "web_page" | "component" | "lti_launch" | "quiz_page";

export type LegacyCrawlerAssetType = "course_page" | "course_quiz" | "course_lti" | "course_link";

export interface LegacyCrawlerAssetTypeMappingEntry {
  canonical_asset_type: CanonicalAssetType;
  rationale: string;
}

interface AssetTaxonomyDocument {
  canonical_asset_types: readonly CanonicalAssetType[];
  tier1_scannable_asset_types: readonly Tier1ScannableAssetType[];
  legacy_crawler_asset_type_mapping: Record<LegacyCrawlerAssetType, LegacyCrawlerAssetTypeMappingEntry>;
}

const require = createRequire(import.meta.url);
const assetTaxonomy = require("../asset-taxonomy.json") as AssetTaxonomyDocument;

export const CANONICAL_ASSET_TYPES = assetTaxonomy.canonical_asset_types;
export const TIER1_SCANNABLE_ASSET_TYPES = assetTaxonomy.tier1_scannable_asset_types;
export const LEGACY_CRAWLER_ASSET_TYPE_MAPPING = assetTaxonomy.legacy_crawler_asset_type_mapping;

const CANONICAL_ASSET_TYPE_SET = new Set<string>(CANONICAL_ASSET_TYPES);
const TIER1_SCANNABLE_ASSET_TYPE_SET = new Set<string>(TIER1_SCANNABLE_ASSET_TYPES);

export function isCanonicalAssetType(value: string): value is CanonicalAssetType {
  return CANONICAL_ASSET_TYPE_SET.has(value);
}

export function isTier1ScannableAssetType(value: string): value is Tier1ScannableAssetType {
  return TIER1_SCANNABLE_ASSET_TYPE_SET.has(value);
}

export interface HealthResponse {
  status: "ok";
  service: string;
  environment: string;
}
