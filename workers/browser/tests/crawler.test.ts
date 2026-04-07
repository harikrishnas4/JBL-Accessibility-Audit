import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { AssetApiClient } from "../src/api-client.js";
import {
  type CollectedPage,
  type CrawlCollectorLike,
  type CrawlCollectorSessionLike,
  InventoryCrawler,
} from "../src/crawler.js";
import type { CrawlRequest } from "../src/contracts.js";
import type { DiscoveryNode } from "../src/fingerprints.js";

function run(name: string, fn: () => Promise<void> | void): Promise<void> {
  return Promise.resolve(fn()).then(() => {
    console.log(`ok - ${name}`);
  });
}

const fixturesDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "tests", "fixtures");

class FixtureCollectorSession implements CrawlCollectorSessionLike {
  constructor(private readonly fixturesByUrl: Map<string, string>) {}

  async collectPage(url: string): Promise<CollectedPage> {
    const fixturePath = this.fixturesByUrl.get(url);
    if (!fixturePath) {
      throw new Error(`missing fixture for ${url}`);
    }
    const html = readFileSync(fixturePath, "utf8");
    return {
      page_url: url,
      discovery_nodes: parseFixtureNodes(html, url),
    };
  }

  async close(): Promise<void> {
    return;
  }
}

class FixtureCollector implements CrawlCollectorLike {
  constructor(private readonly fixturesByUrl: Map<string, string>) {}

  async open(): Promise<CrawlCollectorSessionLike> {
    return new FixtureCollectorSession(this.fixturesByUrl);
  }
}

function parseFixtureNodes(html: string, baseUrl: string): DiscoveryNode[] {
  const bodyTemplateId = /<body[^>]*data-template-id="([^"]+)"/i.exec(html)?.[1] ?? null;
  const descriptors: DiscoveryNode[] = [];
  const blockTags: Array<{ tagName: string; attrName: string }> = [
    { tagName: "a", attrName: "href" },
    { tagName: "iframe", attrName: "src" },
    { tagName: "script", attrName: "src" },
    { tagName: "object", attrName: "data" },
  ];

  for (const { tagName, attrName } of blockTags) {
    const pattern = new RegExp(`<${tagName}\\b([^>]*)>([\\s\\S]*?)</${tagName}>`, "gi");
    for (const match of html.matchAll(pattern)) {
      descriptors.push(buildDiscoveryNode(tagName, attrName, match[1] ?? "", match[2] ?? "", baseUrl, bodyTemplateId));
    }
  }

  const embedPattern = /<embed\b([^>]*)\/?>/gi;
  for (const match of html.matchAll(embedPattern)) {
    descriptors.push(buildDiscoveryNode("embed", "src", match[1] ?? "", "", baseUrl, bodyTemplateId));
  }

  return descriptors;
}

function buildDiscoveryNode(
  tagName: string,
  attrName: string,
  rawAttributes: string,
  rawInnerHtml: string,
  baseUrl: string,
  bodyTemplateId: string | null,
): DiscoveryNode {
  const attributes = parseAttributes(rawAttributes);
  const locator = new URL(attributes[attrName] ?? "", baseUrl).toString();
  const dataAttributes = Object.entries(attributes).reduce<Record<string, string>>((accumulator, [key, value]) => {
    if (!key.startsWith("data-")) {
      return accumulator;
    }
    const normalizedKey = key.slice(5).replace(/-([a-z])/g, (_, character: string) => character.toUpperCase());
    accumulator[normalizedKey] = value;
    return accumulator;
  }, {});

  return {
    tag_name: tagName,
    locator,
    text_content: stripTags(rawInnerHtml),
    attributes: {
      id: attributes.id ?? "",
      class: attributes.class ?? "",
      role: attributes.role ?? "",
      type: attributes.type ?? "",
      "data-testid": attributes["data-testid"] ?? "",
      "data-template-id": attributes["data-template-id"] ?? "",
    },
    data_attributes: dataAttributes,
    template_id: attributes["data-template-id"] ?? bodyTemplateId,
    ancestor_chain: [],
  };
}

function parseAttributes(rawAttributes: string): Record<string, string> {
  const attributes: Record<string, string> = {};
  const pattern = /([a-zA-Z_:][a-zA-Z0-9_:.+-]*)="([^"]*)"/g;
  for (const match of rawAttributes.matchAll(pattern)) {
    const key = match[1];
    const value = match[2];
    if (key) {
      attributes[key] = value ?? "";
    }
  }
  return attributes;
}

function stripTags(value: string): string {
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function buildFixtureCollector(): FixtureCollector {
  return new FixtureCollector(
    new Map<string, string>([
      [
        "https://courses.example.com/course/view.php?id=42",
        path.join(fixturesDir, "course-entry.html"),
      ],
      [
        "https://courses.example.com/mod/page/view.php?id=10",
        path.join(fixturesDir, "mod-page.html"),
      ],
      [
        "https://courses.example.com/mod/url/view.php?id=11",
        path.join(fixturesDir, "mod-url.html"),
      ],
      [
        "https://courses.example.com/mod/quiz/view.php?id=12",
        path.join(fixturesDir, "mod-quiz.html"),
      ],
      [
        "https://courses.example.com/mod/lti/view.php?id=13",
        path.join(fixturesDir, "mod-lti.html"),
      ],
    ]),
  );
}

await run("InventoryCrawler extracts in-scope assets and explicit out-of-scope exclusions from fixture pages", async () => {
  const crawler = new InventoryCrawler(buildFixtureCollector());
  const request: CrawlRequest = {
    courseEntryUrl: "https://courses.example.com/course/view.php?id=42",
    authContext: {
      role: "learner",
      login_method: "manual_storage_state",
      captcha_bypassed_manually: false,
      notes: [],
    },
    storageStatePath: "var/evidence/session-state.json",
    ownerTeam: "inventory-team",
    maxPages: 10,
  };

  const result = await crawler.crawl(request);

  assert.deepEqual(result.crawl_snapshot.visited_locators, [
    "https://courses.example.com/course/view.php?id=42",
    "https://courses.example.com/mod/page/view.php?id=10",
    "https://courses.example.com/mod/url/view.php?id=11",
    "https://courses.example.com/mod/quiz/view.php?id=12",
    "https://courses.example.com/mod/lti/view.php?id=13",
  ]);
  assert.equal(result.crawl_snapshot.snapshot_metadata.visited_page_count, 5);
  assert.equal(result.crawl_snapshot.snapshot_metadata.auth_role, "learner");
  assert.deepEqual(result.crawl_snapshot.snapshot_metadata.supported_path_patterns, [
    "mod/page",
    "mod/url",
    "mod/quiz",
    "mod/lti",
  ]);

  const assetTypes = new Set(result.assets.map((asset) => asset.asset_type));
  assert.ok(assetTypes.has("web_page"));
  assert.ok(assetTypes.has("quiz_page"));
  assert.ok(assetTypes.has("lti_launch"));
  assert.ok(assetTypes.has("document_pdf"));
  assert.ok(assetTypes.has("media_video"));
  assert.ok(assetTypes.has("third_party_embed"));
  assert.ok(assetTypes.has("component"));

  const pageAsset = result.assets.find((asset) => asset.locator.includes("/mod/page/"));
  assert.ok(pageAsset);
  assert.equal(pageAsset?.owner_team, "inventory-team");
  assert.equal(pageAsset?.auth_context.role, "learner");
  assert.equal(pageAsset?.component_fingerprint.stable_css_selector, "a#page-link");
  assert.equal(pageAsset?.component_fingerprint.template_id, "course-module-link");
  assert.equal(pageAsset?.component_fingerprint.bundle_name, "view.php");
  assert.equal(result.assets.find((asset) => asset.locator.includes("/mod/url/"))?.asset_type, "web_page");
  assert.equal(
    result.assets.find((asset) => asset.locator.endsWith("/assets/lesson-1.pdf"))?.asset_type,
    "document_pdf",
  );
  assert.equal(
    result.assets.find((asset) => asset.locator.endsWith("/assets/lecture-1.mp4"))?.asset_type,
    "media_video",
  );
  assert.equal(
    result.assets.find((asset) => asset.locator.endsWith("/player/course.js"))?.asset_type,
    "component",
  );
  assert.equal(
    result.assets.find((asset) => asset.locator.includes("third-party.example.com/embed/42"))?.asset_type,
    "third_party_embed",
  );

  const excludedLocators = new Set(result.crawl_snapshot.excluded_locators.map((item) => item.locator));
  assert.ok(excludedLocators.has("https://courses.example.com/mod/forum/view.php?id=14"));
  assert.ok(excludedLocators.has("https://courses.example.com/mod/forum/view.php?id=15"));
  assert.ok(excludedLocators.has("https://third-party.example.com/embed/42"));
  assert.ok(
    result.assets
      .filter((asset) => asset.scope_status === "out_of_scope")
      .every((asset) => typeof asset.scope_reason === "string" && asset.scope_reason.length > 0),
  );
});

await run("AssetApiClient maps crawl results into the assets upsert endpoint payload", async () => {
  const requests: Array<{ input: string; init?: { method?: string; headers?: Record<string, string>; body?: string } }> =
    [];
  const client = new AssetApiClient("http://127.0.0.1:8000", async (input, init) => {
    requests.push({ input, init });
    return {
      ok: true,
      status: 201,
      async json() {
        return {
          run_id: "run-1",
          crawl_snapshot: {
            crawl_snapshot_id: "crawl-1",
            run_id: "run-1",
            entry_locator: "https://courses.example.com/course/view.php?id=42",
            started_at: "2026-04-06T00:00:00Z",
            completed_at: "2026-04-06T00:05:00Z",
            visited_locators: ["https://courses.example.com/course/view.php?id=42"],
            excluded_locators: [],
            snapshot_metadata: { visited_page_count: 1 },
            created_at: "2026-04-06T00:05:00Z",
            updated_at: "2026-04-06T00:05:00Z",
          },
          assets: [],
        };
      },
      async text() {
        return "";
      },
    };
  });

  const payload = client.buildUpsertRequest("run-1", {
    crawl_snapshot: {
      entry_locator: "https://courses.example.com/course/view.php?id=42",
      started_at: "2026-04-06T00:00:00Z",
      completed_at: "2026-04-06T00:05:00Z",
      visited_locators: ["https://courses.example.com/course/view.php?id=42"],
      excluded_locators: [],
      snapshot_metadata: { visited_page_count: 1 },
    },
    assets: [],
  });

  const response = await client.upsertAssets(payload);

  assert.equal(response.run_id, "run-1");
  assert.equal(requests[0]?.input, "http://127.0.0.1:8000/assets/upsert");
  assert.equal(requests[0]?.init?.method, "POST");
  assert.deepEqual(JSON.parse(requests[0]?.init?.body ?? "{}"), payload);
});
