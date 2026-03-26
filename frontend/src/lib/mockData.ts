import type {
  Account,
  Campaign,
  AdGroup,
  Keyword,
  Ad,
  ChatMessage,
  Conversation,
} from '@/types';

// ---------- Campaigns (based on real Mercan Group data from CAMPAIGN_GUIDELINES.md) ----------

export const mockCampaigns: Campaign[] = [
  {
    id: '23636342079',
    name: 'Portugal Golden Visa - USA',
    status: 'ENABLED',
    channelType: 'SEARCH',
    budgetAmountMicros: 200_000_000, // $200/day
    biddingStrategy: 'MAXIMIZE_CLICKS',
    metrics: {
      impressions: 1_624,
      clicks: 181,
      ctr: 11.15,
      costMicros: 777_000_000, // $777
      conversions: 3,
      cpa: 259.0,
    },
  },
  {
    id: '22551124974',
    name: 'Greece Golden Visa',
    status: 'ENABLED',
    channelType: 'SEARCH',
    budgetAmountMicros: 200_000_000, // $200/day
    biddingStrategy: 'MAXIMIZE_CONVERSIONS',
    metrics: {
      impressions: 8_420,
      clicks: 512,
      ctr: 6.08,
      costMicros: 4_980_000_000, // $4,980
      conversions: 83,
      cpa: 60.0,
    },
  },
  {
    id: '23688200557',
    name: 'MENA Golden Visa',
    status: 'ENABLED',
    channelType: 'SEARCH',
    budgetAmountMicros: 50_000_000, // $50/day
    biddingStrategy: 'MAXIMIZE_CLICKS',
    metrics: {
      impressions: 620,
      clicks: 42,
      ctr: 6.77,
      costMicros: 126_000_000, // $126
      conversions: 0,
      cpa: 0,
    },
  },
  {
    id: '20043943331',
    name: 'EB3 Brazil',
    status: 'ENABLED',
    channelType: 'SEARCH',
    budgetAmountMicros: 100_000_000, // $100/day
    biddingStrategy: 'MAXIMIZE_CLICKS',
    metrics: {
      impressions: 3_200,
      clicks: 195,
      ctr: 6.09,
      costMicros: 1_560_000_000, // $1,560
      conversions: 12,
      cpa: 130.0,
    },
  },
  {
    id: '14815079674',
    name: 'PGV - Impression Share',
    status: 'ENABLED',
    channelType: 'SEARCH',
    budgetAmountMicros: 50_000_000, // $50/day
    biddingStrategy: 'TARGET_IMPRESSION_SHARE',
    metrics: {
      impressions: 4_100,
      clicks: 287,
      ctr: 7.0,
      costMicros: 2_009_000_000, // $2,009
      conversions: 18,
      cpa: 111.61,
    },
  },
];

// ---------- Account hierarchy (real IDs from Mercan Group) ----------

export const mockAccounts: Account[] = [
  {
    id: '6895949945',
    name: 'MQXDev',
    parentId: null,
    level: 'manager',
    isActive: true,
    children: [
      {
        id: '7192648347',
        name: 'Wassim',
        parentId: '6895949945',
        level: 'sub_manager',
        isActive: true,
        children: [
          {
            id: '7178239091',
            name: 'Mercan Group',
            parentId: '7192648347',
            level: 'client',
            isActive: true,
            campaigns: mockCampaigns,
          },
        ],
      },
    ],
  },
];

// ---------- Ad Groups (Portugal Golden Visa - real structure) ----------

export const mockAdGroups: AdGroup[] = [
  {
    id: '202548312468',
    name: 'Portugal Golden Visa',
    status: 'ENABLED',
    campaignId: '23636342079',
    keywordCount: 8,
    adCount: 2,
    metrics: {
      impressions: 680,
      clicks: 82,
      ctr: 12.06,
      costMicros: 352_000_000,
      conversions: 2,
      cpa: 176.0,
    },
  },
  {
    id: '202548333748',
    name: 'Portugal Residency',
    status: 'ENABLED',
    campaignId: '23636342079',
    keywordCount: 7,
    adCount: 2,
    metrics: {
      impressions: 420,
      clicks: 55,
      ctr: 13.10,
      costMicros: 220_000_000,
      conversions: 1,
      cpa: 220.0,
    },
  },
  {
    id: '191851143737',
    name: 'Portugal Golden Visa Fund',
    status: 'ENABLED',
    campaignId: '23636342079',
    keywordCount: 3,
    adCount: 2,
    metrics: {
      impressions: 310,
      clicks: 28,
      ctr: 9.03,
      costMicros: 140_000_000,
      conversions: 0,
      cpa: 0,
    },
  },
  {
    id: '199260227452',
    name: 'Portugal Citizenship by Investment',
    status: 'ENABLED',
    campaignId: '23636342079',
    keywordCount: 5,
    adCount: 2,
    metrics: {
      impressions: 165,
      clicks: 12,
      ctr: 7.27,
      costMicros: 48_000_000,
      conversions: 0,
      cpa: 0,
    },
  },
  {
    id: '191851144937',
    name: 'Mercan Brand',
    status: 'ENABLED',
    campaignId: '23636342079',
    keywordCount: 4,
    adCount: 1,
    metrics: {
      impressions: 49,
      clicks: 4,
      ctr: 8.16,
      costMicros: 17_000_000,
      conversions: 0,
      cpa: 0,
    },
  },
];

// ---------- Keywords (Portugal Golden Visa - real keywords) ----------

export const mockKeywords: Keyword[] = [
  {
    id: 'kw-001',
    text: 'portugal golden visa',
    matchType: 'EXACT',
    adGroupName: 'Portugal Golden Visa',
    status: 'ENABLED',
    qualityScore: 7,
    metrics: { impressions: 280, clicks: 58, ctr: 20.71, costMicros: 248_000_000, conversions: 2, cpa: 124.0 },
  },
  {
    id: 'kw-002',
    text: 'portugal golden visa',
    matchType: 'PHRASE',
    adGroupName: 'Portugal Golden Visa',
    status: 'ENABLED',
    qualityScore: 7,
    metrics: { impressions: 120, clicks: 14, ctr: 11.67, costMicros: 56_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-003',
    text: 'golden visa portugal',
    matchType: 'PHRASE',
    adGroupName: 'Portugal Golden Visa',
    status: 'ENABLED',
    qualityScore: 7,
    metrics: { impressions: 95, clicks: 8, ctr: 8.42, costMicros: 32_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-004',
    text: 'portugal golden visa program',
    matchType: 'EXACT',
    adGroupName: 'Portugal Golden Visa',
    status: 'ENABLED',
    qualityScore: 7,
    metrics: { impressions: 45, clicks: 5, ctr: 11.11, costMicros: 20_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-005',
    text: 'portugal golden visa 2026',
    matchType: 'EXACT',
    adGroupName: 'Portugal Golden Visa',
    status: 'ENABLED',
    qualityScore: 7,
    metrics: { impressions: 38, clicks: 3, ctr: 7.89, costMicros: 12_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-006',
    text: 'portugal residency for us citizens',
    matchType: 'PHRASE',
    adGroupName: 'Portugal Residency',
    status: 'ENABLED',
    qualityScore: 2,
    metrics: { impressions: 190, clicks: 49, ctr: 25.79, costMicros: 196_000_000, conversions: 1, cpa: 196.0 },
  },
  {
    id: 'kw-007',
    text: 'portugal residency by investment',
    matchType: 'PHRASE',
    adGroupName: 'Portugal Residency',
    status: 'ENABLED',
    qualityScore: 5,
    metrics: { impressions: 85, clicks: 6, ctr: 7.06, costMicros: 24_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-008',
    text: 'portugal investment visa',
    matchType: 'PHRASE',
    adGroupName: 'Portugal Residency',
    status: 'ENABLED',
    qualityScore: 4,
    metrics: { impressions: 72, clicks: 4, ctr: 5.56, costMicros: 16_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-009',
    text: 'portugal golden visa fund',
    matchType: 'EXACT',
    adGroupName: 'Portugal Golden Visa Fund',
    status: 'ENABLED',
    qualityScore: 5,
    metrics: { impressions: 110, clicks: 12, ctr: 10.91, costMicros: 60_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-010',
    text: 'portugal golden visa investment fund',
    matchType: 'EXACT',
    adGroupName: 'Portugal Golden Visa Fund',
    status: 'ENABLED',
    qualityScore: 4,
    metrics: { impressions: 65, clicks: 5, ctr: 7.69, costMicros: 25_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-011',
    text: 'portugal citizenship by investment',
    matchType: 'PHRASE',
    adGroupName: 'Portugal Citizenship by Investment',
    status: 'ENABLED',
    qualityScore: 5,
    metrics: { impressions: 90, clicks: 7, ctr: 7.78, costMicros: 28_000_000, conversions: 0, cpa: 0 },
  },
  {
    id: 'kw-012',
    text: 'mercan group portugal',
    matchType: 'EXACT',
    adGroupName: 'Mercan Brand',
    status: 'ENABLED',
    qualityScore: null,
    metrics: { impressions: 20, clicks: 2, ctr: 10.0, costMicros: 8_000_000, conversions: 0, cpa: 0 },
  },
];

// ---------- Ads ----------

export const mockAds: Ad[] = [
  {
    id: 'ad-001',
    headlines: ['Portugal Golden Visa 2026', 'Invest & Get EU Residency', 'Free Consultation'],
    descriptions: [
      'Start your journey to EU residency through Portugal\'s Golden Visa. Expert guidance from Mercan Group.',
      'Trusted by 500+ families worldwide. Get your free eligibility assessment today.',
    ],
    status: 'ENABLED',
    adGroupName: 'Portugal Golden Visa',
    metrics: { impressions: 680, clicks: 82, ctr: 12.06, costMicros: 352_000_000, conversions: 2, cpa: 176.0 },
  },
  {
    id: 'ad-002',
    headlines: ['Move to Portugal Legally', 'Golden Visa Program', 'Apply Now'],
    descriptions: [
      'Portugal Golden Visa: Your path to EU citizenship. Fund investment from €500K.',
      'Experienced immigration experts. 98% approval rate. Book a call with Mercan Group.',
    ],
    status: 'ENABLED',
    adGroupName: 'Portugal Residency',
    metrics: { impressions: 420, clicks: 55, ctr: 13.10, costMicros: 220_000_000, conversions: 1, cpa: 220.0 },
  },
  {
    id: 'ad-003',
    headlines: ['Portugal Golden Visa Fund', 'Investment Starting €500K', 'Talk to an Expert'],
    descriptions: [
      'Explore Portugal investment fund opportunities. Get residency and access to the EU.',
      'Mercan Group: Helping investors relocate since 2010. Schedule your consultation.',
    ],
    status: 'ENABLED',
    adGroupName: 'Portugal Golden Visa Fund',
    metrics: { impressions: 310, clicks: 28, ctr: 9.03, costMicros: 140_000_000, conversions: 0, cpa: 0 },
  },
];

// ---------- Chat messages ----------

export const mockMessages: ChatMessage[] = [
  {
    id: 'msg-001',
    role: 'user',
    content: 'Check if PGV LP-CT conversion tag has recorded any conversions since March 19.',
    createdAt: '2026-03-25T10:00:00Z',
  },
  {
    id: 'msg-002',
    role: 'assistant',
    content:
      'The **PGV LP - CT** conversion action (ID: 7463488293) has recorded **3 conversions** since the jQuery fix on March 19.\n\n- **March 20-26:** 3 conversions\n- **Cost per conversion:** $259.00\n- **Campaign:** Portugal Golden Visa - USA\n\nThe fix is working. The conversion tag is now firing correctly on form submissions via Gravity Forms. Per the guidelines, we should wait until March 26 (7-day stabilization period) before making any further changes.',
    toolCalls: [
      {
        id: 'tc-001',
        source: 'google-ads',
        name: 'get_campaign_metrics',
        input: { customer_id: '7178239091', campaign_id: '23636342079', date_range: '2026-03-19..2026-03-26' },
        output: { conversions: 3, cost: 777, impressions: 1624, clicks: 181 },
        status: 'success',
      },
    ],
    createdAt: '2026-03-25T10:00:05Z',
  },
  {
    id: 'msg-003',
    role: 'user',
    content: 'Can you check the GTM container to verify the conversion tag is still properly configured?',
    createdAt: '2026-03-25T10:01:00Z',
  },
  {
    id: 'msg-004',
    role: 'assistant',
    content:
      'I checked the GTM container **GTM-KWFH5X9T** and everything looks correct:\n\n1. **Conversion Linker** - Active on all pages ✓\n2. **GF dataLayer push tag** - Using jQuery event listener (fixed V4) ✓\n3. **PGV LP-CT tag** - Fires on `gf_submit` event with URL filter for `/business-immigration/portugal-golden-visa-program` ✓\n4. **Google Tag AW-826329520** - Active on all pages ✓\n\nAll 5 tags are properly configured. The fix from March 19 is still in place.',
    toolCalls: [
      {
        id: 'tc-002',
        source: 'chrome',
        name: 'navigate',
        input: { url: 'https://tagmanager.google.com/#/container/accounts/826329520/containers/GTM-KWFH5X9T' },
        output: { title: 'Google Tag Manager', status: 'loaded' },
        status: 'success',
      },
      {
        id: 'tc-003',
        source: 'chrome',
        name: 'read_page',
        input: { selector: '.tag-list' },
        output: { tags: ['Conversion Linker', 'GF Push dataLayer', 'PGV LP-CT', 'Google Ads Conv', 'Google Tag'] },
        status: 'success',
      },
    ],
    createdAt: '2026-03-25T10:01:10Z',
  },
];

// ---------- Conversations ----------

export const mockConversations: Conversation[] = [
  {
    id: 'conv-001',
    accountId: '7178239091',
    campaignId: '23636342079',
    campaignName: 'Portugal Golden Visa - USA',
    title: 'Conversion tag verification post-fix',
    createdAt: '2026-03-25T10:00:00Z',
  },
  {
    id: 'conv-002',
    accountId: '7178239091',
    campaignId: '22551124974',
    campaignName: 'Greece Golden Visa',
    title: 'Budget and CPA optimization',
    createdAt: '2026-03-24T14:30:00Z',
  },
];

// ---------- Flat account list helper ----------

export function flattenAccounts(accounts: Account[]): Account[] {
  const result: Account[] = [];
  function walk(accs: Account[]) {
    for (const a of accs) {
      result.push(a);
      if (a.children) walk(a.children);
    }
  }
  walk(accounts);
  return result;
}

// ---------- Formatting helpers ----------

export function formatMicros(micros: number): string {
  return `$${(micros / 1_000_000).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function formatPercent(n: number): string {
  return `${n.toFixed(2)}%`;
}
