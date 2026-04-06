import type {
  AssetUpsertRequest,
  AssetUpsertResponse,
  AuthProfileCreateRequest,
  AuthProfileRecord,
  CrawlResult,
  SessionResult,
} from "./contracts.js";

export interface FetchResponseLike {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
  text(): Promise<string>;
}

export type FetchLike = (
  input: string,
  init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
  },
) => Promise<FetchResponseLike>;

export class AuthProfileApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetchImpl: FetchLike = globalThis.fetch as unknown as FetchLike,
  ) {}

  async createAuthProfile(payload: AuthProfileCreateRequest): Promise<AuthProfileRecord> {
    const response = await this.fetchImpl(`${this.baseUrl}/auth-profiles`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return this.handleResponse(response);
  }

  async getAuthProfile(authProfileId: string): Promise<AuthProfileRecord> {
    const response = await this.fetchImpl(`${this.baseUrl}/auth-profiles/${authProfileId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    return this.handleResponse(response);
  }

  buildCreateRequest(runId: string, session: SessionResult): AuthProfileCreateRequest {
    return {
      run_id: runId,
      auth_context: session.authContext,
      session_state_path: session.sessionStatePath,
      validation_status: session.validationStatus,
    };
  }

  private async handleResponse(response: FetchResponseLike): Promise<AuthProfileRecord> {
    if (!response.ok) {
      throw new Error(`AuthProfile API request failed with status ${response.status}: ${await response.text()}`);
    }
    return (await response.json()) as AuthProfileRecord;
  }
}

export class AssetApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetchImpl: FetchLike = globalThis.fetch as unknown as FetchLike,
  ) {}

  async upsertAssets(payload: AssetUpsertRequest): Promise<AssetUpsertResponse> {
    const response = await this.fetchImpl(`${this.baseUrl}/assets/upsert`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return this.handleResponse(response);
  }

  buildUpsertRequest(runId: string, crawlResult: CrawlResult): AssetUpsertRequest {
    return {
      run_id: runId,
      crawl_snapshot: crawlResult.crawl_snapshot,
      assets: crawlResult.assets,
    };
  }

  private async handleResponse(response: FetchResponseLike): Promise<AssetUpsertResponse> {
    if (!response.ok) {
      throw new Error(`Asset API request failed with status ${response.status}: ${await response.text()}`);
    }
    return (await response.json()) as AssetUpsertResponse;
  }
}
