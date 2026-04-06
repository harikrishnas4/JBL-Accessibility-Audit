import { AxeBuilder } from "@axe-core/playwright";
import {
  chromium,
  type Browser,
  type BrowserContext,
  type BrowserType,
  type Cookie,
  type Page,
} from "playwright";

import type {
  RawFindingRecord,
  ScanAdapterRequest,
  ScanAdapterResult,
  ScanAssetType,
} from "./contracts.js";
import { LocalEvidenceStorageAdapter, type EvidenceStorageAdapter, type StoredArtifactReference } from "./evidence-store.js";

const SUPPORTED_SCAN_ASSET_TYPES = new Set<ScanAssetType>(["web_page", "component", "lti_launch", "quiz_page"]);

export interface AxeNodeLike {
  target?: string[];
  html?: string;
  failureSummary?: string;
  any?: unknown[];
  all?: unknown[];
  none?: unknown[];
}

export interface AxeRuleLike {
  id: string;
  impact?: string | null;
  description?: string;
  help: string;
  helpUrl?: string;
  tags: string[];
  nodes?: AxeNodeLike[];
}

export interface AxeResultsLike {
  violations: AxeRuleLike[];
  passes: AxeRuleLike[];
  incomplete: AxeRuleLike[];
  inapplicable: AxeRuleLike[];
  url?: string;
}

export interface FlattenedFindingSeed {
  result_type: RawFindingRecord["result_type"];
  rule_id: string;
  wcag_sc: string | null;
  severity: string | null;
  message: string;
  target_fingerprint: string | null;
  raw_payload: Record<string, unknown>;
  observed_at: string;
  is_failure: boolean;
  is_representative_pass: boolean;
}

export interface AxeAnalyzerLike {
  analyze(page: Page): Promise<AxeResultsLike>;
}

class PlaywrightAxeAnalyzer implements AxeAnalyzerLike {
  async analyze(page: Page): Promise<AxeResultsLike> {
    return (await new AxeBuilder({ page }).analyze()) as AxeResultsLike;
  }
}

export function assertSupportedScanAssetType(assetType: string): asserts assetType is ScanAssetType {
  if (!SUPPORTED_SCAN_ASSET_TYPES.has(assetType as ScanAssetType)) {
    throw new Error(`Unsupported asset type '${assetType}' for Tier 1 scan adapter.`);
  }
}

export function extractWcagSuccessCriterion(tags: string[]): string | null {
  const match = tags.find((tag) => /^wcag\d{3,4}$/i.test(tag));
  if (!match) {
    return null;
  }
  const digits = match.replace(/^wcag/i, "");
  return digits.split("").join(".");
}

export function flattenAxeResults(results: AxeResultsLike, observedAt: string = new Date().toISOString()): FlattenedFindingSeed[] {
  const flattened: FlattenedFindingSeed[] = [];
  let representativePassAssigned = false;

  const appendSeeds = (
    resultType: FlattenedFindingSeed["result_type"],
    rule: AxeRuleLike,
  ) => {
    const nodes = resultType === "inapplicable" ? [] : (rule.nodes ?? []);
    if (nodes.length === 0) {
      flattened.push({
        result_type: resultType,
        rule_id: rule.id,
        wcag_sc: extractWcagSuccessCriterion(rule.tags),
        severity: rule.impact ?? null,
        message: rule.description ?? rule.help,
        target_fingerprint: null,
        raw_payload: { rule },
        observed_at: observedAt,
        is_failure: resultType === "violation",
        is_representative_pass: false,
      });
      return;
    }

    for (const node of nodes) {
      const isRepresentativePass = resultType === "pass" && !representativePassAssigned;
      if (isRepresentativePass) {
        representativePassAssigned = true;
      }
      flattened.push({
        result_type: resultType,
        rule_id: rule.id,
        wcag_sc: extractWcagSuccessCriterion(rule.tags),
        severity: rule.impact ?? null,
        message: normalizeMessage(rule, node),
        target_fingerprint: buildTargetFingerprint(node.target),
        raw_payload: {
          rule: {
            id: rule.id,
            impact: rule.impact ?? null,
            description: rule.description ?? null,
            help: rule.help,
            helpUrl: rule.helpUrl ?? null,
            tags: rule.tags,
          },
          node,
        },
        observed_at: observedAt,
        is_failure: resultType === "violation",
        is_representative_pass: isRepresentativePass,
      });
    }
  };

  for (const rule of results.violations) {
    appendSeeds("violation", rule);
  }
  for (const rule of results.passes) {
    appendSeeds("pass", rule);
  }
  for (const rule of results.incomplete) {
    appendSeeds("incomplete", rule);
  }
  for (const rule of results.inapplicable) {
    appendSeeds("inapplicable", rule);
  }

  return flattened;
}

export class Tier1ScanAdapter {
  constructor(
    private readonly browserType: BrowserType<Browser> = chromium,
    private readonly evidenceStorage: EvidenceStorageAdapter = new LocalEvidenceStorageAdapter(),
    private readonly analyzer: AxeAnalyzerLike = new PlaywrightAxeAnalyzer(),
  ) {}

  async scan(request: ScanAdapterRequest): Promise<ScanAdapterResult> {
    assertSupportedScanAssetType(request.assetType);

    const browser = await this.browserType.launch({ headless: true });
    const contextOptions = request.storageStatePath
      ? {
          storageState: request.storageStatePath,
          viewport: { width: request.viewport.width, height: request.viewport.height },
        }
      : {
          viewport: { width: request.viewport.width, height: request.viewport.height },
        };
    const context = await browser.newContext(contextOptions);

    try {
      if (request.cookies?.length) {
        await context.addCookies(request.cookies);
      }
      await context.tracing.start({ screenshots: true, snapshots: true });

      const page = await context.newPage();
      await page.goto(request.locator, { waitUntil: "load" });
      const results = await this.analyzer.analyze(page);
      const domSnapshot = await this.evidenceStorage.writeDomSnapshot(
        request.runId,
        request.assetId,
        "dom-snapshot",
        await page.content(),
        {
          asset_type: request.assetType,
          locator: page.url(),
          viewport: request.viewport.name,
        },
      );

      const flattenedFindings = flattenAxeResults(results);
      const findings = await this.attachEvidenceArtifacts(
        request,
        flattenedFindings,
        page,
        context,
        domSnapshot,
      );

      return {
        run_id: request.runId,
        asset_id: request.assetId,
        asset_type: request.assetType,
        viewport: request.viewport,
        findings,
        scan_metadata: {
          scanned_url: page.url(),
          result_counts: summarizeResults(findings),
        },
      };
    } finally {
      await context.close();
      await browser.close();
    }
  }

  private async attachEvidenceArtifacts(
    request: ScanAdapterRequest,
    flattenedFindings: FlattenedFindingSeed[],
    page: Page,
    context: BrowserContext,
    domSnapshot: StoredArtifactReference,
  ): Promise<RawFindingRecord[]> {
    const failureFindings = flattenedFindings.filter((item) => item.is_failure);
    const representativePass = flattenedFindings.find((item) => item.is_representative_pass) ?? null;
    const failureTrace = failureFindings.length > 0 ? await this.captureTrace(request, context) : null;
    if (failureFindings.length === 0) {
      await context.tracing.stop();
    }

    const representativePassScreenshot =
      representativePass === null
        ? null
        : await this.evidenceStorage.writeScreenshot(
            request.runId,
            request.assetId,
            page,
            "representative-pass",
            {
              asset_type: request.assetType,
              viewport: request.viewport.name,
              result_type: "pass",
            },
          );

    const findings: RawFindingRecord[] = [];
    for (let index = 0; index < flattenedFindings.length; index += 1) {
      const seed = flattenedFindings[index];
      const evidenceArtifacts = [];
      if (seed.is_failure) {
        const screenshot = await this.evidenceStorage.writeScreenshot(
          request.runId,
          request.assetId,
          page,
          `failure-${index + 1}-${seed.rule_id}`,
          {
            asset_type: request.assetType,
            viewport: request.viewport.name,
            result_type: seed.result_type,
            target_fingerprint: seed.target_fingerprint,
          },
        );
        evidenceArtifacts.push(stripAbsolutePath(screenshot), stripAbsolutePath(domSnapshot));
        if (failureTrace) {
          evidenceArtifacts.push(stripAbsolutePath(failureTrace));
        }
      } else if (seed.is_representative_pass && representativePassScreenshot) {
        evidenceArtifacts.push(
          stripAbsolutePath(representativePassScreenshot),
          stripAbsolutePath(domSnapshot),
        );
      }

      findings.push({
        result_type: seed.result_type,
        rule_id: seed.rule_id,
        wcag_sc: seed.wcag_sc,
        resolution_state: "new",
        severity: seed.severity,
        message: seed.message,
        target_fingerprint: seed.target_fingerprint,
        raw_payload: seed.raw_payload,
        observed_at: seed.observed_at,
        evidence_artifacts: evidenceArtifacts,
      });
    }

    return findings;
  }

  private async captureTrace(
    request: ScanAdapterRequest,
    context: BrowserContext,
  ): Promise<StoredArtifactReference> {
    const destination = await this.evidenceStorage.prepareArtifactDestination(
      request.runId,
      request.assetId,
      "trace",
      "failure-trace",
      "zip",
      {
        asset_type: request.assetType,
        viewport: request.viewport.name,
      },
    );
    await context.tracing.stop({ path: destination.absolute_path });
    return destination;
  }
}

function normalizeMessage(rule: AxeRuleLike, node: AxeNodeLike): string {
  const summaryLine = node.failureSummary?.split("\n").map((value) => value.trim()).find(Boolean);
  return summaryLine ?? rule.description ?? rule.help;
}

function buildTargetFingerprint(targets: string[] | undefined): string | null {
  if (!targets || targets.length === 0) {
    return null;
  }
  return targets.map((value) => value.trim()).filter(Boolean).join(" | ") || null;
}

function stripAbsolutePath(artifact: StoredArtifactReference) {
  const { absolute_path: _, ...record } = artifact;
  return record;
}

function summarizeResults(findings: RawFindingRecord[]) {
  return findings.reduce<Record<string, number>>((accumulator, finding) => {
    accumulator[finding.result_type] = (accumulator[finding.result_type] ?? 0) + 1;
    return accumulator;
  }, {});
}

export function withCookies(request: ScanAdapterRequest, cookies: Cookie[]): ScanAdapterRequest {
  return {
    ...request,
    cookies,
  };
}
