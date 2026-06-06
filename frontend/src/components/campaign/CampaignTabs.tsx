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
import { fetchPlans } from '@/lib/api';
import { countNeedsAttention } from '@/components/plans/planHelpers';
import { formatBiddingStrategy } from '@/lib/formatters';
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
        <p className="text-xs text-muted-foreground mt-0.5">
          {campaign.channelType} &middot; {formatBiddingStrategy(campaign.biddingStrategy)}
        </p>
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
