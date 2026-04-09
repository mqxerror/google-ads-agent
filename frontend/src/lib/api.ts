import type {
  Campaign,
  AdGroup,
  Keyword,
  Ad,
  GuidelineFile,
  Conversation,
  AccountV2,
  AccountHealth,
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
    biddingStrategy: c.bidding_strategy || c.campaign_type,
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
    }))
  );
}

export async function sendMessage(conversationId: string, content: string): Promise<ReadableStream<Uint8Array> | null> {
  const res = await fetch(`${BASE}/conversations/${conversationId}/message`, {
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
