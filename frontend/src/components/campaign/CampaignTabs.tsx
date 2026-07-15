import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import CampaignOverview from './CampaignOverview';
import KeywordTable from './KeywordTable';
import AdList from './AdList';
import SearchTermManager from './SearchTermManager';
import LandingPageAnalyzer from './LandingPageAnalyzer';
import GuidelinesViewer from '@/components/guidelines/GuidelinesViewer';
import MemoryExplorer from '@/components/memory/MemoryExplorer';
import CampaignReport from '@/components/reports/CampaignReport';
import WorkflowPanel from '@/components/workflow/WorkflowPanel';
import PlansPanel from '@/components/plans/PlansPanel';
import { useQuery } from '@tanstack/react-query';
import { fetchPlans, fetchCampaignLiveHead } from '@/lib/api';
import { countNeedsAttention } from '@/components/plans/planHelpers';
import { formatBiddingStrategy } from '@/lib/formatters';
import LiveHeadChip from './LiveHeadChip';
import type { Campaign } from '@/types';

interface CampaignTabsProps {
  campaign: Campaign;
  accountId: string;
}

export default function CampaignTabs({ campaign, accountId }: CampaignTabsProps) {
  const { data: plans = [] } = useQuery({
    queryKey: ['plans', accountId, campaign.id],
    queryFn: () => fetchPlans(accountId, campaign.id),
    enabled: !!accountId && !!campaign.id,
    staleTime: 20_000,
  });
  const needsAttention = countNeedsAttention(plans);

  // Live-truth header (B4 / PART 2): poll the control-plane read on the same 60s
  // cadence as the server TTL, so the chip stays fresh without hammering Google.
  // Never throws for a quota/circuit failure — the endpoint degrades to
  // state:'unverified' with a roster fallback instead.
  const { data: liveHead, isLoading: liveHeadLoading } = useQuery({
    queryKey: ['live-head', accountId, campaign.id],
    queryFn: () => fetchCampaignLiveHead(accountId, campaign.id),
    enabled: !!accountId && !!campaign.id,
    staleTime: 55_000,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });

  // Prefer LIVE values in the header when they differ from the cached campaign
  // object — this is the whole point of B4 (fixes "app shows Maximize
  // Conversions when the account says Maximize Clicks"). On an unverified read we
  // fall back to the cached values (the chip already flags them amber).
  const live = liveHead?.state === 'live' ? liveHead : null;
  const headChannel = live?.campaign_type ?? campaign.channelType;
  const headBidding = live ? (live.bidding_strategy ?? '') : campaign.biddingStrategy;

  // The dashboard "Upcoming" timeline asks to open this campaign on its Plans
  // tab; honour that via a one-shot window event.
  const [tab, setTab] = useState('overview');
  useEffect(() => {
    const handler = () => setTab('plans');
    window.addEventListener('plans:open-tab', handler);
    return () => window.removeEventListener('plans:open-tab', handler);
  }, []);

  return (
    <div className="p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">{campaign.name}</h2>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="text-xs text-muted-foreground">
            {headChannel} &middot; {formatBiddingStrategy(headBidding)}
          </p>
          <span className="text-muted-foreground/40" aria-hidden>&middot;</span>
          <LiveHeadChip head={liveHead} loading={liveHeadLoading} />
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-secondary/50">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="keywords">Keywords</TabsTrigger>
          <TabsTrigger value="search-terms">Search Terms</TabsTrigger>
          <TabsTrigger value="ads">Ads</TabsTrigger>
          <TabsTrigger value="landing-page">Landing Page</TabsTrigger>
          <TabsTrigger value="guidelines">Guidelines</TabsTrigger>
          <TabsTrigger value="memory">Memory</TabsTrigger>
          <TabsTrigger value="report">Report</TabsTrigger>
          <TabsTrigger value="team-audit">Team Audit</TabsTrigger>
          <TabsTrigger value="plans" className="gap-1.5">
            Plans
            {needsAttention > 0 && (
              <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-warning-soft px-1 text-[10px] font-semibold text-warning">
                {needsAttention}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <CampaignOverview campaign={campaign} accountId={accountId} />
        </TabsContent>

        <TabsContent value="keywords" className="mt-4">
          <KeywordTable accountId={accountId} campaignId={campaign.id} />
        </TabsContent>

        <TabsContent value="search-terms" className="mt-4">
          <SearchTermManager campaignId={campaign.id} />
        </TabsContent>

        <TabsContent value="ads" className="mt-4">
          <AdList accountId={accountId} campaignId={campaign.id} />
        </TabsContent>

        <TabsContent value="landing-page" className="mt-4">
          <LandingPageAnalyzer campaign={campaign} accountId={accountId} />
        </TabsContent>

        <TabsContent value="guidelines" className="mt-4">
          <GuidelinesViewer />
        </TabsContent>

        <TabsContent value="memory" className="mt-4">
          <MemoryExplorer campaignId={campaign.id} />
        </TabsContent>

        <TabsContent value="report" className="mt-4">
          <CampaignReport campaignId={campaign.id} />
        </TabsContent>

        <TabsContent value="team-audit" className="mt-4">
          <WorkflowPanel accountId={accountId} campaignId={campaign.id} campaignName={campaign.name} />
        </TabsContent>

        <TabsContent value="plans" className="mt-4">
          <PlansPanel accountId={accountId} campaignId={campaign.id} campaignName={campaign.name} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
