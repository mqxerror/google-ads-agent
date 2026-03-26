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
}

export interface ToolCall {
  id: string;
  source: 'google-ads' | 'chrome';
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
}
