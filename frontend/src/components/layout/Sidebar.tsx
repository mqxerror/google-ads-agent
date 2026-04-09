import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronRight,
  ChevronDown,
  PanelLeftClose,
  PanelLeft,
  Search,
  Building2,
  Users,
  Briefcase,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns, fetchAccounts, fetchCampaignGoals } from '@/lib/api';
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
}: {
  account: Account;
  filter: string;
  depth: number;
  mccAccountId: string;
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
            <AccountNode key={child.id} account={child} filter={filter} depth={depth + 1} mccAccountId={mccAccountId} />
          ))}
        </>
      )}
    </div>
  );
}

type StatusFilter = 'ALL' | 'ENABLED' | 'PAUSED';

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, selectedAccountId, setSelectedAccount, connectedAccounts } = useAppStore();
  const [filter, setFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ENABLED');

  // Determine which client account to query for campaigns
  const mccAccountId = selectedAccountId || connectedAccounts[0]?.id || '';
  const clientAccountId = useClientAccountId();

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
      </div>

      {/* Account tree */}
      <ScrollArea className="flex-1 px-1">
        {accounts.map((acc) => (
          <AccountNode key={acc.id} account={acc} filter={filter} depth={0} mccAccountId={mccAccountId} />
        ))}
      </ScrollArea>

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
