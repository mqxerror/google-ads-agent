import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns, updateCampaignStatus } from '@/lib/api';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { formatMicros, formatNumber, formatBiddingStrategy } from '@/lib/formatters';
import CampaignTabs from '@/components/campaign/CampaignTabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { BarChart3, TrendingUp, MousePointerClick, DollarSign, Pause, Play, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Campaign } from '@/types';

function AccountOverview() {
  const clientAccountId = useClientAccountId();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  const { data: campaigns = [], isLoading } = useQuery({
    queryKey: ['campaigns', clientAccountId],
    queryFn: () => fetchCampaigns(clientAccountId),
    staleTime: 60_000,
    enabled: !!clientAccountId,
  });

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading campaigns...</div>;

  const totalImpressions = campaigns.reduce((s, c) => s + c.metrics.impressions, 0);
  const totalClicks = campaigns.reduce((s, c) => s + c.metrics.clicks, 0);
  const totalCost = campaigns.reduce((s, c) => s + c.metrics.costMicros, 0);
  const totalConversions = campaigns.reduce((s, c) => s + c.metrics.conversions, 0);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleBulkAction = async (status: 'ENABLED' | 'PAUSED') => {
    if (selected.size === 0) return;
    setBulkLoading(true);
    try {
      const promises = Array.from(selected).map((campaignId) =>
        updateCampaignStatus(clientAccountId, campaignId, status)
      );
      await Promise.all(promises);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      setSelected(new Set());
    } catch (e) {
      console.error('Bulk action failed:', e);
    } finally {
      setBulkLoading(false);
    }
  };

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

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-4 bg-secondary/50 rounded-lg px-4 py-2">
          <span className="text-xs font-medium">{selected.size} selected</span>
          <Button size="sm" variant="outline" className="text-xs h-7 gap-1" onClick={() => handleBulkAction('PAUSED')} disabled={bulkLoading}>
            {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Pause className="h-3 w-3" />}
            Pause Selected
          </Button>
          <Button size="sm" variant="outline" className="text-xs h-7 gap-1" onClick={() => handleBulkAction('ENABLED')} disabled={bulkLoading}>
            {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
            Enable Selected
          </Button>
          <button className="text-xs text-muted-foreground hover:text-foreground ml-auto" onClick={() => setSelected(new Set())}>
            Clear
          </button>
        </div>
      )}

      <h3 className="text-sm font-medium text-muted-foreground mb-3">{campaigns.length} Campaigns</h3>
      <div className="space-y-2">
        {campaigns.map((c) => (
          <CampaignRow
            key={c.id}
            campaign={c}
            isSelected={selected.has(c.id)}
            onToggleSelect={() => toggleSelect(c.id)}
          />
        ))}
      </div>
    </div>
  );
}

function CampaignRow({ campaign, isSelected, onToggleSelect }: { campaign: Campaign; isSelected: boolean; onToggleSelect: () => void }) {
  const { setSelectedCampaign } = useAppStore();
  const statusColor = campaign.status === 'ENABLED' ? 'bg-status-enabled' : campaign.status === 'PAUSED' ? 'bg-status-paused' : 'bg-status-removed';

  return (
    <div className={cn(
      'flex items-center gap-3 bg-card border rounded-lg p-3 transition-colors',
      isSelected ? 'border-primary/50 bg-primary/5' : 'border-border hover:bg-secondary/40'
    )}>
      <input
        type="checkbox"
        checked={isSelected}
        onChange={onToggleSelect}
        className="rounded shrink-0"
        onClick={(e) => e.stopPropagation()}
      />
      <button
        onClick={() => setSelectedCampaign(campaign.id)}
        className="flex-1 flex items-center gap-3 text-left min-w-0"
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
    </div>
  );
}

export default function ContentArea() {
  const { selectedCampaignId } = useAppStore();
  const accountId = useClientAccountId();

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
        {campaign ? (
          <CampaignTabs campaign={campaign} accountId={accountId} />
        ) : (
          <AccountOverview />
        )}
      </ScrollArea>
    </div>
  );
}
