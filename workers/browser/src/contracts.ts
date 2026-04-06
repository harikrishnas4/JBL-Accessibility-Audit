import type { Cookie } from "playwright";

export type AuthRole = "learner" | "instructor" | "admin";
export type LoginMethod = "username_password" | "manual_storage_state" | "manual_cookie_injection";
export type ValidationStatus = "pending" | "validated" | "failed";
export type AssetScopeStatus = "in_scope" | "out_of_scope";
export type ScanAssetType = "web_page" | "component" | "lti_launch" | "quiz_page";
export type FindingResultType = "violation" | "pass" | "incomplete" | "inapplicable";
export type EvidenceArtifactType = "screenshot" | "trace" | "dom_snapshot_reference";

export interface LoginFlowSelectors {
  loginUrl: string;
  usernameSelector: string;
  passwordSelector: string;
  submitSelector: string;
}

export interface UsernamePasswordLoginFlow {
  username: string;
  password: string;
  selectors: LoginFlowSelectors;
}

export interface ManualSessionImport {
  storageStatePath?: string;
  cookies?: Cookie[];
  captchaBypassedManually?: boolean;
}

export interface AuthenticatedAccessSignal {
  authenticatedSelector?: string;
  authenticatedUrlPattern?: string;
  authenticatedTextPattern?: string;
}

export interface SessionRequest {
  authRole: AuthRole;
  courseUrl: string;
  loginFlow?: UsernamePasswordLoginFlow;
  manualSession?: ManualSessionImport;
  validation: AuthenticatedAccessSignal;
  persistSessionStatePath?: string;
}

export interface SessionAuthContext {
  role: AuthRole;
  login_method: LoginMethod;
  captcha_bypassed_manually: boolean;
  notes: string[];
}

export interface SessionResult {
  authContext: SessionAuthContext;
  sessionStatePath: string | null;
  validationStatus: ValidationStatus;
  authenticated: boolean;
}

export interface AuthProfileCreateRequest {
  run_id: string;
  auth_context: SessionAuthContext;
  session_state_path: string | null;
  validation_status: ValidationStatus;
}

export interface AuthProfileRecord extends AuthProfileCreateRequest {
  auth_profile_id: string;
  created_at: string;
}

export interface CrawlRequest {
  courseEntryUrl: string;
  authContext: SessionAuthContext;
  storageStatePath?: string;
  cookies?: Cookie[];
  ownerTeam?: string | null;
  maxPages?: number;
}

export interface ComponentFingerprint {
  stable_css_selector: string;
  template_id: string | null;
  bundle_name: string | null;
  controlled_dom_signature: string;
}

export interface ExtractedAsset {
  asset_id: string;
  asset_type: string;
  source_system: string;
  locator: string;
  scope_status: AssetScopeStatus;
  scope_reason?: string;
  layer: string;
  shared_key: string | null;
  owner_team: string | null;
  auth_context: SessionAuthContext;
  handling_path: string;
  component_fingerprint: ComponentFingerprint;
  updated_at: string;
}

export interface CrawlExclusionRecord {
  locator: string;
  reason: string;
}

export interface CrawlSnapshotPayload {
  entry_locator: string;
  started_at: string;
  completed_at: string;
  visited_locators: string[];
  excluded_locators: CrawlExclusionRecord[];
  snapshot_metadata: Record<string, unknown>;
}

export interface CrawlResult {
  crawl_snapshot: CrawlSnapshotPayload;
  assets: ExtractedAsset[];
}

export interface AssetUpsertRequest {
  run_id: string;
  crawl_snapshot: CrawlSnapshotPayload;
  assets: ExtractedAsset[];
}

export interface CrawlSnapshotRecord extends CrawlSnapshotPayload {
  crawl_snapshot_id: string;
  run_id: string;
  created_at: string;
  updated_at: string;
}

export interface AssetRecord extends ExtractedAsset {
  run_id: string;
  crawl_snapshot_id: string | null;
  created_at: string;
}

export interface AssetUpsertResponse {
  run_id: string;
  crawl_snapshot: CrawlSnapshotRecord;
  assets: AssetRecord[];
}

export interface ViewportSpec {
  name: string;
  width: number;
  height: number;
}

export interface EvidenceArtifactRecord {
  artifact_type: EvidenceArtifactType;
  storage_path: string;
  artifact_metadata: Record<string, unknown>;
  captured_at: string;
}

export interface RawFindingRecord {
  result_type: FindingResultType;
  rule_id: string;
  wcag_sc: string | null;
  resolution_state: string;
  severity: string | null;
  message: string;
  target_fingerprint: string | null;
  raw_payload: Record<string, unknown>;
  observed_at: string;
  evidence_artifacts: EvidenceArtifactRecord[];
}

export interface ScanAdapterRequest {
  runId: string;
  assetId: string;
  assetType: ScanAssetType;
  locator: string;
  viewport: ViewportSpec;
  storageStatePath?: string;
  cookies?: Cookie[];
}

export interface ScanAdapterResult {
  run_id: string;
  asset_id: string;
  asset_type: ScanAssetType;
  viewport: ViewportSpec;
  findings: RawFindingRecord[];
  scan_metadata: Record<string, unknown>;
}
