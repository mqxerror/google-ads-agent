import type {
  Campaign,
  AdGroup,
  Keyword,
  Ad,
  GuidelineFile,
  Conversation,
  AccountV2,
  DashboardData,
  Alert,
  OnboardingResult,
  CampaignGoal,
} from '@/types';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

// ── Freshness envelope (Dashboard v2.1 — Epic A, story A3) ───────
// The backend attaches this to its read endpoints so every home section can
// show its data age honestly. `/metrics/overview` + `/account-report` ship it
// in the JSON body; `/campaigns` ships it as an `X-Data-Freshness` response
// header (its body is a bare array — see fetchCampaignsFreshness). The chip is
// judged by data_through_date, NEVER by a synced_at stamp (that stamp lies —
// see the plan RC-5).
export interface FreshnessEnvelope {
  /** MAX(date) actually written to the metrics store — the honest age anchor. */
  data_through_date: string | null;
  /** When a sync last VERIFIED data against Google (null = never succeeded). */
  last_success_at: string | null;
  /** Minutes since last_success_at (null = never). */
  age_minutes: number | null;
  /** 'fresh' | 'syncing' | 'stale' | 'error'. */
  state: string;
  /** Present only for the 'error' state — the last error string. */
  detail?: string | null;
}

// ── Live-truth campaign header (Dashboard v2.1 — Epic B / B4, PART 2) ─
// The control-plane surface (status · bidding · budget) read LIVE from Google
// with a 60s micro-cache, so the header can show "✓ live" and never lie about
// account state (fixes RC-8 "app shows Maximize Conversions when account says
// Maximize Clicks"). On a live-read failure the endpoint returns state
// 'unverified' + a roster `fallback` so the UI degrades to amber, never silent.
export interface LiveHeadFallback {
  status: string | null;
  bidding_strategy: string | null;
  budget_micros: number | null;
  last_synced_at: string | null;
}
export interface LiveHead {
  campaign_id: string;
  status: string | null;
  bidding_strategy: string | null;
  budget_micros: number | null;
  campaign_type: string | null;
  name: string | null;
  /** ISO instant the read actually verified against Google (live state only). */
  verified_at: string | null;
  state: 'live' | 'unverified';
  /** Present only for the 'unverified' state — the last-known roster values. */
  fallback?: LiveHeadFallback | null;
}

/** ONE tiny live GAQL read of a campaign's control-plane state (60s TTL server
 *  side). READ-ONLY. Never throws for a quota/circuit failure — the server
 *  returns state:'unverified' with a roster fallback instead. */
export async function fetchCampaignLiveHead(
  accountId: string,
  campaignId: string,
): Promise<LiveHead> {
  return request<LiveHead>(`/accounts/${accountId}/campaigns/${campaignId}/live-head`);
}

// ── External changes ("changed outside the app" — Epic C / C5) ────────
// Out-of-band roster changes (status / bidding_strategy / budget_micros) that
// happened without an app-side mutation — the answer to "why does the account
// look different?" (the Greece-Plan-B mystery). Local SQLite, zero Google calls.
export interface ExternalChange {
  id: number;
  campaign_id: string;
  account_id: string;
  field: string;
  before: string | null;
  after: string | null;
  detected_at: string;
  source: string;
}
export async function fetchExternalChanges(
  accountId: string,
  limit = 20,
): Promise<ExternalChange[]> {
  const res = await request<{ external_changes: ExternalChange[] }>(
    `/accounts/${accountId}/external-changes?limit=${limit}`,
  );
  return res.external_changes ?? [];
}

// ── Campaign mapper ─────────────────────────────────────────────

interface ApiCampaign {
  id: string;
  name: string;
  status: string;
  campaign_type: string;
  budget_micros: number;
  bidding_strategy: string;
  metrics: { impressions: number; clicks: number; cost_micros: number; conversions: number; ctr: number; avg_cpc_micros: number };
}

function mapCampaign(c: ApiCampaign): Campaign {
  const { clicks, conversions, cost_micros: costMicros } = c.metrics;
  return {
    id: c.id,
    name: c.name,
    status: c.status as Campaign['status'],
    channelType: c.campaign_type,
    budgetAmountMicros: c.budget_micros,
    // B2: never dress the channel type up as a bidding strategy. When the roster
    // has no strategy we pass '' through — the display layer renders a quiet '—'
    // (formatBiddingStrategy), never a fabricated value (the plan's api.ts:49 lie).
    biddingStrategy: c.bidding_strategy || '',
    metrics: {
      impressions: c.metrics.impressions,
      clicks,
      ctr: c.metrics.ctr,
      costMicros,
      conversions,
      cpa: conversions > 0 ? costMicros / 1_000_000 / conversions : 0,
    },
  };
}

// ── AdGroup mapper ──────────────────────────────────────────────

interface ApiAdGroup {
  id: string;
  name: string;
  campaign_id: string;
  status: string;
  cpc_bid_micros: number;
  metrics: { impressions: number; clicks: number; cost_micros: number; conversions: number };
}

function mapAdGroup(ag: ApiAdGroup): AdGroup {
  const { impressions, clicks, cost_micros, conversions } = ag.metrics;
  return {
    id: ag.id,
    name: ag.name,
    status: ag.status,
    campaignId: ag.campaign_id,
    metrics: {
      impressions, clicks,
      ctr: impressions > 0 ? clicks / impressions * 100 : 0,
      costMicros: cost_micros, conversions,
      cpa: conversions > 0 ? cost_micros / 1_000_000 / conversions : 0,
    },
  };
}

// ── Keyword mapper ──────────────────────────────────────────────

interface ApiKeyword {
  id: string;
  text: string;
  match_type: string;
  ad_group_id: string;
  ad_group_name: string;
  campaign_id: string;
  status: string;
  quality_score: number | null;
  metrics: { impressions: number; clicks: number; cost_micros: number; conversions: number };
}

function mapKeyword(k: ApiKeyword): Keyword {
  const { impressions, clicks, cost_micros, conversions } = k.metrics;
  return {
    id: k.id,
    text: k.text,
    matchType: k.match_type,
    adGroupName: k.ad_group_name,
    status: k.status,
    qualityScore: k.quality_score,
    metrics: {
      impressions, clicks,
      ctr: impressions > 0 ? clicks / impressions * 100 : 0,
      costMicros: cost_micros, conversions,
      cpa: conversions > 0 ? cost_micros / 1_000_000 / conversions : 0,
    },
  };
}

// ── Ad mapper ───────────────────────────────────────────────────

interface ApiAd {
  id: string;
  ad_group_id: string;
  ad_group_name: string;
  campaign_id: string;
  headlines: string[];
  descriptions: string[];
  final_urls: string[];
  status: string;
  metrics: { impressions: number; clicks: number; cost_micros: number; conversions: number };
}

function mapAd(a: ApiAd): Ad {
  const { impressions, clicks, cost_micros, conversions } = a.metrics;
  return {
    id: a.id,
    headlines: a.headlines,
    descriptions: a.descriptions,
    status: a.status,
    adGroupName: a.ad_group_name,
    metrics: {
      impressions, clicks,
      ctr: impressions > 0 ? clicks / impressions * 100 : 0,
      costMicros: cost_micros, conversions,
      cpa: conversions > 0 ? cost_micros / 1_000_000 / conversions : 0,
    },
  };
}

// ── API Functions ───────────────────────────────────────────────

// Accounts
interface ApiAccount {
  id: string;
  name: string;
  parent_id: string | null;
  level: string;
  is_active: boolean;
}

export async function fetchAccounts(): Promise<ApiAccount[]> {
  return request<ApiAccount[]>('/accounts');
}

// Campaigns
export async function fetchCampaigns(
  accountId: string,
  dateFrom?: string,
  dateTo?: string,
): Promise<Campaign[]> {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  const qs = params.toString();
  const raw = await request<ApiCampaign[]>(`/accounts/${accountId}/campaigns${qs ? `?${qs}` : ''}`);
  return raw.map(mapCampaign);
}

// Campaigns freshness (A3). The /campaigns body is a bare array AND is a
// single-source-of-truth consumed by the Sidebar via the ['campaigns'] key, so
// we do NOT change fetchCampaigns' shape. CONSERVATIVE choice: a companion
// fetcher that reads ONLY the `X-Data-Freshness` response header (JSON) and
// discards the body — exposed under its own ['campaigns-freshness'] key so no
// existing ['campaigns'] consumer is touched. Dev runs through the Vite proxy
// (same-origin), so the header is readable without CORS expose_headers.
export async function fetchCampaignsFreshness(
  accountId: string,
): Promise<FreshnessEnvelope | null> {
  const res = await fetch(`${BASE}/accounts/${accountId}/campaigns`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) return null;
  const header = res.headers.get('X-Data-Freshness');
  if (!header) return null;
  try {
    return JSON.parse(header) as FreshnessEnvelope;
  } catch {
    return null;
  }
}

// Ad Groups
export async function fetchAdGroups(accountId: string, campaignId: string): Promise<AdGroup[]> {
  const raw = await request<ApiAdGroup[]>(`/accounts/${accountId}/campaigns/${campaignId}/adgroups`);
  return raw.map(mapAdGroup);
}

// Keywords
export async function fetchKeywords(accountId: string, campaignId: string): Promise<Keyword[]> {
  const raw = await request<ApiKeyword[]>(`/accounts/${accountId}/campaigns/${campaignId}/keywords`);
  return raw.map(mapKeyword);
}

// Ads
export async function fetchAds(accountId: string, campaignId: string): Promise<Ad[]> {
  const raw = await request<ApiAd[]>(`/accounts/${accountId}/campaigns/${campaignId}/ads`);
  return raw.map(mapAd);
}

// Campaign Targeting
export function fetchCampaignTargeting(
  accountId: string,
  campaignId: string,
): Promise<{ locations: string[]; languages: string[] }> {
  return request(`/accounts/${accountId}/campaigns/${campaignId}/targeting`);
}

// ── Campaigns sync (V11 single-source-of-truth — see campaigns_repo.py) ──

export interface CampaignsSyncStatus {
  account_id: string;
  last_synced_at: string | null;
  stale_after_seconds: number;
}

export function fetchCampaignsSyncStatus(accountId: string): Promise<CampaignsSyncStatus> {
  return request<CampaignsSyncStatus>(`/accounts/${accountId}/campaigns-sync-status`);
}

export function forceSyncCampaigns(accountId: string): Promise<{ account_id: string; synced: number; last_synced_at: string | null }> {
  return request(`/accounts/${accountId}/sync/campaigns`, { method: 'POST' });
}

/** Manual metrics sync (A3 "Sync now"): pulls fresh daily metrics from Google
 *  Ads into the local store, then the freshness envelope flips fresh. Callers
 *  should invalidate ['metrics-overview'], ['campaigns'*], ['fix-actions'],
 *  ['account-report-meta'] afterwards so every chip refreshes. */
export function syncAccountNow(
  accountId: string,
): Promise<{ synced_rows: number; campaigns: number; days: number }> {
  return request(`/accounts/${encodeURIComponent(accountId)}/sync`, { method: 'POST' });
}

// ── Studio (higgsfield generation) ─────────────────────────────

export interface HiggsfieldGenerateImageRequest {
  prompt: string;
  model: string;
  aspect_ratios: string[];
  variants_per_aspect: number;
  soul_id?: string;
  account_id?: string;
  campaign_id?: string;
}

export interface StudioJobStatus {
  asset_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'nsfw' | string;
  url: string | null;
  thumbnail_url: string | null;
  prompt: string | null;
  model: string | null;
  aspect_ratio: string | null;
  higgsfield_cdn_url: string | null;
  error_code: string | null;
  error_message: string | null;
  width: number | null;
  height: number | null;
  created_at: string | null;
}

export function studioGenerateImage(body: HiggsfieldGenerateImageRequest): Promise<{ asset_ids: string[] }> {
  return request('/studio/generate-image', { method: 'POST', body: JSON.stringify(body) });
}

export interface HiggsfieldGenerateVideoRequest {
  prompt: string;
  model: string;
  aspect_ratio: string;
  duration_seconds?: number;
  mode?: string;          // Kling: std / pro / 4k
  quality?: string;       // Veo: basic / high / ultra
  submodel?: string;      // Veo: veo-3-1-fast / veo-3-1-preview
  sound?: string;         // Kling: on / off
  soul_id?: string;
  account_id?: string;
  campaign_id?: string;
}

export function studioGenerateVideo(body: HiggsfieldGenerateVideoRequest): Promise<{ asset_id: string }> {
  return request('/studio/generate-video', { method: 'POST', body: JSON.stringify(body) });
}

export interface CostEstimateRequest {
  prompt: string;
  model: string;
  aspect_ratio?: string;
  duration_seconds?: number;
  mode?: string;
  quality?: string;
  soul_id?: string;
}

export interface CostEstimateResponse {
  // Nullable: when a model rejects the params we sent (Veo 3 old
  // needs --input_image; Wan accepts duration as enum strings only),
  // credits will be null and error_code/message carry the upstream
  // explanation. The UI surfaces this inline instead of showing "—".
  credits: number | null;
  credits_exact: number | null;
  error_code?: string | null;
  error_message?: string | null;
  /** Classifies WHY the estimate is null (e.g. "auth" = CLI logged out). */
  error_class?: string | null;
}

export function studioCostEstimate(body: CostEstimateRequest): Promise<CostEstimateResponse> {
  return request('/studio/cost-estimate', { method: 'POST', body: JSON.stringify(body) });
}

export interface BalanceResponse {
  credits: number | null;
  email: string | null;
  plan: string | null;
  extras: Record<string, unknown>;
}

export function studioBalance(): Promise<BalanceResponse> {
  return request<BalanceResponse>('/studio/balance');
}

// ── Studio auth pre-flight (Higgsfield CLI login state) ─────────
// Always 200. logged_in=false + error_class="auth" means the CLI is
// logged out — the UI disables Render and shows a `higgsfield auth
// login` banner instead of clicking users into a guaranteed failure.
export interface StudioAuthStatus {
  logged_in: boolean;
  error_class: string | null;
  message: string | null;
}

export function studioAuthStatus(): Promise<StudioAuthStatus> {
  return request<StudioAuthStatus>('/studio/auth-status');
}

// ── Server-side model catalog (Epic 11 P1) ─────────────────────
// Single source of truth for models + per-model param contracts.
// Ends the FE-hardcoded-list drift; the StudioPanel ModelPicker is
// fed exclusively from this.

export interface StudioModelConstraints {
  aspect_ratios?: string[];
  /** 'enum' = only `durations` values legal (Veo); 'int' = integer
   * seconds up to max_duration (Kling); absent/null = no --duration. */
  duration_type?: 'enum' | 'int' | null;
  durations?: number[];
  max_duration?: number;
  modes?: string[];          // Kling: std / pro / 4k
  qualities?: string[];      // Veo: basic / high / ultra
  submodels?: string[];
  sound?: string[];
  supports_soul?: boolean;
  requires_input_image?: boolean;
}

export interface StudioModelInfo {
  id: string;
  label: string;
  kind: 'image' | 'video' | string;
  tier: 'Best quality' | 'Fast' | 'Budget' | string;
  cost_text: string;
  available: boolean;
  default: boolean;
  constraints: StudioModelConstraints;
  /** Optional catalog provenance (e.g. "Chinese" / "American" / "Soul"). */
  origin?: string;
  /** Optional short model-strength note surfaced in the gallery. */
  strengths?: string;
}

export interface ModelCatalogResponse {
  models: StudioModelInfo[];
  source: 'live' | 'static' | string;
}

export function studioListModels(kind?: 'image' | 'video'): Promise<ModelCatalogResponse> {
  const qs = kind ? `?kind=${kind}` : '';
  return request<ModelCatalogResponse>(`/studio/models${qs}`);
}

export interface SoulCharacter {
  id: string;
  account_id: string;
  name: string;
  soul_id: string | null;
  training_model: 'soul-2' | 'soul-cinematic' | string;
  status: 'pending' | 'training' | 'ready' | 'failed' | string;
  reference_image_paths: string[] | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  ready_at: string | null;
}

export function studioListSouls(accountId?: string): Promise<SoulCharacter[]> {
  const qs = accountId ? `?account_id=${encodeURIComponent(accountId)}` : '';
  return request<SoulCharacter[]>(`/studio/soul${qs}`);
}

export function studioGetSoul(soulPk: string): Promise<SoulCharacter> {
  return request<SoulCharacter>(`/studio/soul/${soulPk}`);
}

export interface MarketingHook {
  id: string;
  name: string;
  type: string | null;
  prompt: string;
  thumbnail_url: string | null;
  video_url: string | null;
  is_pinned: boolean;
  source: string | null;
}

export function studioListMarketingHooks(): Promise<MarketingHook[]> {
  return request<MarketingHook[]>('/studio/marketing-studio/hooks');
}

// Landing-page brief extraction. Operator pastes a campaign's landing
// URL → backend fetches the page, Claude drafts on-brand creative
// prompts (3 angle variants). The picked variant flows into the
// StudioPanel prompt field.
export interface BriefVariant {
  angle: 'problem-led' | 'aspirational' | 'social-proof' | string;
  prompt: string;
  rationale: string;
}

export interface DecomposedBrief {
  subject: string;
  setting: string;
  value_prop: string;
  audience: string;
  tone: string;
  program: string;
  hard_constraints: string[];
  claim_hints: string[];
}

export interface ExtractBriefResponse {
  url: string;
  final_url: string;
  title: string | null;
  description: string | null;
  h1: string | null;
  body_excerpt: string | null;
  og: Record<string, string>;
  brief: DecomposedBrief | null;
  variants: BriefVariant[];
  pinned_claims_used: string[];
  /** Back-compat alias for the first variant's prompt. */
  drafted_prompt: string;
}

export interface ExtractBriefRequest {
  /** Landing page to fetch + decompose. Either this or `context`. */
  url?: string;
  /** Inline rough idea + campaign context (PMax wizard slots) — runs
   * the same 2-stage Visual Director drafter without a page fetch. */
  context?: string;
  target: 'image' | 'video';
  /** Optional — when provided, the drafter loads the campaign's
   * pinned_facts.md and grounds the social-proof variant in
   * operator-verified claims. */
  account_id?: string;
  campaign_id?: string;
}
export function studioExtractBrief(body: ExtractBriefRequest): Promise<ExtractBriefResponse> {
  return request<ExtractBriefResponse>('/studio/extract-brief', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/**
 * Train a new Soul. FormData because we're uploading 5-20 reference
 * images. The endpoint returns immediately with status=pending; poll
 * studioGetSoul or refresh the list to watch the state machine.
 */
export async function studioTrainSoul(args: {
  accountId: string;
  name: string;
  trainingModel: 'soul-2' | 'soul-cinematic';
  images: File[];
}): Promise<SoulCharacter> {
  const fd = new FormData();
  fd.append('name', args.name);
  fd.append('account_id', args.accountId);
  fd.append('training_model', args.trainingModel);
  for (const f of args.images) fd.append('images', f);
  const r = await fetch('/api/studio/soul/train', { method: 'POST', body: fd });
  if (!r.ok) {
    const txt = await r.text();
    throw new Error(`Soul training failed (${r.status}): ${txt.slice(0, 300)}`);
  }
  return r.json();
}

export function studioGetJob(assetId: string): Promise<StudioJobStatus> {
  return request<StudioJobStatus>(`/studio/jobs/${assetId}`);
}

// ── Video Engine (Epic 11 P2) — segment-timeline renders ────────
// One request = ordered segments (intro/body/outro), each tagged
// with an engine: storyboard (free hyperframes scenes) | higgsfield
// (one AI clip) | soul (Soul presenter — motion + VO, NO lip-sync).

export interface VideoEngineSegment {
  engine: 'storyboard' | 'higgsfield' | 'soul' | string;
  /** storyboard — hyperframes scenes, verbatim. */
  scenes?: object[];
  /** higgsfield — one generated clip. */
  prompt?: string;
  model?: string;
  duration?: number;
  speak?: string;
  /** soul — presenter clip from a trained Soul (non-lipsync). */
  soul_id?: string;
  soul_character_id?: string;
  script?: string;
  look_prompt?: string;
}

export interface VideoEngineEstimate {
  /** Sum of the estimates the CLI could price (cached clips = 0). */
  total_credits: number;
  /** Lookups the CLI couldn't answer — total above is partial. */
  unknown_count: number;
  cached_hits: number;
  items: { kind: string; model: string; credits: number | null; cached: boolean; note?: string | null }[];
}

export function videoEngineEstimate(body: {
  segments?: VideoEngineSegment[];
  scenes?: object[];
  aspect?: string;
  /** "Finished video" mode — the backend planner derives N clips from
   * a target length + model + prompt and sums their per-clip cost, so
   * no hand-built segments are needed. */
  target_seconds?: number;
  model_id?: string;
  prompt?: string;
}): Promise<VideoEngineEstimate> {
  return request<VideoEngineEstimate>('/video-engine/estimate', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function videoEngineRender(body: {
  account_id: string;
  /** Explicit segment timeline (talking-intro flow). Omit when the
   * planner should build the clips from target_seconds/model_id/prompt. */
  segments?: VideoEngineSegment[];
  voice_id?: string;
  music_filename?: string;
  quality?: string;
  aspect?: string;
  campaign_id?: string;
  brief?: string;
  /** "Finished video" mode — planner-built clips. */
  target_seconds?: number;
  model_id?: string;
  prompt?: string;
  /** VO script the backend TTS sizes to the finished video. NOTE: needs
   * the backend render endpoint to consume it (coordination point). */
  voiceover_script?: string;
}): Promise<{ job_id: string; status: string }> {
  return request('/video-engine/render', { method: 'POST', body: JSON.stringify(body) });
}

export interface VideoEngineRenderJob {
  status: 'running' | 'done' | 'error' | string;
  stage?: string;
  message?: string;
  asset_id?: string;
  url?: string;
  duration?: number;
  scene_count?: number;
}

export function videoEngineRenderStatus(jobId: string): Promise<VideoEngineRenderJob> {
  return request<VideoEngineRenderJob>(`/video-engine/render/${jobId}`);
}

// ── AI Video Studio — video projects + brand avatars (Epic B/C4) ──

export interface StoryboardScene { n: number; duration: number; visual_prompt: string; vo_line: string; on_screen_text?: string | null; continuity?: string; model?: string }
export interface Storyboard { scenes: StoryboardScene[]; vo_full?: string; music_mood?: string; title?: string; version?: number }
export interface VideoProject { id: string; account_id: string; campaign_id: string | null; conversation_id: string; title: string; brief: string; model_id: string; target_seconds: number; aspect: string; consult_director: number; storyboard_json: Storyboard | null; status: string; asset_id: string | null; created_at: string; updated_at: string }
export interface BrandAvatar { id: string; account_id: string; name: string; soul_id: string | null; voice_id: string | null; style_notes?: string; created_at: string }

export function createVideoProject(body: { account_id: string; campaign_id?: string | null; campaign_name?: string; title?: string; brief?: string; model_id: string; target_seconds: number; aspect?: string; consult_director?: number | null }): Promise<VideoProject> { return request('/studio/video-projects', { method: 'POST', body: JSON.stringify(body) }); }
/** Where the Director sources the brief from. Omitted == "text" (legacy). */
export interface BriefSource { type: 'text' | 'campaign' | 'landing_page'; url?: string }
export function draftVideoProject(id: string, message?: string, briefSource?: BriefSource): Promise<{ turn_id: string }> { return request(`/studio/video-projects/${id}/draft`, { method: 'POST', body: JSON.stringify({ message, ...(briefSource ? { brief_source: briefSource } : {}) }) }); }
export function patchVideoProject(id: string, patch: Partial<{ title: string; brief: string; model_id: string; target_seconds: number; aspect: string; consult_director: number; storyboard_json: Storyboard | Record<string, unknown> | string; status: string; asset_id: string | null; campaign_id: string | null }>): Promise<VideoProject> { return request(`/studio/video-projects/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }); }
export function getVideoProject(id: string): Promise<VideoProject> { return request(`/studio/video-projects/${id}`); }
export function listVideoProjects(accountId: string): Promise<Partial<VideoProject>[]> { return request(`/studio/video-projects?account_id=${encodeURIComponent(accountId)}`); }
export function listBrandAvatars(accountId: string): Promise<BrandAvatar[]> { return request(`/studio/brand-avatars?account_id=${encodeURIComponent(accountId)}`); }

// ── Operations (direct campaign actions) ────────────────────────

export function updateCampaignStatus(customerId: string, campaignId: string, status: 'ENABLED' | 'PAUSED'): Promise<{ status: string }> {
  return request('/operations/campaign/status', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, campaign_id: campaignId, status }),
  });
}

export function updateCampaignBudget(customerId: string, campaignId: string, budgetMicros: number): Promise<{ status: string }> {
  return request('/operations/campaign/budget', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, campaign_id: campaignId, budget_micros: budgetMicros }),
  });
}

export function addKeyword(customerId: string, campaignId: string, adGroupId: string, keywordText: string, matchType: string = 'EXACT'): Promise<{ status: string }> {
  return request('/operations/keyword/add', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, campaign_id: campaignId, ad_group_id: adGroupId, keyword_text: keywordText, match_type: matchType }),
  });
}

export function updateKeywordStatus(customerId: string, keywordCriterionId: string, adGroupId: string, status: 'ENABLED' | 'PAUSED'): Promise<{ status: string }> {
  return request('/operations/keyword/status', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, keyword_criterion_id: keywordCriterionId, ad_group_id: adGroupId, status }),
  });
}

export function addNegativeKeyword(customerId: string, campaignId: string, keywordText: string, matchType: string = 'EXACT'): Promise<{ status: string }> {
  return request('/operations/campaign/negative-keyword', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, campaign_id: campaignId, keyword_text: keywordText, match_type: matchType }),
  });
}

export function fetchSearchTerms(customerId: string, campaignId: string, dateFrom: string, dateTo: string): Promise<Array<{
  search_term: string; status: string; campaign_id: string; ad_group_id: string; ad_group_name: string;
  impressions: number; clicks: number; cost_micros: number; conversions: number;
}>> {
  return request('/operations/search-terms', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId, campaign_id: campaignId, date_from: dateFrom, date_to: dateTo }),
  });
}

// Guidelines
export function fetchGuidelines(): Promise<GuidelineFile[]> {
  return request<GuidelineFile[]>('/guidelines');
}

export function fetchGuidelineContent(filename: string): Promise<string> {
  return fetch(`${BASE}/guidelines/${encodeURIComponent(filename)}`).then((r) => r.text());
}

export function saveGuidelineContent(filename: string, content: string): Promise<void> {
  return request<void>(`/guidelines/${encodeURIComponent(filename)}`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

// Conversations
export function fetchConversations(accountId?: string, campaignId?: string): Promise<Conversation[]> {
  const params = new URLSearchParams();
  if (accountId) params.set('account_id', accountId);
  if (campaignId) params.set('campaign_id', campaignId);
  const qs = params.toString();
  return request<Conversation[]>(`/conversations${qs ? `?${qs}` : ''}`).then((convs) =>
    convs.map((c: any) => ({
      id: c.id,
      accountId: c.account_id || '',
      campaignId: c.campaign_id,
      campaignName: c.campaign_name,
      title: c.title,
      createdAt: c.created_at || '',
      updatedAt: c.updated_at || '',
      messageCount: c.message_count || 0,
    }))
  );
}

/** Authoritative single-conversation lookup. Resolves null if it no longer
 *  exists. Used to verify a thread's campaign binding before reusing it. */
export function fetchConversation(id: string): Promise<Conversation | null> {
  return request<any>(`/conversations/${id}`)
    .then((c) => ({
      id: c.id,
      accountId: c.account_id || '',
      campaignId: c.campaign_id ?? null,
      campaignName: c.campaign_name ?? null,
      title: c.title,
      createdAt: c.created_at || '',
      updatedAt: c.updated_at || '',
      messageCount: c.message_count || 0,
    }))
    .catch(() => null);
}

export function createConversation(data: { account_id?: string; campaign_id?: string; campaign_name?: string; title?: string }): Promise<Conversation> {
  return request<any>('/conversations', { method: 'POST', body: JSON.stringify(data) }).then((c) => ({
    id: c.id,
    accountId: c.account_id || '',
    campaignId: c.campaign_id,
    campaignName: c.campaign_name,
    title: c.title,
    createdAt: c.created_at || '',
    updatedAt: c.updated_at || '',
    messageCount: 0,
  }));
}

export function deleteConversation(conversationId: string): Promise<{ deleted: boolean }> {
  return request(`/conversations/${conversationId}`, { method: 'DELETE' });
}

export function deleteMessage(conversationId: string, messageId: string): Promise<{ deleted: boolean }> {
  return request(`/conversations/${conversationId}/messages/${messageId}`, { method: 'DELETE' });
}

export function stopAgentTask(conversationId: string): Promise<{ stopped: boolean }> {
  return request(`/conversations/${conversationId}/stop`, { method: 'POST' });
}

// ── Chat Orchestration v2 — turn API (Epic 3, stories 3.1/3.2/3.4) ──────────

/** Per-turn stop (story 1.5 endpoint). Idempotent — a terminal turn returns
 *  `{status:"already_done"}`. */
export function stopTurn(conversationId: string, turnId: string): Promise<{ status?: string }> {
  return request(`/conversations/${conversationId}/turns/${turnId}/stop`, { method: 'POST' });
}

/** Per-specialist stop (story 2.6 endpoint). Kills exactly one running call. */
export function stopTurnCall(
  conversationId: string,
  turnId: string,
  callId: string,
): Promise<{ status?: string }> {
  return request(
    `/conversations/${conversationId}/turns/${turnId}/calls/${callId}/stop`,
    { method: 'POST' },
  );
}

/** History replay: the full persisted event list for a past orchestrated turn
 *  (story 3.2). Returns v2 envelopes in seq order. */
export function fetchTurnEvents(
  conversationId: string,
  turnId: string,
): Promise<import('@/types/orchestration').OrchestrationEvent[]> {
  return request(`/conversations/${conversationId}/turns/${turnId}/events`);
}

/** Reconnect: any active turn(s) for a conversation (story 1.6). Shape kept
 *  loose — the backend returns turn headers we resubscribe to by cursor. */
export function fetchActiveTurns(
  conversationId: string,
): Promise<{ turn_id: string; cursor?: number; mode?: string }[]> {
  return request(`/conversations/${conversationId}/turns/active`);
}

/** Two-step orchestrated send (stories 3.1/3.2). POST /message with
 *  `orchestrate:true` returns JSON `{turn_id}` immediately (NOT a stream); the
 *  caller then opens the turn SSE via `streamTurn`. The direct-mode send path
 *  (ChatPanel.actualSend) is untouched — this is ONLY used when the toggle is ON.
 *  `body` carries the same fields the direct POST sends (content/account_id/
 *  campaign_id/campaign_name/model/active_role/attachments) plus the orchestrate
 *  flag. // backend field: orchestrate */
export async function startTurn(
  conversationId: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<{ turn_id: string }> {
  const res = await fetch(`${BASE}/conversations/${conversationId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    // backend field: orchestrate — the agreed toggle name for force-orchestrate.
    body: JSON.stringify({ ...body, orchestrate: true }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json() as Promise<{ turn_id: string }>;
}

/** Open the turn SSE viewer (story 3.1). Replays from `cursor` then tails; the
 *  detached run is never killed by closing this stream. Uses the shared
 *  `parseSse` util — no 4th hand-rolled parser. `onEvent` receives each raw v2
 *  envelope; the caller applies its own identity guard inside `onEvent`. */
export async function streamTurn(
  conversationId: string,
  turnId: string,
  cursor: number,
  opts: {
    onEvent: (event: import('@/types/orchestration').OrchestrationEvent) => void;
    signal?: AbortSignal;
  },
): Promise<void> {
  const { parseSse } = await import('@/lib/parseSse');
  const res = await fetch(
    `${BASE}/conversations/${conversationId}/turns/${turnId}/stream?cursor=${cursor}`,
    { signal: opts.signal },
  );
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  await parseSse(res, {
    onEvent: (ev) => opts.onEvent(ev as import('@/types/orchestration').OrchestrationEvent),
    signal: opts.signal,
  });
}

export function searchConversations(query: string, accountId?: string): Promise<import('@/types').ConversationSearchResult[]> {
  const params = new URLSearchParams({ q: query });
  if (accountId) params.set('account_id', accountId);
  return request(`/conversations/search?${params.toString()}`);
}

export function fetchMessages(conversationId: string): Promise<import('@/types').ChatMessage[]> {
  return request<any[]>(`/conversations/${conversationId}/messages`).then((msgs) =>
    msgs.map((m) => ({
      id: m.id,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      toolCalls: m.tool_input ? JSON.parse(m.tool_input) : undefined,
      createdAt: m.created_at || '',
      agentRole: m.agent_role || undefined,
      agentRoleName: m.agent_role_name || undefined,
      // v2: a persisted turn_id means this bubble is an orchestrated turn —
      // ChatMessage lazily hydrates its ledger from /turns/{id}/events.
      turnId: m.turn_id || undefined,
    }))
  );
}

export async function sendMessage(conversationId: string, content: string): Promise<ReadableStream<Uint8Array> | null> {
  // ?stream=1 restores the pre-v2 legacy streaming contract: the backend now
  // defaults to JSON `{turn_id}` (detached turn) and only emits the legacy
  // StreamingResponse when this flag is present. Without it the reader in
  // actualSend consumes a ~30-byte JSON body, gets no frames, and spins forever.
  const res = await fetch(`${BASE}/conversations/${conversationId}/message?stream=1`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.body;
}

// Setup
export function fetchSetupStatus(): Promise<{ configured: boolean }> {
  return request('/setup/status');
}

// ── V2: Multi-Account API ──────────────────────────────────────────

export function fetchAccountsV2(): Promise<AccountV2[]> {
  return request<AccountV2[]>('/v2/accounts');
}

export function fetchDashboard(): Promise<DashboardData> {
  return request<DashboardData>('/v2/dashboard');
}

export function addAccount(data: {
  developer_token: string;
  client_id: string;
  client_secret: string;
  refresh_token: string;
  login_customer_id: string;
}): Promise<AccountV2> {
  return request<AccountV2>('/v2/accounts', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function removeAccount(accountId: string): Promise<{ deleted: boolean }> {
  return request(`/v2/accounts/${accountId}`, { method: 'DELETE' });
}

export function onboardAccount(accountId: string): Promise<OnboardingResult> {
  return request<OnboardingResult>(`/v2/accounts/${accountId}/onboard`, {
    method: 'POST',
  });
}

export function fetchAlerts(accountId: string): Promise<Alert[]> {
  return request<Alert[]>(`/v2/accounts/${accountId}/alerts`);
}

export function dismissAlert(accountId: string, alertId: number): Promise<{ dismissed: boolean }> {
  return request(`/v2/accounts/${accountId}/alerts/${alertId}/dismiss`, { method: 'POST' });
}

export function fetchCampaignGoals(accountId: string, campaignId: string): Promise<CampaignGoal> {
  return request<CampaignGoal>(`/v2/accounts/${accountId}/campaigns/${campaignId}/goals`);
}

// ── V2: Chart Data ─────────────────────────────────────────────

export interface DailyMetric {
  date: string;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  ctr: number;
  cpc: number;
  cpa: number;
}

export function fetchCampaignChart(
  accountId: string,
  campaignId: string,
  dateFrom?: string,
  dateTo?: string,
): Promise<DailyMetric[]> {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  const qs = params.toString();
  return request<DailyMetric[]>(`/accounts/${accountId}/campaigns/${campaignId}/chart${qs ? `?${qs}` : ''}`);
}

export function fetchAccountChart(
  accountId: string,
  dateFrom?: string,
  dateTo?: string,
): Promise<DailyMetric[]> {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  const qs = params.toString();
  return request<DailyMetric[]>(`/accounts/${accountId}/chart${qs ? `?${qs}` : ''}`);
}

// ── Period-over-period account metrics (Epic 13, Story 13.7/13.8) ──
// Purpose-built rollup for the homepage KPI cards: current window vs the
// immediately-preceding equal window, plus a per-day series for sparklines.
// Local SQLite only (no live Google Ads calls). Replaces the KpiCards'
// former manual two-fetch rollup of fetchAccountChart.
//
// Contract (backend, verified via curl 2026-07-04):
//   delta_pct is null when the prior window is empty/zero — NEVER fabricate a
//   delta in that case. conv_rate is a FRACTION (0.0358 = 3.58%). A series
//   day's cpa can be null (spend but no conversions).

/** One metric's current value + prior value + % change. */
export interface MetricPoint {
  value: number | null;
  prev_value: number | null;
  /** null when prior=0/empty — render no delta, don't invent one. */
  delta_pct: number | null;
}

export interface MetricsSeriesDay {
  date: string;
  spend: number | null;
  conversions: number | null;
  cpa: number | null;
  /** fraction (0.0358 = 3.58%). */
  conv_rate: number | null;
}

export interface MetricsOverview {
  account_id: string;
  days: number;
  window: { start: string; end: string };
  prev_window: { start: string; end: string };
  metrics: {
    spend: MetricPoint;
    conversions: MetricPoint;
    cpa: MetricPoint;
    conv_rate: MetricPoint;
  };
  series: MetricsSeriesDay[];
  /** Data-age envelope (A3). Absent on older backends → treat as unknown. */
  freshness?: FreshnessEnvelope;
}

export function fetchMetricsOverview(
  accountId: string,
  days: number,
): Promise<MetricsOverview> {
  return request<MetricsOverview>(
    `/accounts/${encodeURIComponent(accountId)}/metrics/overview?days=${days}`,
  );
}

// ── Settings ──────────────────────────────────────────────

export interface AppSettings {
  chrome_mcp_enabled: boolean;
  chrome_reuse_existing: boolean;
  chrome_use_default_profile: boolean;
  chrome_debug_port: number;
  gtm_mcp_enabled: boolean;
  gtm_mcp_command: string;
  google_ads_configured: boolean;
  google_ads_login_customer_id: string;
  mcp_status: Record<string, {
    enabled: boolean;
    available?: boolean;
    tools?: string;
    info?: string;
    path?: string;
    reason?: string;
  }>;
}

export async function fetchSettings(): Promise<AppSettings> {
  return request<AppSettings>('/settings');
}

export async function updateSettings(data: {
  chrome_mcp_enabled?: boolean;
  chrome_reuse_existing?: boolean;
  chrome_use_default_profile?: boolean;
  gtm_mcp_enabled?: boolean;
  gtm_mcp_command?: string;
}): Promise<{ status: string; mcp_status: Record<string, unknown> }> {
  const res = await fetch('/api/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Settings update failed: ${res.status}`);
  return res.json();
}

// ── Landing Page Analyzer ────────────────────────────────────────

export interface CategoryScore {
  score: number;
  grade: string;
  findings: string[];
}

export interface Recommendation {
  priority: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  category: string;
  expected_impact?: string;
  effort?: string;
}

export interface ABTestIdea {
  hypothesis: string;
  expected_impact: string;
  effort: string;
  category: string;
}

export interface CompetitorInsight {
  competitor: string;
  strengths?: string[];
  weaknesses?: string[];
  ideas_to_steal?: string[];
}

export interface AdStrengthAnalysis {
  current_rating?: string;
  headlines_count?: number;
  descriptions_count?: number;
  missing?: string[];
  suggested_headlines?: string[];
  suggested_descriptions?: string[];
}

export interface LandingPageAnalysis {
  url: string;
  analyzed_at: string;
  cro_score: number;
  grade: string;
  executive_summary: string;
  categories: Record<string, CategoryScore>;
  critical_issues?: Array<{ title: string; category: string; impact: string; fix: string }>;
  recommendations: Recommendation[];
  ab_test_ideas: ABTestIdea[];
  competitor_insights?: CompetitorInsight[];
  ad_strength_analysis?: AdStrengthAnalysis;
}

export interface LandingPageAnalysisResponse {
  analysis: LandingPageAnalysis | null;
  raw_markdown: string;
  has_data: boolean;
}

export function fetchLandingPageAnalysis(
  accountId: string,
  campaignId: string,
): Promise<LandingPageAnalysisResponse> {
  return request<LandingPageAnalysisResponse>(`/accounts/${accountId}/campaigns/${campaignId}/landing-page/analysis`);
}

export function clearLandingPageAnalysis(
  accountId: string,
  campaignId: string,
): Promise<{ deleted: boolean }> {
  return request(`/accounts/${accountId}/campaigns/${campaignId}/landing-page/analysis`, { method: 'DELETE' });
}

// ── Roles (specialist personas) ──────────────────────────────────

export interface AgencyRoleSummary {
  id: string;
  name: string;
  avatar: string;
  specialty: string;
  customized?: boolean;
}

export interface AgencyRoleDetail {
  id: string;
  name: string;
  avatar: string;
  specialty: string;
  system_prompt: string;
  tools_focus?: string[];
  context_needs?: string[];
}

export function fetchRoles(): Promise<{ roles: AgencyRoleSummary[] }> {
  return request('/roles');
}

export function fetchRoleDetail(roleId: string): Promise<AgencyRoleDetail> {
  return request(`/roles/${roleId}`);
}

export function customizeRole(
  roleId: string,
  updates: Partial<AgencyRoleDetail>,
): Promise<{ status: string; role_id: string }> {
  return request(`/roles/${roleId}/customize`, {
    method: 'POST',
    body: JSON.stringify(updates),
  });
}

export function resetRole(roleId: string): Promise<{ status: string; role_id: string }> {
  return request(`/roles/${roleId}/customize`, { method: 'DELETE' });
}

// ── Scheduled Plans ──────────────────────────────────────────────

export type PlanStatus =
  | 'scheduled' | 'due' | 'running' | 'awaiting_approval' | 'done' | 'failed' | 'paused';
export type PlanActionCategory =
  | 'budget' | 'bids' | 'status' | 'geo' | 'search_terms' | 'audit' | 'report' | 'other';
export type PlanMode = 'auto' | 'approval';
export type PlanScheduleType = 'once' | 'recurring';

export interface PlanRun {
  id: string;
  plan_id: string;
  status: string;
  result?: string | null;
  cost?: number | null;
  created_at: string;
  ran_at?: string | null;
}

export interface Plan {
  id: string;
  account_id: string;
  campaign_id?: string | null;
  campaign_name?: string | null;
  conversation_id?: string | null;
  status: PlanStatus;
  title: string;
  action_detail: string;
  action_category: PlanActionCategory;
  mode: PlanMode;
  schedule_type: PlanScheduleType;
  run_at?: string | null;
  recurrence?: string | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  last_result?: string | null;
  last_cost?: number | null;
  proposed_change?: string | null;
  context_snippet?: string | null;
  run_count?: number;
  timezone?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  runs?: PlanRun[];
}

export interface CreatePlanBody {
  account_id: string;
  campaign_id?: string | null;
  campaign_name?: string | null;
  conversation_id?: string | null;
  title: string;
  action_detail: string;
  action_category: PlanActionCategory;
  mode?: PlanMode;
  schedule_type: PlanScheduleType;
  run_at?: string | null;
  recurrence?: string | null;
  timezone?: string;
  context_snippet?: string | null;
}

export interface UpdatePlanBody {
  title?: string;
  action_detail?: string;
  action_category?: PlanActionCategory;
  mode?: PlanMode;
  run_at?: string | null;
  recurrence?: string | null;
  status?: PlanStatus;
}

export interface PlanDraft {
  title: string;
  action_detail: string;
  action_category: PlanActionCategory;
  suggested_run_at?: string | null;
  recurrence?: string | null;
  mode?: PlanMode;
}

export function createPlan(body: CreatePlanBody): Promise<Plan> {
  return request<Plan>('/plans', { method: 'POST', body: JSON.stringify(body) });
}

export function fetchPlans(accountId: string, campaignId?: string): Promise<Plan[]> {
  const params = new URLSearchParams({ account_id: accountId });
  if (campaignId) params.set('campaign_id', campaignId);
  return request<Plan[]>(`/plans?${params.toString()}`);
}

export function fetchUpcomingPlans(accountId: string): Promise<Plan[]> {
  return request<Plan[]>(`/plans/upcoming?account_id=${encodeURIComponent(accountId)}`);
}

export function fetchPlan(id: string): Promise<Plan> {
  return request<Plan>(`/plans/${id}`);
}

export function updatePlan(id: string, body: UpdatePlanBody): Promise<Plan> {
  return request<Plan>(`/plans/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
}

export function deletePlan(id: string): Promise<{ deleted: boolean }> {
  return request(`/plans/${id}`, { method: 'DELETE' });
}

export function approvePlan(id: string): Promise<Plan> {
  return request<Plan>(`/plans/${id}/approve`, { method: 'POST' });
}

export function skipPlan(id: string): Promise<Plan> {
  return request<Plan>(`/plans/${id}/skip`, { method: 'POST' });
}

export function snoozePlan(id: string, hours = 24): Promise<Plan> {
  return request<Plan>(`/plans/${id}/snooze?hours=${hours}`, { method: 'POST' });
}

export function runPlanNow(id: string): Promise<Plan> {
  return request<Plan>(`/plans/${id}/run-now`, { method: 'POST' });
}

export interface ExtractPlanBody {
  account_id: string;
  campaign_id?: string | null;
  campaign_name?: string | null;
  text: string;
}

export function extractPlan(body: ExtractPlanBody): Promise<PlanDraft> {
  return request<PlanDraft>('/plans/extract', { method: 'POST', body: JSON.stringify(body) });
}

export async function launchChrome(): Promise<{ status: string; message?: string; profile_dir?: string }> {
  const res = await fetch('/api/settings/chrome/launch', { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Launch failed' }));
    throw new Error(err.detail || 'Launch failed');
  }
  return res.json();
}

export async function stopChrome(): Promise<{ status: string }> {
  const res = await fetch('/api/settings/chrome/stop', { method: 'POST' });
  if (!res.ok) throw new Error('Stop failed');
  return res.json();
}

// ── Account Director fix list (Epic 13) ──────────────────────────
// The homepage "Needs attention" strip: the latest persisted account audit +
// always-fresh fast signals, each surfaced as a money-ranked, approvable
// ACTION. Shapes mirror backend/app/services/finding_actions.py and
// account_report_store.py exactly (do NOT drift from the real contract).

/** One row in the fix list — a finding/fast-signal turned into a proposed
 *  action, annotated with its decision state. Sorted by `dollar_impact_wk`
 *  desc by the server; unquantified/advisory items sink below. */
export interface FixAction {
  finding_key: string;
  source: 'finding' | 'signal';
  title: string;
  detail: string;
  action_category: PlanActionCategory | 'negative_keyword';
  campaign_ids: string[];
  campaign_name?: string | null;
  /** null = unquantified (render "--", excluded from recoverable total). */
  dollar_impact_wk: number | null;
  /** false = advisory: show `advisory_reason` inline, NO Approve buttons. */
  actionable: boolean;
  advisory_reason?: string | null;
  /** 'approval' = gated (needs sign-off); 'auto' = fires now on approve. */
  mode: PlanMode;
  requires_approval: boolean;
  mutation?: string | null;
  diff_preview: string;
  /** decision state; 'proposed' = undecided. */
  status: 'proposed' | 'approved' | 'approved_once' | 'denied';
  plan_id?: string | null;
}

export interface FixActionsResponse {
  account_id: string;
  actions: FixAction[];
  count: number;
  actionable_count: number;
  advisory_count: number;
  total_recoverable_wk: number;
}

export type FixDecision = 'approve' | 'approve_once' | 'deny';

export interface FixDecisionResult {
  status?: 'approved' | 'approved_once' | 'denied';
  finding_key: string;
  plan_id?: string | null;
  mode?: PlanMode;
  gated?: boolean;
  requires_approval?: boolean;
  fired?: boolean;
  error?: string;
  advisory_reason?: string | null;
}

/** Latest account audit meta + staleness (account_report_store.get_latest). */
export interface AccountReportMeta {
  account_id: string;
  exists: boolean;
  run_id?: string | null;
  summary?: string;
  total_recoverable_wk?: number;
  campaigns_audited?: string[];
  campaigns_excluded?: string[];
  generated_at?: string | null;
  age_minutes?: number | null;
  age_hours?: number | null;
  is_stale?: boolean;
  stale_after_hours?: number;
}

export interface AccountReportResponse {
  account_id: string;
  report: AccountReportMeta;
  /** Data-age envelope (A3), sibling to `report`. Absent on older backends. */
  freshness?: FreshnessEnvelope;
}

export function fetchFixActions(
  accountId: string,
  includeDenied = false,
): Promise<FixActionsResponse> {
  const q = includeDenied ? '?include_denied=true' : '';
  return request<FixActionsResponse>(`/accounts/${encodeURIComponent(accountId)}/actions${q}`);
}

export function decideFixAction(
  accountId: string,
  findingKey: string,
  decision: FixDecision,
): Promise<FixDecisionResult> {
  return request<FixDecisionResult>(
    `/accounts/${encodeURIComponent(accountId)}/actions/${encodeURIComponent(findingKey)}/decide`,
    { method: 'POST', body: JSON.stringify({ decision }) },
  );
}

/** Report meta only (staleness label + zero-state). Skips the fast-signals
 *  payload the actions endpoint already folds in. */
export function fetchAccountReportMeta(accountId: string): Promise<AccountReportResponse> {
  return request<AccountReportResponse>(
    `/accounts/${encodeURIComponent(accountId)}/account-report?include_signals=false`,
  );
}

// ── Outcome tracking (Epic 13, Story 13.8 change log) ────────────
// The homepage Agent-activity change log reads the `recommendations`
// baseline snapshots here: each executed recommendation, with a measured
// before→after `delta` once its post-window lands (outcome_tracker.py).
// Rendered READ-ONLY — no revert endpoint exists, so we never show an
// Undo that would 404. Shapes mirror get_outcome_dashboard() (verified
// via curl 2026-07-04).

/** before→after snapshot for a measured recommendation. Absent fields stay
 *  undefined; the whole object is null until the outcome is measured. */
export interface OutcomeDelta {
  cpa_before?: number | null;
  cpa_after?: number | null;
  ctr_before?: number | null;
  ctr_after?: number | null;
  conversions_before?: number | null;
  conversions_after?: number | null;
  cpa_change_pct?: number | null;
}

export interface OutcomeRecord {
  id: string;
  campaign_id: string | null;
  action_type: string;
  action_detail: string;
  /** 'improved' | 'degraded' | 'no_change' | null (null = not yet measured). */
  outcome: 'improved' | 'degraded' | 'no_change' | null;
  delta: OutcomeDelta | null;
  executed_at: string | null;
  measured_at: string | null;
}

export interface OutcomeDashboard {
  total_recommendations: number;
  measured: number;
  pending: number;
  improved: number;
  degraded: number;
  no_change: number;
  success_rate: number;
  top_actions: unknown[];
  recent: OutcomeRecord[];
}

export function fetchOutcomes(accountId: string): Promise<OutcomeDashboard> {
  return request<OutcomeDashboard>(`/accounts/${encodeURIComponent(accountId)}/outcomes`);
}
