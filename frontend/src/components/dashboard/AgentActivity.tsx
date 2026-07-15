/**
 * AgentActivity — the home page's "what did the agent do / what's next"
 * section (Epic 13, Story 13.8; tightened 2026-07-05 per operator "home is
 * too long"). Replaces the old Agent Performance + Conversation Map panels.
 *
 * Blocks (each obeys zero-state discipline — absent when empty):
 *   a) Recent activity — ONE unified, most-recent-first list (capped ~5) that
 *      merges the former "Change log" (executed recommendations w/ before→after
 *      from GET /accounts/:id/outcomes, outcome_tracker.py) and "Recent actions"
 *      (the agent-action timeline from /accounts/:id/activity). They were
 *      redundant stacked, so they are now interleaved by timestamp. A measured
 *      change row shows "CPA $X → $Y" (improved / degraded tint); a pending one
 *      shows "measuring…" — never a fabricated delta. RENDERED READ-ONLY: there
 *      is NO revert endpoint in the backend, so no Undo affordance (would 404,
 *      verified 2026-07-04). A measured-summary line appears only after ≥1
 *      measured action (the "Agent Performance" zero-state ban).
 *   b) Upcoming — next Scheduled Plans as a slim inline strip (capped ~3).
 *
 * "Recent threads" was REMOVED from the home (2026-07-05): it lives on the
 * Conversations page. A single quiet "View conversations →" link replaces it.
 *
 * Trust copy sits under the write surfaces (brief §8).
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, CalendarClock, History, ExternalLink } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
import {
  fetchUpcomingPlans,
  fetchOutcomes,
  fetchExternalChanges,
  type OutcomeRecord,
  type ExternalChange,
} from '@/lib/api';
import { statusVisual, relativeTime } from '@/components/plans/planHelpers';
import { cn } from '@/lib/utils';

interface AgentActivityProps {
  accountId: string;
}

interface ActivityItem {
  timestamp: string;
  role: string;
  role_id: string;
  avatar: string;
  action: string;
  type: string;
}
interface CampaignSummary {
  campaign_id: string;
  campaign_name: string;
  recent_activities: ActivityItem[];
}

/** One row in the unified "Recent activity" list — either a measured change
 *  (carries before→after) or a plain timeline action. `sortKey` is the raw
 *  timestamp used to interleave both sources newest-first. */
interface UnifiedRow {
  key: string;
  sortKey: string;
  campaignId: string | null;
  campaignName: string;
  text: string;
  ago: string;
  /** present only for change-log rows */
  ba?: { before: string; after: string; metric: string } | null;
  outcome?: OutcomeRecord['outcome'];
}

/** Parse a 'YYYY-MM-DD HH:MM[:SS]' timestamp (assumed UTC) to millis, or null. */
function parseTs(ts: string): number | null {
  const t = new Date(ts.replace(' ', 'T') + (/[Z+]/.test(ts) ? '' : 'Z')).getTime();
  return Number.isFinite(t) ? t : null;
}

/** Relative "…ago" from a 'YYYY-MM-DD HH:MM[:SS]' timestamp (assumed UTC). */
function actionTime(ts: string): string {
  const t = parseTs(ts);
  if (t === null) return '';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`;
  return new Date(t).toLocaleDateString();
}

/** Absolute local timestamp for a title/hover, e.g. "Jul 7, 2026, 2:02 PM".
 *  Empty string when unparseable so `title=""` renders no tooltip. */
function absoluteTime(ts?: string | null): string {
  if (!ts) return '';
  const t = parseTs(ts);
  return t === null ? '' : new Date(t).toLocaleString();
}

/** Friendly label for a roster field that changed outside the app. */
const EXTERNAL_FIELD_LABELS: Record<string, string> = {
  status: 'Status',
  bidding_strategy: 'Bidding',
  budget_micros: 'Budget',
};
function externalFieldLabel(field: string): string {
  return EXTERNAL_FIELD_LABELS[field] || field;
}

/** Render an external-change value for display — budget micros become dollars;
 *  everything else passes through (null → "—"). */
function externalValue(field: string, raw: string | null): string {
  if (raw === null || raw === '') return '—';
  if (field === 'budget_micros') {
    const micros = Number(raw);
    if (Number.isFinite(micros)) return `$${(micros / 1_000_000).toFixed(0)}`;
  }
  return raw;
}

/** A compact "$X → $Y" before→after when the recommendation was measured,
 *  otherwise null. Prefers CPA (the tracker's primary metric), falls back to
 *  CTR. Never fabricates a value that isn't in the delta. */
function beforeAfter(rec: OutcomeRecord): { before: string; after: string; metric: string } | null {
  const d = rec.delta;
  if (!d) return null;
  if (typeof d.cpa_before === 'number' && typeof d.cpa_after === 'number') {
    return { before: `$${d.cpa_before.toFixed(0)}`, after: `$${d.cpa_after.toFixed(0)}`, metric: 'CPA' };
  }
  if (typeof d.ctr_before === 'number' && typeof d.ctr_after === 'number') {
    return { before: `${d.ctr_before.toFixed(1)}%`, after: `${d.ctr_after.toFixed(1)}%`, metric: 'CTR' };
  }
  return null;
}

export default function AgentActivity({ accountId }: AgentActivityProps) {
  const { setSelectedCampaign, setShowConversations } = useAppStore();

  const { data: activityData } = useQuery({
    queryKey: ['account-activity', accountId],
    queryFn: async () => {
      const res = await fetch(`/api/accounts/${accountId}/activity`);
      return res.json() as Promise<{ campaigns: CampaignSummary[]; total_activities: number }>;
    },
    staleTime: 30_000,
    enabled: !!accountId,
  });

  const { data: outcomes } = useQuery({
    queryKey: ['account-outcomes', accountId],
    queryFn: () => fetchOutcomes(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  const { data: plans = [] } = useQuery({
    queryKey: ['plans-upcoming', accountId],
    queryFn: () => fetchUpcomingPlans(accountId),
    enabled: !!accountId,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  // C5: out-of-band roster changes — "why does the account look different?"
  const { data: externalChanges = [] } = useQuery({
    queryKey: ['external-changes', accountId],
    queryFn: () => fetchExternalChanges(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  // campaign_id → name, borrowed from the activity payload (outcomes carry
  // only the id).
  const campaignName = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of activityData?.campaigns ?? []) {
      if (c.campaign_id) m.set(c.campaign_id, c.campaign_name);
    }
    return m;
  }, [activityData]);

  // ── Unified "Recent activity": merge change-log + timeline, newest first,
  //    cap at ~5. The two were redundant stacked; interleave by timestamp.
  const recentActivity = useMemo<UnifiedRow[]>(() => {
    const rows: UnifiedRow[] = [];

    for (const rec of outcomes?.recent ?? []) {
      const ts = rec.executed_at || '';
      rows.push({
        key: `chg-${rec.id}`,
        sortKey: ts,
        campaignId: rec.campaign_id || null,
        campaignName: (rec.campaign_id && campaignName.get(rec.campaign_id)) || 'Account',
        text: rec.action_detail,
        ago: actionTime(ts),
        ba: beforeAfter(rec),
        outcome: rec.outcome,
      });
    }

    for (const c of activityData?.campaigns ?? []) {
      for (const a of c.recent_activities ?? []) {
        const ts = a.timestamp || '';
        rows.push({
          key: `act-${c.campaign_id}-${ts}-${a.action.slice(0, 12)}`,
          sortKey: ts,
          campaignId: c.campaign_id || null,
          campaignName: c.campaign_name || 'Account',
          text: a.action.replace(/[*#]/g, '').trim(),
          ago: actionTime(ts),
        });
      }
    }

    return rows.sort((a, b) => b.sortKey.localeCompare(a.sortKey)).slice(0, 5);
  }, [outcomes, activityData, campaignName]);

  const measured = outcomes?.measured ?? 0;
  const upcoming = useMemo(() => plans.slice(0, 3), [plans]);
  const external = useMemo<ExternalChange[]>(() => externalChanges.slice(0, 5), [externalChanges]);

  const hasAnything = recentActivity.length > 0 || upcoming.length > 0 || external.length > 0;
  // Zero-state discipline: nothing to show → the whole section is absent.
  if (!hasAnything) return null;

  return (
    <section aria-label="Agent activity" className="space-y-3">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-foreground">Agent activity</h2>
        <button
          onClick={() => setShowConversations(true)}
          className="text-[11px] text-accent transition-colors hover:underline"
        >
          View conversations →
        </button>
      </div>

      {/* a) Recent activity — unified change-log + timeline, newest first. */}
      {recentActivity.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-subtle">
              <History className="h-3 w-3" />
              Recent activity
            </div>
            {/* Agent-Performance summary — only after ≥1 measured action. */}
            {measured >= 1 && (
              <span className="text-[11px] text-subtle">
                {measured} measured
                {(outcomes?.improved ?? 0) > 0 && <> · {outcomes?.improved} improved</>}
              </span>
            )}
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="divide-y divide-border">
              {recentActivity.map((row) => (
                <button
                  key={row.key}
                  onClick={() => row.campaignId && setSelectedCampaign(row.campaignId)}
                  className="flex w-full items-center gap-3 px-4 py-2 text-left transition-colors hover:bg-secondary/40"
                >
                  <span className="w-32 shrink-0 truncate text-xs text-muted-foreground">{row.campaignName}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">{row.text}</span>
                  {row.ba ? (
                    <span
                      className={cn(
                        'hidden shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium tabular-nums sm:inline-flex',
                        row.outcome === 'improved'
                          ? 'bg-success-soft text-success'
                          : row.outcome === 'degraded'
                            ? 'bg-danger-soft text-danger'
                            : 'bg-secondary text-muted-foreground',
                      )}
                      title={`${row.ba.metric} before → after`}
                    >
                      {row.ba.before}
                      <ArrowRight className="h-2.5 w-2.5" />
                      {row.ba.after}
                    </span>
                  ) : row.ba === null && row.outcome !== undefined ? (
                    <span className="hidden shrink-0 text-[10px] text-subtle sm:inline">measuring…</span>
                  ) : null}
                  <span
                    className="w-16 shrink-0 text-right text-[11px] text-subtle"
                    title={absoluteTime(row.sortKey)}
                  >
                    {row.ago}
                  </span>
                </button>
              ))}
            </div>
          </div>
          {/* Trust line — read-only log (no revert API exists). */}
          <p className="mt-1.5 text-[11px] text-subtle">Every write is reviewed. Every write is reversible.</p>
        </div>
      )}

      {/* a2) Changed outside the app (C5) — out-of-band roster changes with no
             app-side mutation. The answer to "why does the account look
             different?". Only rendered when there are rows. */}
      {external.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-subtle">
            <ExternalLink className="h-3 w-3" />
            Changed outside the app
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="divide-y divide-border">
              {external.map((c) => {
                const name = campaignName.get(c.campaign_id) || 'Campaign';
                return (
                  <button
                    key={c.id}
                    onClick={() => c.campaign_id && setSelectedCampaign(c.campaign_id)}
                    className="flex w-full items-center gap-3 px-4 py-2 text-left transition-colors hover:bg-secondary/40"
                  >
                    <span className="w-32 shrink-0 truncate text-xs text-muted-foreground">{name}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                      {externalFieldLabel(c.field)}{' '}
                      <span className="text-subtle tabular-nums">
                        {externalValue(c.field, c.before)}
                      </span>{' '}
                      <ArrowRight className="inline h-2.5 w-2.5 text-subtle" />{' '}
                      <span className="tabular-nums">{externalValue(c.field, c.after)}</span>
                    </span>
                    <span
                      className="w-16 shrink-0 text-right text-[11px] text-subtle"
                      title={absoluteTime(c.detected_at)}
                    >
                      {actionTime(c.detected_at)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* b) Upcoming scheduled plans — slim inline strip, capped ~3. */}
      {upcoming.length > 0 && (
        <div>
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-subtle">
            <CalendarClock className="h-3 w-3" />
            Upcoming
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            <div className="divide-y divide-border">
              {upcoming.map((p) => {
                const sv = statusVisual(p.status);
                return (
                  <button
                    key={p.id}
                    onClick={() => {
                      if (!p.campaign_id) return;
                      setSelectedCampaign(p.campaign_id);
                      setTimeout(() => window.dispatchEvent(new CustomEvent('plans:open-tab')), 0);
                    }}
                    className="flex w-full items-center gap-3 px-4 py-2 text-left transition-colors hover:bg-secondary/40"
                  >
                    <span className={cn('h-2 w-2 shrink-0 rounded-full', sv.dot, sv.pulse && 'studio-pulse')} aria-label={sv.label} />
                    <span className="w-32 shrink-0 truncate text-xs text-muted-foreground">{p.campaign_name || 'Account'}</span>
                    <span className="min-w-0 flex-1 truncate text-sm text-foreground">{p.title}</span>
                    <span
                      className="shrink-0 text-[11px] text-subtle"
                      title={absoluteTime(p.next_run_at || p.run_at)}
                    >
                      {relativeTime(p.next_run_at || p.run_at)}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
