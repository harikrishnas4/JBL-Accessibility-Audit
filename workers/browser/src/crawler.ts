import { chromium, type Browser, type BrowserContext, type BrowserType, type Cookie, type Page } from "playwright";

import type {
  CrawlExclusionRecord,
  CrawlRequest,
  CrawlResult,
  ExtractedAsset,
} from "./contracts.js";
import {
  buildAssetId,
  buildComponentFingerprint,
  buildSharedKey,
  type DiscoveryAncestor,
  type DiscoveryNode,
} from "./fingerprints.js";

const SUPPORTED_MODULE_PATHS = [
  { fragment: "mod/page", regex: /\/mod\/page\//i, assetType: "course_page" },
  { fragment: "mod/url", regex: /\/mod\/url\//i, assetType: "course_link" },
  { fragment: "mod/quiz", regex: /\/mod\/quiz\//i, assetType: "course_quiz" },
  { fragment: "mod/lti", regex: /\/mod\/lti\//i, assetType: "course_lti" },
] as const;

const EMBED_TAGS = new Set(["iframe", "script", "object", "embed"]);

export interface CollectedPage {
  page_url: string;
  discovery_nodes: DiscoveryNode[];
}

export interface CrawlCollectorSessionLike {
  collectPage(url: string): Promise<CollectedPage>;
  close(): Promise<void>;
}

export interface CrawlCollectorLike {
  open(request: CrawlRequest): Promise<CrawlCollectorSessionLike>;
}

class PlaywrightCrawlCollector implements CrawlCollectorLike {
  constructor(
    private readonly browserType: BrowserType<Browser> = chromium,
    private readonly launchOptions: Parameters<BrowserType<Browser>["launch"]>[0] = { headless: true },
  ) {}

  async open(request: CrawlRequest): Promise<CrawlCollectorSessionLike> {
    const browser = await this.browserType.launch(this.launchOptions);
    const context = await browser.newContext(
      request.storageStatePath ? { storageState: request.storageStatePath } : undefined,
    );
    if (request.cookies?.length) {
      await context.addCookies(request.cookies);
    }
    return new PlaywrightCrawlCollectorSession(browser, context);
  }
}

class PlaywrightCrawlCollectorSession implements CrawlCollectorSessionLike {
  constructor(
    private readonly browser: Browser,
    private readonly context: BrowserContext,
  ) {}

  async collectPage(url: string): Promise<CollectedPage> {
    const page = await this.context.newPage();
    try {
      await page.goto(url);
      return {
        page_url: page.url(),
        discovery_nodes: await collectDiscoveryNodes(page),
      };
    } finally {
      await page.close();
    }
  }

  async close(): Promise<void> {
    await this.context.close();
    await this.browser.close();
  }
}

async function collectDiscoveryNodes(page: Page): Promise<DiscoveryNode[]> {
  return page.evaluate(() => {
    const toAbsoluteUrl = (value: string | null): string | null => {
      if (!value) {
        return null;
      }
      try {
        return new URL(value, document.baseURI).toString();
      } catch {
        return null;
      }
    };

    const toAncestor = (element: Element): DiscoveryAncestor => {
      const dataTestId = element.getAttribute("data-testid");
      const classNames = (element.getAttribute("class") ?? "")
        .split(/\s+/)
        .map((item) => item.trim())
        .filter(Boolean);
      return {
        tag_name: element.tagName.toLowerCase(),
        id: element.getAttribute("id"),
        data_testid: dataTestId,
        class_names: classNames,
      };
    };

    const trackedNodes = Array.from(
      document.querySelectorAll("a[href], iframe[src], script[src], object[data], embed[src]"),
    );
    return trackedNodes.flatMap((element) => {
      const tagName = element.tagName.toLowerCase();
      const attributeName =
        tagName === "a" ? "href" : tagName === "object" ? "data" : "src";
      const locator = toAbsoluteUrl(element.getAttribute(attributeName));
      if (!locator) {
        return [];
      }

      const dataAttributes = Array.from(element.attributes)
        .filter((attribute) => attribute.name.startsWith("data-"))
        .reduce<Record<string, string>>((accumulator, attribute) => {
          const rawKey = attribute.name.slice(5);
          const normalizedKey = rawKey.replace(/-([a-z])/g, (_, character: string) => character.toUpperCase());
          accumulator[normalizedKey] = attribute.value;
          return accumulator;
        }, {});

      const ancestorChain: DiscoveryAncestor[] = [];
      let parent = element.parentElement;
      while (parent && ancestorChain.length < 3) {
        ancestorChain.unshift(toAncestor(parent));
        parent = parent.parentElement;
      }

      const templateSource =
        element.closest("[data-template-id]")?.getAttribute("data-template-id") ??
        document.body.getAttribute("data-template-id");

      return [
        {
          tag_name: tagName,
          locator,
          text_content: element.textContent ?? "",
          attributes: {
            id: element.getAttribute("id") ?? "",
            class: element.getAttribute("class") ?? "",
            role: element.getAttribute("role") ?? "",
            type: element.getAttribute("type") ?? "",
            "data-testid": element.getAttribute("data-testid") ?? "",
            "data-template-id": element.getAttribute("data-template-id") ?? "",
          },
          data_attributes: dataAttributes,
          template_id: templateSource,
          ancestor_chain: ancestorChain,
        },
      ];
    });
  });
}

export class InventoryCrawler {
  constructor(private readonly collector: CrawlCollectorLike = new PlaywrightCrawlCollector()) {}

  async crawl(request: CrawlRequest): Promise<CrawlResult> {
    const crawlStartedAt = new Date().toISOString();
    const maxPages = request.maxPages ?? 25;
    const collectorSession = await this.collector.open(request);
    const pendingUrls: string[] = [request.courseEntryUrl];
    const queuedUrls = new Set<string>(pendingUrls);
    const visitedUrls = new Set<string>();
    const assetsById = new Map<string, ExtractedAsset>();
    const excludedLocators = new Map<string, CrawlExclusionRecord>();

    try {
      while (pendingUrls.length > 0 && visitedUrls.size < maxPages) {
        const currentUrl = pendingUrls.shift();
        if (!currentUrl || visitedUrls.has(currentUrl)) {
          continue;
        }

        const collectedPage = await collectorSession.collectPage(currentUrl);
        visitedUrls.add(collectedPage.page_url);

        for (const node of collectedPage.discovery_nodes) {
          const asset = classifyDiscoveredNode(node, request);
          if (asset === null) {
            continue;
          }

          assetsById.set(asset.asset_id, asset);
          if (asset.scope_status === "out_of_scope" && asset.scope_reason) {
            excludedLocators.set(asset.locator, { locator: asset.locator, reason: asset.scope_reason });
          }

          if (isApprovedModuleLocator(asset.locator) && !visitedUrls.has(asset.locator) && !queuedUrls.has(asset.locator)) {
            pendingUrls.push(asset.locator);
            queuedUrls.add(asset.locator);
          }
        }
      }
    } finally {
      await collectorSession.close();
    }

    const crawlCompletedAt = new Date().toISOString();
    return {
      crawl_snapshot: {
        entry_locator: request.courseEntryUrl,
        started_at: crawlStartedAt,
        completed_at: crawlCompletedAt,
        visited_locators: Array.from(visitedUrls),
        excluded_locators: Array.from(excludedLocators.values()),
        snapshot_metadata: {
          supported_path_patterns: SUPPORTED_MODULE_PATHS.map((item) => item.fragment),
          visited_page_count: visitedUrls.size,
          extracted_asset_count: assetsById.size,
          auth_role: request.authContext.role,
        },
      },
      assets: Array.from(assetsById.values()).sort((left, right) => left.asset_id.localeCompare(right.asset_id)),
    };
  }
}

export function classifyDiscoveredNode(node: DiscoveryNode, request: CrawlRequest): ExtractedAsset | null {
  const locator = parseLocator(node.locator);
  if (!locator) {
    return null;
  }

  const moduleMatch = SUPPORTED_MODULE_PATHS.find((item) => item.regex.test(locator.pathname));
  if (moduleMatch) {
    return buildAssetRecord({
      request,
      node,
      locator: locator.toString(),
      assetType: moduleMatch.assetType,
      sourceSystem: "moodle",
      scopeStatus: "in_scope",
      layer: "course_module",
      handlingPath: moduleMatch.fragment,
    });
  }

  if (/\/mod\//i.test(locator.pathname)) {
    return buildAssetRecord({
      request,
      node,
      locator: locator.toString(),
      assetType: "unsupported_module",
      sourceSystem: "moodle",
      scopeStatus: "out_of_scope",
      scopeReason: "unsupported_module_path",
      layer: "course_module",
      handlingPath: locator.pathname.split("/").slice(1, 3).join("/"),
    });
  }

  if (locator.pathname.toLowerCase().endsWith(".pdf")) {
    return buildAssetRecord({
      request,
      node,
      locator: locator.toString(),
      assetType: "pdf_document",
      sourceSystem: locator.hostname,
      scopeStatus: "in_scope",
      layer: "document",
      handlingPath: `${node.tag_name}:pdf`,
    });
  }

  if (locator.hostname === "cdn-media.jblearning.com") {
    return buildAssetRecord({
      request,
      node,
      locator: locator.toString(),
      assetType: "cdn_media_asset",
      sourceSystem: locator.hostname,
      scopeStatus: "in_scope",
      layer: "embedded_media",
      handlingPath: `${node.tag_name}:cdn-media`,
    });
  }

  if (locator.hostname === "human.biodigital.com") {
    return buildAssetRecord({
      request,
      node,
      locator: locator.toString(),
      assetType: "biodigital_embed",
      sourceSystem: locator.hostname,
      scopeStatus: "in_scope",
      layer: "embedded_content",
      handlingPath: `${node.tag_name}:biodigital`,
    });
  }

  if (EMBED_TAGS.has(node.tag_name)) {
    return buildAssetRecord({
      request,
      node,
      locator: locator.toString(),
      assetType: "unsupported_embed",
      sourceSystem: locator.hostname || "embedded_resource",
      scopeStatus: "out_of_scope",
      scopeReason: "unsupported_embed_origin",
      layer: "embedded_content",
      handlingPath: `${node.tag_name}:unsupported`,
    });
  }

  return null;
}

function buildAssetRecord(options: {
  request: CrawlRequest;
  node: DiscoveryNode;
  locator: string;
  assetType: string;
  sourceSystem: string;
  scopeStatus: ExtractedAsset["scope_status"];
  scopeReason?: string;
  layer: string;
  handlingPath: string;
}): ExtractedAsset {
  const { request, node, locator, assetType, sourceSystem, scopeStatus, scopeReason, layer, handlingPath } = options;
  const fingerprint = buildComponentFingerprint({ ...node, locator });
  return {
    asset_id: buildAssetId(assetType, locator, fingerprint),
    asset_type: assetType,
    source_system: sourceSystem,
    locator,
    scope_status: scopeStatus,
    ...(scopeReason ? { scope_reason: scopeReason } : {}),
    layer,
    shared_key: buildSharedKey(sourceSystem, { ...node, locator }, fingerprint),
    owner_team: request.ownerTeam ?? null,
    auth_context: request.authContext,
    handling_path: handlingPath,
    component_fingerprint: fingerprint,
    updated_at: new Date().toISOString(),
  };
}

function parseLocator(value: string): URL | null {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}

function isApprovedModuleLocator(locator: string): boolean {
  const parsed = parseLocator(locator);
  if (!parsed) {
    return false;
  }
  return SUPPORTED_MODULE_PATHS.some((item) => item.regex.test(parsed.pathname));
}
