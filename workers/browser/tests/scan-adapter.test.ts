import assert from "node:assert/strict";
import { access, mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { chromium } from "playwright";

import { LocalEvidenceStorageAdapter } from "../src/evidence-store.js";
import {
  assertSupportedScanAssetType,
  extractWcagSuccessCriterion,
  flattenAxeResults,
  Tier1ScanAdapter,
  type AxeResultsLike,
} from "../src/scan-adapter.js";

function run(name: string, fn: () => Promise<void> | void): Promise<void> {
  return Promise.resolve(fn()).then(() => {
    console.log(`ok - ${name}`);
  });
}

const fixturesDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "tests", "fixtures");

await run("Tier1ScanAdapter scans a fixture page and captures local evidence artifacts", async () => {
  const evidenceDirectory = await mkdtemp(path.join(os.tmpdir(), "jbl-scan-tier1-"));
  try {
    const adapter = new Tier1ScanAdapter(
      chromium,
      new LocalEvidenceStorageAdapter(evidenceDirectory, "var/evidence"),
    );
    const result = await adapter.scan({
      runId: "run-tier1",
      assetId: "asset-web-page",
      assetType: "web_page",
      locator: pathToFileURL(path.join(fixturesDir, "scan-web-page.html")).toString(),
      viewport: {
        name: "desktop",
        width: 1280,
        height: 800,
      },
    });

    assert.equal(result.asset_type, "web_page");
    assert.ok(result.findings.some((finding) => finding.result_type === "violation"));
    assert.ok(result.findings.some((finding) => finding.result_type === "pass"));
    assert.ok(result.findings.some((finding) => finding.result_type === "inapplicable"));

    const violation = result.findings.find((finding) => finding.result_type === "violation");
    assert.ok(violation);
    assert.deepEqual(
      new Set(violation?.evidence_artifacts.map((artifact) => artifact.artifact_type)),
      new Set(["screenshot", "trace", "dom_snapshot_reference"]),
    );

    const representativePass = result.findings.find(
      (finding) => finding.result_type === "pass" && finding.evidence_artifacts.length > 0,
    );
    assert.ok(representativePass);
    assert.deepEqual(
      new Set(representativePass?.evidence_artifacts.map((artifact) => artifact.artifact_type)),
      new Set(["screenshot", "dom_snapshot_reference"]),
    );

    const uniqueArtifactPaths = new Set(
      result.findings.flatMap((finding) => finding.evidence_artifacts.map((artifact) => artifact.storage_path)),
    );
    for (const storagePath of uniqueArtifactPaths) {
      const absolutePath = path.join(
        evidenceDirectory,
        storagePath.replace(/^var[\\/]+evidence[\\/]+/i, "").replace(/^var\/evidence\//, ""),
      );
      await access(absolutePath);
    }
  } finally {
    await rm(evidenceDirectory, { recursive: true, force: true });
  }
});

await run("flattenAxeResults preserves incomplete and inapplicable outcomes", () => {
  const observedAt = "2026-04-06T12:00:00.000Z";
  const results: AxeResultsLike = {
    violations: [],
    passes: [],
    incomplete: [
      {
        id: "color-contrast",
        impact: "serious",
        description: "Color contrast must be sufficient.",
        help: "Elements must meet minimum color contrast ratio thresholds",
        tags: ["wcag143", "wcag2aa"],
        nodes: [
          {
            target: [".button-cta"],
            failureSummary: "Contrast could not be verified automatically.",
          },
        ],
      },
    ],
    inapplicable: [
      {
        id: "video-caption",
        impact: null,
        description: "Video captions are not applicable.",
        help: "Videos must have captions",
        tags: ["wcag122", "wcag2a"],
      },
    ],
  };

  const flattened = flattenAxeResults(results, observedAt);

  assert.equal(flattened.length, 2);
  assert.deepEqual(
    flattened.map((finding) => finding.result_type),
    ["incomplete", "inapplicable"],
  );
  assert.equal(flattened[0]?.wcag_sc, "1.4.3");
  assert.equal(flattened[1]?.wcag_sc, "1.2.2");
  assert.equal(flattened[0]?.observed_at, observedAt);
});

await run("supported scan asset types are enforced explicitly", () => {
  assert.doesNotThrow(() => assertSupportedScanAssetType("web_page"));
  assert.doesNotThrow(() => assertSupportedScanAssetType("component"));
  assert.doesNotThrow(() => assertSupportedScanAssetType("lti_launch"));
  assert.doesNotThrow(() => assertSupportedScanAssetType("quiz_page"));
  assert.throws(() => assertSupportedScanAssetType("document_pdf"), /Unsupported asset type/);
  assert.throws(() => assertSupportedScanAssetType("media_video"), /Unsupported asset type/);
  assert.throws(() => assertSupportedScanAssetType("third_party_embed"), /Unsupported asset type/);
  assert.equal(extractWcagSuccessCriterion(["wcag111", "wcag2a"]), "1.1.1");
});
