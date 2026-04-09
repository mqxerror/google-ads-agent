import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BarChart3, MousePointerClick, Percent, DollarSign, TrendingUp, Target,
  ChevronRight, ChevronDown, Pause, Play, Pencil,
} from 'lucide-react';
import PerformanceChart from '@/components/charts/PerformanceChart';
import { subDays, format } from 'date-fns';
import type { DateRange } from 'react-day-picker';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import MetricCard from './MetricCard';
import DateRangePicker from './DateRangePicker';
import { fetchCampaigns, fetchAdGroups, fetchCampaignTargeting, updateCampaignStatus, updateCampaignBudget } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { formatMicros, formatNumber, formatPercent, formatBiddingStrategy } from '@/lib/formatters';
import type { Campaign, AdGroup } from '@/types';

interface CampaignOverviewProps {
  campaign: Campaign;
  accountId: string;
}

function AdGroupRow({ adGroup }: { adGroup: AdGroup }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border rounded-md">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-3 py-2 hover:bg-secondary/40 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <span className={cn('w-2 h-2 rounded-full', adGroup.status === 'ENABLED' ? 'bg-status-enabled' : 'bg-status-paused')} />
        <span className="text-sm font-medium flex-1 truncate">{adGroup.name}</span>
        <span className={cn('text-xs', adGroup.status === 'ENABLED' ? 'text-status-enabled' : 'text-status-paused')}>
          {adGroup.status}
        </span>
      </button>
      {expanded && (
        <div className="px-4 py-3 border-t border-border bg-secondary/20">
          <div className="grid grid-cols-3 gap-4 text-xs">
            <div><span className="text-muted-foreground">Impressions:</span> {formatNumber(adGroup.metrics.impressions)}</div>
            <div><span className="text-muted-foreground">Clicks:</span> {formatNumber(adGroup.metrics.clicks)}</div>
            <div><span className="text-muted-foreground">CTR:</span> {formatPercent(adGroup.metrics.ctr)}</div>
            <div><span className="text-muted-foreground">Cost:</span> {formatMicros(adGroup.metrics.costMicros)}</div>
            <div><span className="text-muted-foreground">Conversions:</span> {adGroup.metrics.conversions}</div>
            <div><span className="text-muted-foreground">CPA:</span> {adGroup.metrics.cpa > 0 ? `$${adGroup.metrics.cpa.toFixed(2)}` : '—'}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CampaignOverview({ campaign, accountId }: CampaignOverviewProps) {
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: subDays(new Date(), 6),
    to: new Date(),
  });

  const dateFrom = dateRange?.from ? format(dateRange.from, 'yyyy-MM-dd') : undefined;
  const dateTo = dateRange?.to ? format(dateRange.to, 'yyyy-MM-dd') : undefined;

  // Fetch campaign metrics for selected date range
  const { data: freshCampaign } = useQuery({
    queryKey: ['campaign-metrics', accountId, campaign.id, dateFrom, dateTo],
    queryFn: async () => {
      const campaigns = await fetchCampaigns(accountId, dateFrom, dateTo);
      return campaigns.find(c => c.id === campaign.id) ?? campaign;
    },
    placeholderData: campaign,
    enabled: !!dateFrom && !!dateTo,
  });

  // Fetch ad groups
  const { data: adGroups = [], isLoading: adGroupsLoading } = useQuery({
    queryKey: ['adgroups', accountId, campaign.id],
    queryFn: () => fetchAdGroups(accountId, campaign.id),
  });

  // Fetch targeting
  const { data: targeting } = useQuery({
    queryKey: ['targeting', accountId, campaign.id],
    queryFn: () => fetchCampaignTargeting(accountId, campaign.id),
  });

  const queryClient = useQueryClient();
  const [editingBudget, setEditingBudget] = useState(false);
  const [budgetValue, setBudgetValue] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const handleToggleStatus = async () => {
    const newStatus = campaign.status === 'ENABLED' ? 'PAUSED' : 'ENABLED';
    setActionLoading(true);
    try {
      await updateCampaignStatus(accountId, campaign.id, newStatus);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e) {
      console.error('Failed to update status:', e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleBudgetSave = async () => {
    const micros = Math.round(parseFloat(budgetValue) * 1_000_000);
    if (isNaN(micros) || micros <= 0) return;
    setActionLoading(true);
    try {
      await updateCampaignBudget(accountId, campaign.id, micros);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      setEditingBudget(false);
    } catch (e) {
      console.error('Failed to update budget:', e);
    } finally {
      setActionLoading(false);
    }
  };

  const m = freshCampaign?.metrics ?? campaign.metrics;

  const statusColor =
    campaign.status === 'ENABLED'
      ? 'bg-status-enabled/20 text-status-enabled'
      : campaign.status === 'PAUSED'
        ? 'bg-status-paused/20 text-status-paused'
        : 'bg-status-removed/20 text-status-removed';

  return (
    <div className="space-y-6">
      {/* Quick Actions */}
      <div className="flex items-center gap-3">
        <Button
          variant={campaign.status === 'ENABLED' ? 'outline' : 'default'}
          size="sm"
          className="text-xs gap-1.5"
          onClick={handleToggleStatus}
          disabled={actionLoading}
        >
          {campaign.status === 'ENABLED' ? (
            <><Pause className="h-3 w-3" /> Pause Campaign</>
          ) : (
            <><Play className="h-3 w-3" /> Enable Campaign</>
          )}
        </Button>

        {editingBudget ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">$</span>
            <Input
              className="h-7 w-24 text-xs"
              value={budgetValue}
              onChange={(e) => setBudgetValue(e.target.value)}
              placeholder={String(campaign.budgetAmountMicros / 1_000_000)}
              autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') handleBudgetSave(); if (e.key === 'Escape') setEditingBudget(false); }}
            />
            <span className="text-xs text-muted-foreground">/day</span>
            <Button size="sm" className="h-7 text-xs" onClick={handleBudgetSave} disabled={actionLoading}>Save</Button>
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setEditingBudget(false)}>Cancel</Button>
          </div>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="text-xs gap-1.5"
            onClick={() => { setBudgetValue(String(campaign.budgetAmountMicros / 1_000_000)); setEditingBudget(true); }}
          >
            <Pencil className="h-3 w-3" /> Edit Budget ({formatMicros(campaign.budgetAmountMicros)}/d)
          </Button>
        )}

        <div className="ml-auto">
          <DateRangePicker dateRange={dateRange} onDateRangeChange={setDateRange} />
        </div>
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-6 gap-3">
        <MetricCard label="Impressions" value={formatNumber(m.impressions)} icon={<BarChart3 className="h-3.5 w-3.5" />} />
        <MetricCard label="Clicks" value={formatNumber(m.clicks)} icon={<MousePointerClick className="h-3.5 w-3.5" />} />
        <MetricCard label="CTR" value={formatPercent(m.ctr)} icon={<Percent className="h-3.5 w-3.5" />} />
        <MetricCard label="Cost" value={formatMicros(m.costMicros)} icon={<DollarSign className="h-3.5 w-3.5" />} />
        <MetricCard label="Conversions" value={formatNumber(m.conversions)} icon={<TrendingUp className="h-3.5 w-3.5" />} />
        <MetricCard label="CPA" value={m.cpa > 0 ? `$${m.cpa.toFixed(2)}` : '—'} icon={<Target className="h-3.5 w-3.5" />} />
      </div>

      {/* Performance Chart */}
      <PerformanceChart campaignId={campaign.id} />

      <Separator />

      {/* Campaign settings */}
      <div>
        <h3 className="text-sm font-medium mb-3">Campaign Settings</h3>
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Status</span>
              <Badge variant="secondary" className={statusColor}>{campaign.status}</Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Channel</span>
              <span>{campaign.channelType}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Bidding Strategy</span>
              <span>{formatBiddingStrategy(campaign.biddingStrategy)}</span>
            </div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Daily Budget</span>
              <span>{formatMicros(campaign.budgetAmountMicros)}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Location</span>
              <span>{targeting?.locations?.join(', ') || 'Loading...'}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Language</span>
              <span>{targeting?.languages?.join(', ') || 'Loading...'}</span>
            </div>
          </div>
        </div>
      </div>

      <Separator />

      {/* Ad group tree */}
      <div>
        <h3 className="text-sm font-medium mb-3">Ad Groups ({adGroups.length})</h3>
        <div className="space-y-2">
          {adGroupsLoading && <p className="text-sm text-muted-foreground">Loading ad groups...</p>}
          {adGroups.map((ag) => (
            <AdGroupRow key={ag.id} adGroup={ag} />
          ))}
          {!adGroupsLoading && adGroups.length === 0 && (
            <p className="text-sm text-muted-foreground italic">No ad groups found for this campaign.</p>
          )}
        </div>
      </div>
    </div>
  );
}
