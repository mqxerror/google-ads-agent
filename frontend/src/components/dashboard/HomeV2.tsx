/**
 * HomeV2 — the Epic 13 command-center home (Story 13.5 shell).
 *
 * One column, one focus (design brief §1). Replaces the old bulky
 * AccountOverview composition (lifetime KPI grid + OutcomeDashboard +
 * ConversationGraph + campaign grid). Top → bottom:
 *   header (account · date-range · Create Campaign)
 *   ① FixListStrip     (hero mount — calm zero-state; 13.6 fills it)
 *   ② KpiCards         (Spend · Conversions · CPA · Conv rate)
 *   ③ CampaignsRanked  (compact ranked table)
 *   ④ AgentActivity    (recent activity · upcoming) — capped + slim
 *
 * Everything below the header obeys zero-state discipline — an empty
 * section renders nothing, so the page collapses gracefully to just the
 * fix-list strip's calm empty state on a brand-new account.
 *
 * Chat is NOT here: on the home page it's summoned via the floating
 * button / ⌘K drawer (HomeChatDock), not a parked rail. The sidebar is
 * an icon rail with a flyout tree. Both handled by the layout.
 */

import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Rocket } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useAccountEvents } from '@/hooks/useAccountEvents';
import { Button } from '@/components/ui/button';
import HomeDateRangePicker, { windowFor } from './HomeDateRangePicker';
import FixListStrip from './FixListStrip';
import KpiCards from './KpiCards';
import CampaignsRanked from './CampaignsRanked';
import AgentActivity from './AgentActivity';
import HomeSkeleton from './HomeSkeleton';
import {
  fetchCampaigns, fetchMetricsOverview, fetchFixActions, fetchAccountReportMeta,
} from '@/lib/api';
import type { Campaign } from '@/types';

export default function HomeV2({ onOpenBuilder }: { onOpenBuilder?: () => void }) {
  const accountId = useClientAccountId();
  const { homeRangeDays, selectedAccountId, connectedAccounts, lastCampaignId, setSelectedCampaign } =
    useAppStore();

  // C1: open ONE EventSource per account so sync_completed / external_change
  // pushes refresh the home live, without a poll or a reload.
  useAccountEvents(accountId);

  // ── C4: parallel prefetch (fire-and-forget) ──────────────────────────
  // Warm the four home queries in parallel on mount so a warm navigation back
  // to home renders instantly. Same keys/queryFns the sections use (shared
  // cache). Non-blocking — render never waits on these. The `useQuery`s below
  // and inside each section stay the source of truth; prefetch only pre-fills.
  const qc = useQueryClient();
  useEffect(() => {
    if (!accountId) return;
    const { dateFrom, dateTo } = windowFor(homeRangeDays);
    qc.prefetchQuery({ queryKey: ['metrics-overview', accountId, homeRangeDays], queryFn: () => fetchMetricsOverview(accountId, homeRangeDays), staleTime: 120_000 });
    qc.prefetchQuery({ queryKey: ['campaigns', accountId, dateFrom, dateTo], queryFn: () => fetchCampaigns(accountId, dateFrom, dateTo), staleTime: 60_000 });
    qc.prefetchQuery({ queryKey: ['fix-actions', accountId], queryFn: () => fetchFixActions(accountId), staleTime: 30_000 });
    qc.prefetchQuery({ queryKey: ['account-report-meta', accountId], queryFn: () => fetchAccountReportMeta(accountId), staleTime: 30_000 });
  }, [qc, accountId, homeRangeDays]);

  // ── C4: first-paint skeleton gate ────────────────────────────────────
  // Until the primary home queries resolve for the FIRST time (no cached data
  // yet), show in-layout skeletons of the real geometry instead of a spinner /
  // blank flash. Once data (or an empty result) lands, the real sections take
  // over and own their own loading/zero states. Keyed off the shared caches so
  // warm navs skip the skeleton entirely (data already there → render instant).
  const { dateFrom: gFrom, dateTo: gTo } = windowFor(homeRangeDays);
  const { isLoading: metricsFirstLoad } = useQuery({
    queryKey: ['metrics-overview', accountId, homeRangeDays],
    queryFn: () => fetchMetricsOverview(accountId, homeRangeDays),
    staleTime: 120_000,
    enabled: !!accountId,
  });
  const { isLoading: rankedFirstLoad } = useQuery({
    queryKey: ['campaigns', accountId, gFrom, gTo],
    queryFn: () => fetchCampaigns(accountId, gFrom, gTo),
    staleTime: 60_000,
    enabled: !!accountId,
  });
  // Skeleton only on the genuine cold first paint (both primary reads pending).
  const showSkeleton = !!accountId && metricsFirstLoad && rankedFirstLoad;

  const accountName =
    connectedAccounts.find((a) => a.id === selectedAccountId)?.name ||
    connectedAccounts[0]?.name ||
    'Account';

  // Warm the base campaign cache so the sidebar flyout + chat share it — and so
  // the "Continue where you left off" card can resolve the last campaign's name.
  const { data: campaigns } = useQuery({
    queryKey: ['campaigns', accountId],
    queryFn: () => fetchCampaigns(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  // C2 support: resolve the last-viewed campaign's name from the warm cache. On
  // the home no campaign is selected, so the card always renders when a memory
  // exists. Name falls back gracefully when the roster hasn't loaded yet.
  const lastCampaign = lastCampaignId
    ? (campaigns as Campaign[] | undefined)?.find((c) => c.id === lastCampaignId)
    : undefined;
  const lastCampaignName = lastCampaign?.name || 'your last campaign';

  return (
    <div className="mx-auto max-w-[1000px] px-6 py-5">
      {/* Header */}
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-foreground">{accountName}</h1>
          {/* Account context bar (B5): CID always; currency + timezone omitted —
              they are not exposed to the client (AccountV2 carries neither, and
              no endpoint queries Google's currency_code / time_zone). Conservative:
              show what is true, fabricate nothing. */}
          <p className="text-xs text-subtle">
            Command center<span className="mx-1.5 text-border">·</span>CID {accountId}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <HomeDateRangePicker />
          {onOpenBuilder && (
            <Button onClick={onOpenBuilder} className="gap-2">
              <Rocket className="h-4 w-4" />
              Create Campaign
            </Button>
          )}
        </div>
      </header>

      {/* Continue where you left off (C2): quiet resume affordance. Absent when
          there is no last-campaign memory (zero-state discipline). */}
      {lastCampaignId && (
        <button
          onClick={() => setSelectedCampaign(lastCampaignId)}
          className="mb-4 flex w-full items-center gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-left transition-colors hover:bg-secondary/40"
        >
          <span className="text-[11px] font-medium uppercase tracking-wide text-subtle">
            Continue where you left off
          </span>
          <span className="min-w-0 flex-1 truncate text-sm text-foreground">{lastCampaignName}</span>
          <ArrowRight className="h-4 w-4 shrink-0 text-subtle" />
        </button>
      )}

      {/* Stacked sections — dense command center, tightened 2026-07-05. C4:
          cold first paint shows in-layout skeletons (strip/KPI/table) instead
          of a spinner or blank flash; warm navs skip it and render instantly. */}
      {showSkeleton ? (
        <HomeSkeleton />
      ) : (
        <div className="space-y-4">
          <FixListStrip accountId={accountId} />
          <KpiCards accountId={accountId} rangeDays={homeRangeDays} />
          <CampaignsRanked accountId={accountId} rangeDays={homeRangeDays} />
          <AgentActivity accountId={accountId} />
        </div>
      )}
    </div>
  );
}
