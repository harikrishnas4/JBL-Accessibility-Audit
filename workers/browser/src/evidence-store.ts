import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import type { EvidenceArtifactRecord, EvidenceArtifactType } from "./contracts.js";

export interface ScreenshotPageLike {
  screenshot(options: { path: string; fullPage: boolean }): Promise<Buffer>;
}

export interface StoredArtifactReference extends EvidenceArtifactRecord {
  absolute_path: string;
}

export interface EvidenceStorageAdapter {
  prepareArtifactDestination(
    runId: string,
    assetId: string,
    artifactType: EvidenceArtifactType,
    label: string,
    extension: string,
    metadata?: Record<string, unknown>,
  ): Promise<StoredArtifactReference>;
  writeScreenshot(
    runId: string,
    assetId: string,
    page: ScreenshotPageLike,
    label: string,
    metadata?: Record<string, unknown>,
  ): Promise<StoredArtifactReference>;
  writeTrace(
    runId: string,
    assetId: string,
    label: string,
    traceBytes: Buffer,
    metadata?: Record<string, unknown>,
  ): Promise<StoredArtifactReference>;
  writeDomSnapshot(
    runId: string,
    assetId: string,
    label: string,
    domSnapshot: string,
    metadata?: Record<string, unknown>,
  ): Promise<StoredArtifactReference>;
}

export class LocalEvidenceStorageAdapter implements EvidenceStorageAdapter {
  constructor(
    private readonly rootDirectory: string = path.resolve(process.cwd(), "var", "evidence"),
    private readonly pathPrefix: string = "var/evidence",
  ) {}

  async writeScreenshot(
    runId: string,
    assetId: string,
    page: ScreenshotPageLike,
    label: string,
    metadata: Record<string, unknown> = {},
  ): Promise<StoredArtifactReference> {
    const destination = await this.prepareArtifactDestination(runId, assetId, "screenshot", label, "png", metadata);
    await page.screenshot({ path: destination.absolute_path, fullPage: true });
    return destination;
  }

  async writeTrace(
    runId: string,
    assetId: string,
    label: string,
    traceBytes: Buffer,
    metadata: Record<string, unknown> = {},
  ): Promise<StoredArtifactReference> {
    const destination = await this.prepareArtifactDestination(runId, assetId, "trace", label, "zip", metadata);
    await writeFile(destination.absolute_path, traceBytes);
    return destination;
  }

  async writeDomSnapshot(
    runId: string,
    assetId: string,
    label: string,
    domSnapshot: string,
    metadata: Record<string, unknown> = {},
  ): Promise<StoredArtifactReference> {
    const destination = await this.prepareArtifactDestination(
      runId,
      assetId,
      "dom_snapshot_reference",
      label,
      "html",
      metadata,
    );
    await writeFile(destination.absolute_path, domSnapshot, "utf8");
    return destination;
  }

  async prepareArtifactDestination(
    runId: string,
    assetId: string,
    artifactType: EvidenceArtifactType,
    label: string,
    extension: string,
    metadata: Record<string, unknown> = {},
  ): Promise<StoredArtifactReference> {
    const safeLabel = label.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "") || "artifact";
    const fileName = `${new Date().toISOString().replace(/[:.]/g, "-")}--${safeLabel}.${extension}`;
    const absoluteDirectory = path.join(this.rootDirectory, runId, assetId);
    await mkdir(absoluteDirectory, { recursive: true });
    return {
      artifact_type: artifactType,
      absolute_path: path.join(absoluteDirectory, fileName),
      storage_path: path.posix.join(this.pathPrefix.replace(/\\/g, "/"), runId, assetId, fileName),
      artifact_metadata: metadata,
      captured_at: new Date().toISOString(),
    };
  }
}
