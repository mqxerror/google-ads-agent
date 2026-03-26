import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns } from '@/lib/api';
import { formatMicros, formatNumber, formatBiddingStrategy } from '@/lib/formatters';
import CampaignTabs from '@/components/campaign/CampaignTabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { BarChart3, TrendingUp, MousePointerClick, DollarSign } from 'lucide-react';
import type { Campaign } from '@/types';

const CLIENT_ACCOUNT = '7178239091';

function AccountOverview() {
  const { data: campaigns = [], isLoading } = useQuery({
    queryKey: ['campaigns', CLIENT_ACCOUNT],
    queryFn: () => fetchCampaigns(CLIENT_ACCOUNT),
    staleTime: 60_000,
  });

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading campaigns...</div>;

  const totalImpressions = campaigns.reduce((s, c) => s + c.metrics.impressions, 0);
  const totalClicks = campaigns.reduce((s, c) => s + c.metrics.clicks, 0);
  const totalCost = campaigns.reduce((s, c) => s + c.metrics.costMicros, 0);
  const totalConversions = campaigns.reduce((s, c) => s + c.metrics.conversions, 0);

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-6">Account Overview</h2>
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2"><BarChart3 className="h-3.5 w-3.5" />Impressions</div>
          <div className="text-2xl font-semibold">{formatNumber(totalImpressions)}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2"><MousePointerClick className="h-3.5 w-3.5" />Clicks</div>
          <div className="text-2xl font-semibold">{formatNumber(totalClicks)}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2"><DollarSign className="h-3.5 w-3.5" />Total Cost</div>
          <div className="text-2xl font-semibold">{formatMicros(totalCost)}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2"><TrendingUp className="h-3.5 w-3.5" />Conversions</div>
          <div className="text-2xl font-semibold">{formatNumber(totalConversions)}</div>
        </div>
      </div>

      <h3 className="text-sm font-medium text-muted-foreground mb-3">{campaigns.length} Campaigns</h3>
      <div className="space-y-2">
        {campaigns.map((c) => <CampaignRow key={c.id} campaign={c} />)}
      </div>
    </div>
  );
}

function CampaignRow({ campaign }: { campaign: Campaign }) {
  const { setSelectedCampaign } = useAppStore();
  const statusColor = campaign.status === 'ENABLED' ? 'bg-status-enabled' : campaign.status === 'PAUSED' ? 'bg-status-paused' : 'bg-status-removed';

  return (
    <button
      onClick={() => setSelectedCampaign(campaign.id)}
      className="w-full flex items-center gap-3 bg-card border border-border rounded-lg p-3 hover:bg-secondary/40 transition-colors text-left"
    >
      <span className={`w-2 h-2 rounded-full ${statusColor}`} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{campaign.name}</div>
        <div className="text-xs text-muted-foreground">{campaign.channelType} &middot; {formatBiddingStrategy(campaign.biddingStrategy)}</div>
      </div>
      <div className="text-right shrink-0">
        <div className="text-sm font-medium">{formatMicros(campaign.metrics.costMicros)}</div>
        <div className="text-xs text-muted-foreground">{campaign.metrics.conversions} conv.</div>
      </div>
    </button>
  );
}

export default function ContentArea() {
  const { selectedCampaignId, selectedAccountId } = useAppStore();
  const accountId = selectedAccountId || CLIENT_ACCOUNT;

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', CLIENT_ACCOUNT],
    queryFn: () => fetchCampaigns(CLIENT_ACCOUNT),
    staleTime: 60_000,
  });

  const campaign = campaigns.find((c) => c.id === selectedCampaignId);

  return (
    <div className="flex-1 min-w-0 overflow-hidden">
      <ScrollArea className="h-full">
        {campaign ? (
          <CampaignTabs campaign={campaign} accountId={accountId} />
        ) : (
          <AccountOverview />
        )}
      </ScrollArea>
    </div>
  );
}
