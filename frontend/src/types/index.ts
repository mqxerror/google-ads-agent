// Account
export interface Account {
  id: string;
  name: string;
  parentId: string | null;
  level: 'manager' | 'sub_manager' | 'client';
  isActive: boolean;
  children?: Account[];
  campaigns?: Campaign[];
}

// Campaign
export interface Campaign {
  id: string;
  name: string;
  status: 'ENABLED' | 'PAUSED' | 'REMOVED';
  channelType: string;
  budgetAmountMicros: number;
  biddingStrategy: string;
  metrics: CampaignMetrics;
}

export interface CampaignMetrics {
  impressions: number;
  clicks: number;
  ctr: number;
  costMicros: number;
  conversions: number;
  cpa: number;
}

// Ad Groups, Keywords, Ads
export interface AdGroup {
  id: string;
  name: string;
  status: string;
  campaignId: string;
  keywordCount?: number;
  adCount?: number;
  metrics: CampaignMetrics;
}

export interface Keyword {
  id: string;
  text: string;
  matchType: string;
  adGroupName: string;
  status: string;
  qualityScore: number | null;
  metrics: CampaignMetrics;
}

export interface Ad {
  id: string;
  headlines: string[];
  descriptions: string[];
  status: string;
  adGroupName: string;
  metrics: CampaignMetrics;
}

// Chat
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  toolCalls?: ToolCall[];
  createdAt: string;
  agentRole?: string;      // role ID (e.g. "search_term_hunter")
  agentRoleName?: string;  // display name (e.g. "Search Term Hunter")
  agentRoleAvatar?: string; // avatar key (e.g. "search")
}

export interface ToolCall {
  id: string;
  source: 'google-ads' | 'google-ads-mcp' | 'chrome' | 'gtm';
  name: string;
  input: Record<string, unknown>;
  output?: Record<string, unknown>;
  status: 'pending' | 'success' | 'error';
}

// Guidelines
export interface GuidelineFile {
  filename: string;
  lastModified: number;
  size: number;
}

// Conversations
export interface Conversation {
  id: string;
  accountId: string;
  campaignId: string | null;
  campaignName: string | null;
  title: string | null;
  createdAt: string;
  updatedAt?: string;
  messageCount?: number;
}

export interface ConversationSearchResult {
  message_id: string;
  conversation_id: string;
  content_snippet: string;
  campaign_name: string | null;
  title: string | null;
  created_at: string;
}

// V2: Multi-Account
export interface AccountV2 {
  id: string;
  name: string;
  mcc_id: string | null;
  level: string;
  is_active: boolean;
  onboarded_at: string | null;
  last_synced: string | null;
}

export interface AccountHealth {
  id: string;
  name: string;
  health: 'healthy' | 'warning' | 'critical' | 'unknown';
  active_campaigns: number;
  total_spend_30d: number;
  total_conversions_30d: number;
  avg_cpa: number;
  alert_count: number;
  last_synced: string | null;
}

export interface DashboardData {
  accounts: AccountHealth[];
  total_alerts: number;
  total_spend_30d: number;
}

export interface CampaignGoal {
  campaign_id: string;
  campaign_name: string | null;
  objective: string;
  phase: string;
  target_cpa: number | null;
  target_roas: number | null;
}

export interface Alert {
  id: number;
  account_id: string;
  campaign_id: string | null;
  type: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  message: string;
  recommendation: string | null;
  created_at: string;
}

export interface OnboardingResult {
  account_id: string;
  account_name: string;
  campaigns_found: number;
  campaigns: CampaignGoal[];
  guidelines_generated: string[];
}
