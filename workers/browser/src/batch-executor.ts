import { chromium } from "playwright";

import { isTier1ScannableAssetType, type Tier1ScannableAssetType } from "@jbl/contracts";

import type {
  RawFindingRecord,
  ScanAdapterResult,
  ViewportSpec,
} from "./contracts.js";
import { LocalEvidenceStorageAdapter } from "./evidence-store.js";
import { Tier1ScanAdapter } from "./scan-adapter.js";

export interface BatchExecutionAsset {
  asset_id: string;
  asset_type: string;
  locator: string;
  layer?: string;
  shared_key?: string | null;
  owner_team?: string | null;
  handling_path?: string;
}

export interface Tier1BatchExecutionRequest {
  run_id: string;
  assets: BatchExecutionAsset[];
  viewports: ViewportSpec[];
  storage_state_path?: string | null;
  evidence_root_dir?: string;
}

export interface AssetExecutionSummary {
  viewport: string;
  finding_count: number;
  result_counts: Record<string, number>;
  scanned_url: string | null;
}

export interface Tier1BatchAssetSuccess {
  asset_id: string;
  asset_type: Tier1ScannableAssetType;
  findings: RawFindingRecord[];
  scan_metadata: {
    execution_count: number;
    executions: AssetExecutionSummary[];
  };
}

export interface Tier1BatchAssetFailure {
  asset_id: string;
  asset_type: string;
  error: string;
  viewport?: string;
}

export interface Tier1BatchExecutionResponse {
  asset_results: Tier1BatchAssetSuccess[];
  failures: Tier1BatchAssetFailure[];
  summary: {
    attempted_asset_count: number;
    successful_asset_count: number;
    failed_asset_count: number;
    finding_count: number;
  };
}

export interface Tier1ScanAdapterLike {
  scan(request: {
    runId: string;
    assetId: string;
    assetType: Tier1ScannableAssetType;
    locator: string;
    viewport: ViewportSpec;
    storageStatePath?: string;
  }): Promise<ScanAdapterResult>;
}

export async function executeTier1Batch(
  request: Tier1BatchExecutionRequest,
  adapter: Tier1ScanAdapterLike = new Tier1ScanAdapter(
    chromium,
    new LocalEvidenceStorageAdapter(request.evidence_root_dir),
  ),
): Promise<Tier1BatchExecutionResponse> {
  const assetResults: Tier1BatchAssetSuccess[] = [];
  const failures: Tier1BatchAssetFailure[] = [];

  for (const asset of request.assets) {
    if (!isTier1ScannableAssetType(asset.asset_type)) {
      failures.push({
        asset_id: asset.asset_id,
        asset_type: asset.asset_type,
        error: `Unsupported asset type '${asset.asset_type}' for Tier 1 batch execution.`,
      });
      continue;
    }

    const findings: RawFindingRecord[] = [];
    const executions: AssetExecutionSummary[] = [];
    let failed = false;
    for (const viewport of request.viewports) {
      try {
        const result = await adapter.scan({
          runId: request.run_id,
          assetId: asset.asset_id,
          assetType: asset.asset_type,
          locator: asset.locator,
          viewport,
          storageStatePath: request.storage_state_path ?? undefined,
        });
        findings.push(...result.findings);
        executions.push({
          viewport: viewport.name,
          finding_count: result.findings.length,
          result_counts: summarizeResultCounts(result.findings),
          scanned_url: stringOrNull(result.scan_metadata["scanned_url"]),
        });
      } catch (error) {
        failures.push({
          asset_id: asset.asset_id,
          asset_type: asset.asset_type,
          viewport: viewport.name,
          error: error instanceof Error ? error.message : String(error),
        });
        failed = true;
        break;
      }
    }

    if (!failed) {
      assetResults.push({
        asset_id: asset.asset_id,
        asset_type: asset.asset_type,
        findings,
        scan_metadata: {
          execution_count: executions.length,
          executions,
        },
      });
    }
  }

  return {
    asset_results: assetResults,
    failures,
    summary: {
      attempted_asset_count: request.assets.length,
      successful_asset_count: assetResults.length,
      failed_asset_count: failures.length,
      finding_count: assetResults.reduce((total, item) => total + item.findings.length, 0),
    },
  };
}

function summarizeResultCounts(findings: RawFindingRecord[]): Record<string, number> {
  return findings.reduce<Record<string, number>>((accumulator, finding) => {
    accumulator[finding.result_type] = (accumulator[finding.result_type] ?? 0) + 1;
    return accumulator;
  }, {});
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}
