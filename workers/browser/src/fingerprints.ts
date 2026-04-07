import { createHash } from "node:crypto";

import type { AssetType, ComponentFingerprint } from "./contracts.js";

export interface DiscoveryAncestor {
  tag_name: string;
  id: string | null;
  data_testid: string | null;
  class_names: string[];
}

export interface DiscoveryNode {
  tag_name: string;
  locator: string;
  text_content: string;
  attributes: Record<string, string>;
  data_attributes: Record<string, string>;
  template_id: string | null;
  ancestor_chain: DiscoveryAncestor[];
}

function hashValue(value: string): string {
  return createHash("sha256").update(value).digest("hex").slice(0, 16);
}

function quoteAttribute(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function buildNodeSelector(node: DiscoveryNode): string {
  const id = node.attributes.id;
  if (id) {
    return `${node.tag_name.toLowerCase()}#${id}`;
  }

  const dataTestId = node.data_attributes.testid ?? node.attributes["data-testid"];
  if (dataTestId) {
    return `${node.tag_name.toLowerCase()}[data-testid="${quoteAttribute(dataTestId)}"]`;
  }

  const templateId = node.template_id ?? node.data_attributes.templateId ?? node.attributes["data-template-id"];
  if (templateId) {
    return `${node.tag_name.toLowerCase()}[data-template-id="${quoteAttribute(templateId)}"]`;
  }

  const role = node.attributes.role;
  if (role) {
    return `${node.tag_name.toLowerCase()}[role="${quoteAttribute(role)}"]`;
  }

  const classNames = node.attributes.class
    ?.split(/\s+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 2) ?? [];
  if (classNames.length > 0) {
    return `${node.tag_name.toLowerCase()}.${classNames.join(".")}`;
  }

  return node.tag_name.toLowerCase();
}

function buildAncestorSelector(ancestor: DiscoveryAncestor): string {
  if (ancestor.id) {
    return `${ancestor.tag_name.toLowerCase()}#${ancestor.id}`;
  }
  if (ancestor.data_testid) {
    return `${ancestor.tag_name.toLowerCase()}[data-testid="${quoteAttribute(ancestor.data_testid)}"]`;
  }
  if (ancestor.class_names.length > 0) {
    return `${ancestor.tag_name.toLowerCase()}.${ancestor.class_names.slice(0, 2).join(".")}`;
  }
  return ancestor.tag_name.toLowerCase();
}

export function buildStableCssSelector(node: DiscoveryNode): string {
  const selectorParts = node.ancestor_chain.slice(-2).map(buildAncestorSelector);
  selectorParts.push(buildNodeSelector(node));
  return selectorParts.join(" > ");
}

export function extractBundleName(locator: string): string | null {
  try {
    const url = new URL(locator);
    const pathnameParts = url.pathname.split("/").filter(Boolean);
    if (pathnameParts.length === 0) {
      return null;
    }
    return pathnameParts[pathnameParts.length - 1] ?? null;
  } catch {
    return null;
  }
}

export function buildControlledDomSignature(node: DiscoveryNode): string {
  const signaturePayload = JSON.stringify({
    tag: node.tag_name.toLowerCase(),
    locator_path: safePathname(node.locator),
    text: node.text_content.trim().replace(/\s+/g, " ").slice(0, 80),
    attributes: {
      id: node.attributes.id ?? null,
      role: node.attributes.role ?? null,
      type: node.attributes.type ?? null,
      class: node.attributes.class ?? null,
    },
    data_attributes: Object.keys(node.data_attributes)
      .sort()
      .reduce<Record<string, string>>((accumulator, key) => {
        accumulator[key] = node.data_attributes[key] ?? "";
        return accumulator;
      }, {}),
    template_id: node.template_id,
  });
  return hashValue(signaturePayload);
}

function safePathname(locator: string): string {
  try {
    const url = new URL(locator);
    return url.pathname;
  } catch {
    return locator;
  }
}

export function buildComponentFingerprint(node: DiscoveryNode): ComponentFingerprint {
  return {
    stable_css_selector: buildStableCssSelector(node),
    template_id: node.template_id,
    bundle_name: extractBundleName(node.locator),
    controlled_dom_signature: buildControlledDomSignature(node),
  };
}

export function buildSharedKey(sourceSystem: string, node: DiscoveryNode, fingerprint: ComponentFingerprint): string {
  return hashValue(
    JSON.stringify({
      source_system: sourceSystem,
      locator_path: safePathname(node.locator),
      selector: fingerprint.stable_css_selector,
      template_id: fingerprint.template_id,
      bundle_name: fingerprint.bundle_name,
      dom_signature: fingerprint.controlled_dom_signature,
    }),
  );
}

export function buildAssetId(assetType: AssetType, locator: string, fingerprint: ComponentFingerprint): string {
  return hashValue(
    JSON.stringify({
      asset_type: assetType,
      locator,
      selector: fingerprint.stable_css_selector,
      dom_signature: fingerprint.controlled_dom_signature,
    }),
  );
}
