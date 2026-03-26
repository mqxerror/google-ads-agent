import type {
  Campaign,
  AdGroup,
  Keyword,
  Ad,
  GuidelineFile,
  Conversation,
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
export function fetchConversations(): Promise<Conversation[]> {
  return request<Conversation[]>('/conversations');
}

export function createConversation(data: { account_id?: string; campaign_id?: string; title?: string }): Promise<Conversation> {
  return request<Conversation>('/conversations', { method: 'POST', body: JSON.stringify(data) });
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
