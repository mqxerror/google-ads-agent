import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight,
  ChevronDown,
  PanelLeftClose,
  PanelLeft,
  Search,
  Building2,
  Users,
  Briefcase,
  RefreshCw,
  Layers,
  Home,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns, fetchAccounts, fetchCampaignGoals, fetchCampaignsSyncStatus, forceSyncCampaigns } from '@/lib/api';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { Account, Campaign } from '@/types';

// ── Phase Badge ─────────────────────────────────────────────────

const PHASE_STYLES: Record<string, { label: string; color: string }> = {
  launch: { label: 'Launch', color: 'text-blue-400 bg-blue-400/10' },
  learning: { label: 'Learning', color: 'text-yellow-400 bg-yellow-400/10' },
  optimization: { label: 'Optim', color: 'text-green-400 bg-green-400/10' },
  scaling: { label: 'Scale', color: 'text-purple-400 bg-purple-400/10' },
  sunset: { label: 'Sunset', color: 'text-zinc-400 bg-zinc-400/10' },
};

function PhaseBadge({ campaignId, accountId }: { campaignId: string; accountId: string }) {
  const { data } = useQuery({
    queryKey: ['campaign-goal', accountId, campaignId],
    queryFn: () => fetchCampaignGoals(accountId, campaignId),
    staleTime: 300_000, // 5 minutes
    retry: false,
  });

  if (!data?.phase || data.phase === 'unknown') return null;

  const style = PHASE_STYLES[data.phase];
  if (!style) return null;

  return (
    <span
      className={cn('px-1 py-0 rounded text-[8px] font-medium leading-tight', style.color)}
      title={`Phase: ${data.phase}`}
    >
      {style.label}
    </span>
  );
}

// ── Existing Components ─────────────────────────────────────────

function StatusDot({ status }: { status: Campaign['status'] }) {
  const color =
    status === 'ENABLED'
      ? 'bg-status-enabled'
      : status === 'PAUSED'
        ? 'bg-status-paused'
        : 'bg-status-removed';
  return <span className={cn('inline-block w-2 h-2 rounded-full shrink-0', color)} />;
}

function BudgetChip({ micros }: { micros: number }) {
  const dollars = micros / 1_000_000;
  return (
    <span className="text-[10px] text-muted-foreground bg-secondary px-1.5 py-0.5 rounded-sm">
      ${dollars.toFixed(0)}/d
    </span>
  );
}

function AccountNode({
  account,
  filter,
  depth,
  mccAccountId,
  clientAccountId,
}: {
  account: Account;
  filter: string;
  depth: number;
  mccAccountId: string;
  clientAccountId: string;
}) {
  const [expanded, setExpanded] = useState(true);
  const { selectedCampaignId, setSelectedCampaign, setSelectedAccount } = useAppStore();

  const filteredCampaigns = useMemo(
    () =>
      (account.campaigns ?? []).filter((c) =>
        c.name.toLowerCase().includes(filter.toLowerCase())
      ),
    [account.campaigns, filter]
  );

  const childrenHaveMatches = useMemo(() => {
    function hasMatch(acc: Account): boolean {
      if (
        (acc.campaigns ?? []).some((c) =>
          c.name.toLowerCase().includes(filter.toLowerCase())
        )
      )
        return true;
      return (acc.children ?? []).some(hasMatch);
    }
    return hasMatch(account);
  }, [account, filter]);

  if (filter && !childrenHaveMatches) return null;

  const Icon =
    account.level === 'manager'
      ? Building2
      : account.level === 'sub_manager'
        ? Users
        : Briefcase;

  return (
    <div>
      <button
        onClick={() => {
          setExpanded(!expanded);
          setSelectedAccount(account.id);
        }}
        className={cn(
          'w-full flex items-center gap-2 px-2 py-1.5 text-xs text-foreground hover:bg-secondary/60 rounded-sm transition-colors',
        )}
        style={{ paddingLeft: depth * 12 + 8 }}
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
        <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="truncate font-medium">{account.name}</span>
      </button>

      {expanded && (
        <>
          {filteredCampaigns.map((campaign) => (
            <button
              key={campaign.id}
              onClick={() => {
                setSelectedCampaign(campaign.id);
                // Always set the client account ID (the one that holds campaigns),
                // not the parent manager/sub_manager ID
                setSelectedAccount(account.level === 'client' ? account.id : clientAccountId);
              }}
              className={cn(
                'w-full flex items-center gap-1.5 px-2 py-1.5 text-xs hover:bg-secondary/60 rounded-sm transition-colors',
                selectedCampaignId === campaign.id && 'bg-secondary text-foreground',
                selectedCampaignId !== campaign.id && 'text-muted-foreground'
              )}
              style={{ paddingLeft: (depth + 1) * 12 + 20 }}
            >
              <StatusDot status={campaign.status} />
              <span className="truncate">{campaign.name}</span>
              <PhaseBadge campaignId={campaign.id} accountId={mccAccountId} />
              <span className="ml-auto">
                <BudgetChip micros={campaign.budgetAmountMicros} />
              </span>
            </button>
          ))}
          {(account.children ?? []).map((child) => (
            <AccountNode key={child.id} account={child} filter={filter} depth={depth + 1} mccAccountId={mccAccountId} clientAccountId={clientAccountId} />
          ))}
        </>
      )}
    </div>
  );
}

type StatusFilter = 'ALL' | 'ENABLED' | 'PAUSED';

// SQLite datetime('now') returns "YYYY-MM-DD HH:MM:SS" in UTC — coerce to
// ISO so Date.parse handles it consistently across browsers.
function timeAgo(sqliteUtc: string): string {
  const isoish = sqliteUtc.includes('T') ? sqliteUtc : sqliteUtc.replace(' ', 'T') + 'Z';
  const t = new Date(isoish).getTime();
  if (Number.isNaN(t)) return '?';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function Sidebar({ isHome = false, bare = false }: { isHome?: boolean; bare?: boolean }) {
  const {
    sidebarCollapsed, toggleSidebar, selectedAccountId, setSelectedAccount, connectedAccounts,
    setSelectedCampaign, setShowDashboard, setShowStudio, setShowChangelog, setShowGuidelines, setShowConversations,
  } = useAppStore();

  const navigate = useNavigate();
  // Home rail affordance (C3): clear the campaign selection + every takeover
  // panel — the same move the Header's Home button and the `g h` chord make.
  // navigate('/') is the load-bearing step: from inside /studio the campaign is
  // already null, so clearing it wouldn't move the URL — only the route change
  // leaves the Studio surface (and the two-way bridge closes showStudio).
  const goHome = () => {
    navigate('/');
    setSelectedCampaign(null);
    setShowDashboard(false);
    setShowStudio(false);
    setShowChangelog(false);
    setShowGuidelines(false);
    setShowConversations(false);
  };
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ENABLED');
  const [refreshing, setRefreshing] = useState(false);
  // Home (Story 13.5): the sidebar is an icon rail; the campaign tree
  // opens as a flyout on hover (or click-to-pin), reclaiming width for
  // the fix list. `flyoutOpen` = hover state; `flyoutPinned` = clicked.
  const [flyoutOpen, setFlyoutOpen] = useState(false);
  const [flyoutPinned, setFlyoutPinned] = useState(false);
  const queryClient = useQueryClient();

  // Determine which client account to query for campaigns
  const mccAccountId = selectedAccountId || connectedAccounts[0]?.id || '';
  const clientAccountId = useClientAccountId();

  // V11 — surface the single-source-of-truth's freshness directly to the
  // user. The previous design had an invisible 5-min TTL; this makes the
  // staleness window honest.
  const { data: syncStatus, refetch: refetchSyncStatus } = useQuery({
    queryKey: ['campaigns-sync-status', clientAccountId],
    queryFn: () => fetchCampaignsSyncStatus(clientAccountId),
    enabled: !!clientAccountId,
    refetchInterval: 30_000, // tick the "X ago" label every 30s
    staleTime: 10_000,
  });

  const handleRefresh = async () => {
    if (!clientAccountId || refreshing) return;
    setRefreshing(true);
    try {
      await forceSyncCampaigns(clientAccountId);
      // Invalidate so both the campaign list AND the sync status refetch.
      await queryClient.invalidateQueries({ queryKey: ['campaigns', clientAccountId] });
      await refetchSyncStatus();
    } catch {
      // Silent — sidebar continues to show stale data with the old timestamp.
    } finally {
      setRefreshing(false);
    }
  };

  // Fetch account hierarchy for the tree display
  const { data: hierarchy } = useQuery({
    queryKey: ['accounts-hierarchy', mccAccountId],
    queryFn: fetchAccounts,
    staleTime: 300_000,
    enabled: !!mccAccountId,
  });

  // Fetch real campaigns
  const { data: apiCampaigns } = useQuery({
    queryKey: ['campaigns', clientAccountId],
    queryFn: () => fetchCampaigns(clientAccountId),
    staleTime: 60_000,
    retry: 1,
    enabled: !!clientAccountId,
  });

  // Filter campaigns by status
  const filteredApiCampaigns = useMemo(() => {
    const campaigns = apiCampaigns ?? [];
    if (statusFilter === 'ALL') return campaigns;
    return campaigns.filter((c) => c.status === statusFilter);
  }, [apiCampaigns, statusFilter]);

  // Build account tree from real data
  // The Google Ads hierarchy API reports all accounts relative to the querying MCC,
  // so parent_id for clients points to the MCC, not the intermediate sub_manager.
  // We reconstruct the tree by placing the active client under the sub_manager.
  const accounts = useMemo(() => {
    if (!hierarchy || hierarchy.length === 0) {
      return [{
        id: clientAccountId,
        name: connectedAccounts.find((a) => a.id === mccAccountId)?.name || 'Account',
        parentId: null,
        level: 'client' as const,
        isActive: true,
        campaigns: filteredApiCampaigns,
      }];
    }

    const managers = hierarchy.filter((a) => a.level === 'manager');
    const subManagers = hierarchy.filter((a) => a.level === 'sub_manager');

    // Only show the active client (the one with campaigns)
    const activeClient = hierarchy.find((a) => a.id === clientAccountId);
    const clientNode = {
      id: clientAccountId,
      name: activeClient?.name || `Account ${clientAccountId}`,
      parentId: null,
      level: 'client' as const,
      isActive: true,
      campaigns: filteredApiCampaigns,
    };

    // If we have sub_managers, nest the client under the first one
    if (subManagers.length > 0) {
      const smNodes = subManagers.map((sm) => ({
        id: sm.id,
        name: sm.name,
        parentId: sm.parent_id,
        level: 'sub_manager' as const,
        isActive: sm.is_active,
        children: [clientNode],  // Place active client under sub_manager
      }));

      if (managers.length > 0) {
        return managers.map((m) => ({
          id: m.id,
          name: m.name,
          parentId: null,
          level: 'manager' as const,
          isActive: m.is_active,
          children: smNodes,
        }));
      }
      return smNodes;
    }

    // No sub_managers — just show manager > client
    if (managers.length > 0) {
      return managers.map((m) => ({
        id: m.id,
        name: m.name,
        parentId: null,
        level: 'manager' as const,
        isActive: m.is_active,
        children: [clientNode],
      }));
    }

    return [clientNode];
  }, [hierarchy, filteredApiCampaigns, clientAccountId, connectedAccounts, mccAccountId]);

  // Campaign counts for filter badges
  const campaignCounts = useMemo(() => {
    const all = apiCampaigns ?? [];
    return {
      all: all.length,
      enabled: all.filter((c) => c.status === 'ENABLED').length,
      paused: all.filter((c) => c.status === 'PAUSED').length,
    };
  }, [apiCampaigns]);

  // Auto-select client account
  useEffect(() => {
    if (!selectedAccountId && clientAccountId) {
      setSelectedAccount(clientAccountId);
    }
  }, [selectedAccountId, clientAccountId, setSelectedAccount]);

  // The search + status filter + sync signal + campaign tree — shared
  // between the full sidebar and the home flyout so there's one tree.
  const panelBody = (
    <>
      {/* Search */}
      <div className="p-2 space-y-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter campaigns..."
            className="h-8 text-xs pl-7 bg-secondary/50 border-border"
          />
        </div>
        {/* Status filter */}
        <div className="flex gap-1">
          {([
            { key: 'ENABLED' as StatusFilter, label: 'Active', count: campaignCounts.enabled, color: 'text-status-enabled' },
            { key: 'PAUSED' as StatusFilter, label: 'Paused', count: campaignCounts.paused, color: 'text-status-paused' },
            { key: 'ALL' as StatusFilter, label: 'All', count: campaignCounts.all, color: 'text-foreground' },
          ]).map(({ key, label, count, color }) => (
            <button
              key={key}
              onClick={() => setStatusFilter(key)}
              className={cn(
                'flex-1 text-[10px] py-1 rounded-sm transition-colors',
                statusFilter === key
                  ? 'bg-secondary text-foreground font-medium'
                  : 'text-muted-foreground hover:bg-secondary/50'
              )}
            >
              <span className={statusFilter === key ? color : ''}>{label}</span>
              <span className="ml-1 opacity-60">{count}</span>
            </button>
          ))}
        </div>
        {/* V11 — single source of truth freshness signal. Replaces the old
            invisible 5-min cache TTL: the user can SEE how fresh the data
            is and force a refresh on demand. */}
        <div className="flex items-center justify-between text-[9px] text-muted-foreground px-1">
          <span
            title={syncStatus?.last_synced_at || 'never synced'}
            className={cn(
              // After 2× the staleness threshold without a successful sync,
              // dim further so the user notices the data is genuinely old.
              syncStatus?.last_synced_at &&
                Date.now() - new Date(syncStatus.last_synced_at.replace(' ', 'T') + 'Z').getTime() >
                  (syncStatus.stale_after_seconds || 300) * 2_000
                ? 'text-amber-500/70'
                : ''
            )}
          >
            {syncStatus?.last_synced_at
              ? `synced ${timeAgo(syncStatus.last_synced_at)}`
              : 'sync pending…'}
          </span>
          <button
            onClick={handleRefresh}
            disabled={refreshing || !clientAccountId}
            className="p-1 rounded hover:bg-secondary/50 disabled:opacity-40 transition-colors"
            title="Refresh campaign list (live Google Ads API call)"
          >
            <RefreshCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Account tree */}
      <ScrollArea className="flex-1 px-1">
        {accounts.map((acc) => (
          <AccountNode key={acc.id} account={acc} filter={filter} depth={0} mccAccountId={mccAccountId} clientAccountId={clientAccountId} />
        ))}
      </ScrollArea>
    </>
  );

  // ── Home + Studio: icon rail + campaign-tree flyout (Story 13.5) ──
  // `bare` (home OR studio, decided route-side in App.tsx) collapses the
  // sidebar to the 14px rail; the campaign tree stays reachable as the
  // flyout. The rail's Home button (goHome) also exits studio, so it's the
  // one-click way back. No per-surface state to leak — the mode is derived,
  // never persisted.
  if (isHome || bare) {
    const showFlyout = flyoutOpen || flyoutPinned;
    return (
      <div
        className="relative shrink-0"
        onMouseLeave={() => setFlyoutOpen(false)}
      >
        <div className="w-14 h-full bg-sidebar border-r border-border flex flex-col items-center py-3 gap-1">
          {/* Home — the rail's top item; active (highlighted) when already
              home, and the one-click way back from anywhere else. */}
          <button
            onClick={goHome}
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-md transition-colors',
              isHome ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
            )}
            title="Home"
            aria-label="Home"
            aria-current={isHome ? 'page' : undefined}
          >
            <Home className="h-4 w-4" />
          </button>
          <button
            onClick={() => setFlyoutPinned((v) => !v)}
            onMouseEnter={() => setFlyoutOpen(true)}
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-md transition-colors',
              showFlyout ? 'bg-secondary text-foreground' : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground'
            )}
            title="Campaigns"
            aria-label="Campaigns"
            aria-expanded={showFlyout}
          >
            <Layers className="h-4 w-4" />
          </button>
        </div>

        {showFlyout && (
          <div
            className="absolute left-14 top-0 z-30 flex h-full w-70 flex-col bg-sidebar border-r border-border"
            style={{ boxShadow: 'var(--shadow-elevated)' }}
            onMouseEnter={() => setFlyoutOpen(true)}
          >
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Campaigns</span>
              <button
                onClick={() => { setFlyoutPinned(false); setFlyoutOpen(false); }}
                className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary/60 transition-colors"
                title="Close"
                aria-label="Close campaigns flyout"
              >
                <PanelLeftClose className="h-3.5 w-3.5" />
              </button>
            </div>
            {panelBody}
          </div>
        )}
      </div>
    );
  }

  if (sidebarCollapsed) {
    return (
      <div className="w-12 bg-sidebar border-r border-border flex flex-col items-center py-2 shrink-0">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleSidebar}>
          <PanelLeft className="h-4 w-4 text-muted-foreground" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-70 bg-sidebar border-r border-border flex flex-col shrink-0">
      {panelBody}

      {/* Collapse button */}
      <div className="p-2 border-t border-border">
        <Button
          variant="ghost"
          size="sm"
          className="w-full text-xs text-muted-foreground gap-2"
          onClick={toggleSidebar}
        >
          <PanelLeftClose className="h-3.5 w-3.5" />
          Collapse
        </Button>
      </div>
    </div>
  );
}
