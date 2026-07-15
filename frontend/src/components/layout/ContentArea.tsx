import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns } from '@/lib/api';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import CampaignTabs from '@/components/campaign/CampaignTabs';
import CampaignBuilder from '@/components/campaign/CampaignBuilder';
import StudioPage from '@/components/studio/StudioPage';
import ChangelogPage from '@/components/changelog/ChangelogPage';
import GuidelinesPage from '@/components/guidelines/GuidelinesPage';
import HomeV2 from '@/components/dashboard/HomeV2';
import ConversationsPage from '@/pages/Conversations';
import { ScrollArea } from '@/components/ui/scroll-area';

/**
 * ContentArea — the main content router (right of the sidebar).
 *
 * The home surface is now HomeV2 (Epic 13, Story 13.5). The old inline
 * AccountOverview composition (lifetime KPI grid + OutcomeDashboard +
 * ConversationGraph + campaign grid + UpcomingPlans/CampaignRow) was
 * retired here — HomeV2 replaces it. The reusable component files it
 * used (OutcomeDashboard.tsx, ConversationGraph.tsx,
 * CampaignActivityFeed.tsx) are left in place: ConversationGraph now
 * lives on the Conversations page, and OutcomeDashboard /
 * CampaignActivityFeed are the seams Stories 13.7/13.8 will re-mount.
 */
export default function ContentArea() {
  const { selectedCampaignId, showStudio, showChangelog, showGuidelines, showConversations } = useAppStore();
  const accountId = useClientAccountId();
  const [showBuilder, setShowBuilder] = useState(false);
  const handleShowBuilder = (show: boolean) => setShowBuilder(show);

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', accountId],
    queryFn: () => fetchCampaigns(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  const campaign = campaigns.find((c) => c.id === selectedCampaignId);

  return (
    <div className="flex-1 min-w-0 overflow-hidden">
      <ScrollArea className="h-full">
        {showGuidelines ? (
          <GuidelinesPage />
        ) : showChangelog ? (
          <ChangelogPage />
        ) : showConversations ? (
          <ConversationsPage />
        ) : showStudio ? (
          <StudioPage />
        ) : showBuilder ? (
          <CampaignBuilder onClose={() => handleShowBuilder(false)} />
        ) : campaign ? (
          <CampaignTabs campaign={campaign} accountId={accountId} />
        ) : (
          <HomeV2 onOpenBuilder={() => handleShowBuilder(true)} />
        )}
      </ScrollArea>
    </div>
  );
}
