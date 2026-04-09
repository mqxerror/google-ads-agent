import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import CampaignOverview from './CampaignOverview';
import KeywordTable from './KeywordTable';
import AdList from './AdList';
import SearchTermManager from './SearchTermManager';
import GuidelinesViewer from '@/components/guidelines/GuidelinesViewer';
import { formatBiddingStrategy } from '@/lib/formatters';
import type { Campaign } from '@/types';

interface CampaignTabsProps {
  campaign: Campaign;
  accountId: string;
}

export default function CampaignTabs({ campaign, accountId }: CampaignTabsProps) {
  return (
    <div className="p-6">
      <div className="mb-4">
        <h2 className="text-lg font-semibold">{campaign.name}</h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          {campaign.channelType} &middot; {formatBiddingStrategy(campaign.biddingStrategy)}
        </p>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="bg-secondary/50">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="keywords">Keywords</TabsTrigger>
          <TabsTrigger value="search-terms">Search Terms</TabsTrigger>
          <TabsTrigger value="ads">Ads</TabsTrigger>
          <TabsTrigger value="guidelines">Guidelines</TabsTrigger>
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

        <TabsContent value="guidelines" className="mt-4">
          <GuidelinesViewer />
        </TabsContent>
      </Tabs>
    </div>
  );
}
