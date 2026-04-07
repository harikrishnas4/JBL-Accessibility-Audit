import assert from "node:assert/strict";

import {
  executeTier1Batch,
  type Tier1BatchExecutionRequest,
  type Tier1ScanAdapterLike,
} from "../src/batch-executor.js";

function run(name: string, fn: () => Promise<void> | void): Promise<void> {
  return Promise.resolve(fn()).then(() => {
    console.log(`ok - ${name}`);
  });
}

await run("executeTier1Batch aggregates findings across the viewport matrix", async () => {
  const adapter: Tier1ScanAdapterLike = {
    async scan(request) {
      return {
        run_id: request.runId,
        asset_id: request.assetId,
        asset_type: request.assetType,
        viewport: request.viewport,
        findings: [
          {
            result_type: "violation",
            rule_id: `${request.viewport.name}-rule`,
            wcag_sc: "1.1.1",
            resolution_state: "new",
            severity: "critical",
            message: `Failure for ${request.viewport.name}`,
            target_fingerprint: "main",
            raw_payload: {},
            observed_at: "2026-04-07T10:00:00.000Z",
            evidence_artifacts: [],
          },
        ],
        scan_metadata: {
          scanned_url: request.locator,
        },
      };
    },
  };

  const request: Tier1BatchExecutionRequest = {
    run_id: "run-1",
    assets: [
      {
        asset_id: "asset-1",
        asset_type: "web_page",
        locator: "https://example.com/page-1",
      },
    ],
    viewports: [
      { name: "desktop", width: 1280, height: 800 },
      { name: "mobile", width: 375, height: 667 },
    ],
  };

  const result = await executeTier1Batch(request, adapter);

  assert.equal(result.summary.successful_asset_count, 1);
  assert.equal(result.summary.failed_asset_count, 0);
  assert.equal(result.summary.finding_count, 2);
  assert.equal(result.asset_results[0]?.findings.length, 2);
  assert.deepEqual(
    result.asset_results[0]?.scan_metadata.executions.map((item) => item.viewport),
    ["desktop", "mobile"],
  );
});

await run("executeTier1Batch preserves partial asset failures without dropping successful assets", async () => {
  const adapter: Tier1ScanAdapterLike = {
    async scan(request) {
      if (request.assetId === "asset-2") {
        throw new Error("playwright navigation timeout");
      }
      return {
        run_id: request.runId,
        asset_id: request.assetId,
        asset_type: request.assetType,
        viewport: request.viewport,
        findings: [],
        scan_metadata: {
          scanned_url: request.locator,
        },
      };
    },
  };

  const result = await executeTier1Batch(
    {
      run_id: "run-2",
      assets: [
        {
          asset_id: "asset-1",
          asset_type: "web_page",
          locator: "https://example.com/page-1",
        },
        {
          asset_id: "asset-2",
          asset_type: "quiz_page",
          locator: "https://example.com/quiz-2",
        },
      ],
      viewports: [{ name: "desktop", width: 1280, height: 800 }],
    },
    adapter,
  );

  assert.equal(result.summary.successful_asset_count, 1);
  assert.equal(result.summary.failed_asset_count, 1);
  assert.equal(result.asset_results[0]?.asset_id, "asset-1");
  assert.equal(result.failures[0]?.asset_id, "asset-2");
  assert.match(result.failures[0]?.error ?? "", /timeout/i);
});
