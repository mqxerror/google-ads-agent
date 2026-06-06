import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns, updateCampaignStatus, fetchUpcomingPlans } from '@/lib/api';
import { groupByDay, statusVisual, relativeTime } from '@/components/plans/planHelpers';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { formatMicros, formatNumber, formatBiddingStrategy } from '@/lib/formatters';
import CampaignTabs from '@/components/campaign/CampaignTabs';
import CampaignBuilder from '@/components/campaign/CampaignBuilder';
import StudioPage from '@/components/studio/StudioPage';
import ChangelogPage from '@/components/changelog/ChangelogPage';
import GuidelinesPage from '@/components/guidelines/GuidelinesPage';
import CampaignActivityFeed from '@/components/dashboard/CampaignActivityFeed';
import OutcomeDashboard from '@/components/dashboard/OutcomeDashboard';
import ConversationGraph from '@/components/dashboard/ConversationGraph';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { BarChart3, TrendingUp, MousePointerClick, DollarSign, Pause, Play, Loader2, Rocket, Filter, CalendarClock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Campaign } from '@/types';

function AccountOverview({ onOpenBuilder }: { onOpenBuilder?: () => void }) {
  const clientAccountId = useClientAccountId();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);
  const [campaignFilter, setCampaignFilter] = useState<'active' | 'paused' | 'all'>('active');

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
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">Account Overview</h2>
        {onOpenBuilder && (
          <Button onClick={onOpenBuilder} className="gap-2">
            <Rocket className="h-4 w-4" />
            Create Campaign
          </Button>
        )}
      </div>
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

      {/* Agent Performance + Conversation Map — above campaigns */}
      <div className="grid grid-cols-2 gap-6 mb-8">
        <div className="bg-card border border-border rounded-lg p-4">
          <OutcomeDashboard />
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-sm font-semibold">Conversation Map</h3>
          </div>
          <ConversationGraph />
        </div>
      </div>

      {/* Campaign filter + bulk actions */}
      <div className="flex items-center gap-3 mb-3">
        <Filter className="h-3.5 w-3.5 text-muted-foreground" />
        {(['active', 'paused', 'all'] as const).map((f) => {
          const count = f === 'active' ? campaigns.filter(c => c.status === 'ENABLED').length
            : f === 'paused' ? campaigns.filter(c => c.status === 'PAUSED').length
            : campaigns.length;
          return (
            <button
              key={f}
              onClick={() => setCampaignFilter(f)}
              className={cn(
                'text-xs px-2.5 py-1 rounded-full transition-colors',
                campaignFilter === f
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              )}
            >
              {f === 'active' ? 'Active' : f === 'paused' ? 'Paused' : 'All'} ({count})
            </button>
          );
        })}

        {selected.size > 0 && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs font-medium">{selected.size} selected</span>
            <Button size="sm" variant="outline" className="text-xs h-7 gap-1" onClick={() => handleBulkAction('PAUSED')} disabled={bulkLoading}>
              {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Pause className="h-3 w-3" />}
              Pause
            </Button>
            <Button size="sm" variant="outline" className="text-xs h-7 gap-1" onClick={() => handleBulkAction('ENABLED')} disabled={bulkLoading}>
              {bulkLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
              Enable
            </Button>
            <button className="text-xs text-muted-foreground hover:text-foreground" onClick={() => setSelected(new Set())}>Clear</button>
          </div>
        )}
      </div>

      {/* Filtered campaign list */}
      <div className="space-y-2">
        {campaigns
          .filter((c) => {
            if (campaignFilter === 'active') return c.status === 'ENABLED';
            if (campaignFilter === 'paused') return c.status === 'PAUSED';
            return true;
          })
          .map((c) => (
            <CampaignRow
              key={c.id}
              campaign={c}
              isSelected={selected.has(c.id)}
              onToggleSelect={() => toggleSelect(c.id)}
            />
          ))}
      </div>

      {/* Upcoming scheduled plans — quiet, secondary timeline. */}
      <div className="mt-8 pt-6 border-t border-border">
        <UpcomingPlans accountId={clientAccountId} />
      </div>

      {/* Campaign Activity Feed */}
      <div className="mt-8 pt-6 border-t border-border">
        <CampaignActivityFeed />
      </div>
    </div>
  );
}

function UpcomingPlans({ accountId }: { accountId: string }) {
  const { setSelectedCampaign } = useAppStore();
  const { data: plans = [], isLoading } = useQuery({
    queryKey: ['plans-upcoming', accountId],
    queryFn: () => fetchUpcomingPlans(accountId),
    enabled: !!accountId,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (isLoading || plans.length === 0) return null;
  const days = groupByDay(plans);

  const openPlan = (campaignId?: string | null) => {
    if (!campaignId) return;
    setSelectedCampaign(campaignId);
    // CampaignTabs listens for this to jump straight to its Plans tab.
    setTimeout(() => window.dispatchEvent(new CustomEvent('plans:open-tab')), 0);
  };

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <CalendarClock className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Upcoming</h3>
        <span className="text-xs text-muted-foreground">across campaigns</span>
      </div>
      <div className="space-y-4">
        {days.map((d) => (
          <div key={d.dayLabel}>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground mb-1">{d.dayLabel}</div>
            <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
              {d.plans.map((p) => {
                const sv = statusVisual(p.status);
                return (
                  <button
                    key={p.id}
                    onClick={() => openPlan(p.campaign_id)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-left text-sm hover:bg-secondary/40 transition-colors"
                  >
                    <span className={cn('h-2 w-2 shrink-0 rounded-full', sv.dot, sv.pulse && 'studio-pulse')} aria-label={sv.label} />
                    <span className="text-muted-foreground w-40 truncate shrink-0">{p.campaign_name || 'Account'}</span>
                    <span className="flex-1 truncate text-text">{p.title}</span>
                    <span className="text-[11px] text-subtle shrink-0">{relativeTime(p.next_run_at || p.run_at)}</span>
                  </button>
                );
              })}
            </div>
          </div>
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
  const { selectedCampaignId, showStudio, showChangelog, showGuidelines } = useAppStore();
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
        ) : showStudio ? (
          <StudioPage />
        ) : showBuilder ? (
          <CampaignBuilder onClose={() => handleShowBuilder(false)} />
        ) : campaign ? (
          <CampaignTabs campaign={campaign} accountId={accountId} />
        ) : (
          <AccountOverview onOpenBuilder={() => handleShowBuilder(true)} />
        )}
      </ScrollArea>
    </div>
  );
}
