/**
 * FixListStrip — the home page's hero "Needs attention" strip (Epic 13,
 * Story 13.6). This is the surface of the Account Director audit: the
 * latest persisted account report + always-fresh fast-signals, each
 * rendered as ONE money-ranked, inline-approvable row.
 *
 * Contract (backend, live at the operator's end-of-run restart):
 *   GET  /api/accounts/:id/actions        → FixActionsResponse (money-ranked)
 *   POST /api/accounts/:id/actions/:key/decide  {decision}
 *   GET  /api/accounts/:id/account-report → staleness + zero-state
 * See src/lib/api.ts (shapes mirror finding_actions.py / account_report_store.py).
 *
 * Design (research/homepage-redesign-brief.md §4-8):
 *  - header: "Needs attention" · "Total recoverable: $X/wk" · staleness
 *    ("audited 2h ago", amber when stale) · [Run again]
 *  - one compact TABLE, generous rows, subtle dividers — no boxes-in-boxes
 *  - each row is one line (icon · title · campaign chips · $-impact · actions);
 *    click expands the specialist's evidence (progressive disclosure)
 *  - actionable rows: [Approve] [Approve once] [Deny] + [Review in chat];
 *    gated categories show a quiet "needs sign-off" hint; advisory rows show
 *    their reason inline with NO buttons
 *  - trust line under the actions: "Every write is reviewed. Every write is
 *    reversible."
 *  - zero-state (no findings): the calm placeholder (kept from 13.5) — the
 *    ONE section allowed a designed empty state, because it IS the page lead.
 *
 * There is no faked recoverable figure: `total_recoverable_wk` is the server's
 * sum of quantified, non-denied, actionable impacts.
 */

import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ShieldCheck, RefreshCw, ChevronDown, Loader2, Wallet, Gauge, Power,
  MapPin, Ban, Search, ClipboardList, Info, MessageSquare, Lock,
} from 'lucide-react';
import {
  fetchFixActions, fetchAccountReportMeta, decideFixAction,
  type FixAction, type FixDecision, type AccountReportMeta,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import FreshnessChip from './FreshnessChip';
import InfoHover from './InfoHover';
import { toFreshnessState } from './KpiCards';
import { useSyncNow } from '@/hooks/useSyncNow';

interface FixListStripProps {
  accountId: string;
}

/** Category → leading glyph. Keeps rows scannable without a colour language. */
const CATEGORY_ICON: Record<string, typeof Wallet> = {
  budget: Wallet,
  bids: Gauge,
  status: Power,
  geo: MapPin,
  negative_keyword: Ban,
  search_terms: Search,
  audit: ClipboardList,
  report: ClipboardList,
  other: Info,
};

function money(v: number): string {
  return `$${Math.round(v).toLocaleString('en-US')}`;
}

/** "$120/wk" or "--" when unquantified. */
function impactLabel(v: number | null): string {
  return v && v > 0 ? `${money(v)}/wk` : '--';
}

/** "Jul 8" from an ISO date (YYYY-MM-DD). Mirrors FreshnessChip.formatThroughDate
 *  (which is not exported). Returns the raw string on parse fail, null on empty. */
function formatThroughDate(iso?: string | null): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Staleness chip text from the report meta. Amber handled by the caller. */
function stalenessLabel(report?: AccountReportMeta): string {
  if (!report || !report.exists || report.age_hours == null) return '';
  const h = report.age_hours;
  if (h < 1) {
    const m = Math.max(1, Math.round((report.age_minutes ?? h * 60)));
    return `audited ${m}m ago`;
  }
  if (h < 48) return `audited ${Math.round(h)}h ago`;
  return `audited ${Math.round(h / 24)}d ago`;
}

export default function FixListStrip({ accountId }: FixListStripProps) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [auditing, setAuditing] = useState(false);

  const { data: actionsData, isLoading: actionsLoading } = useQuery({
    queryKey: ['fix-actions', accountId],
    queryFn: () => fetchFixActions(accountId),
    enabled: !!accountId,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const { data: reportData } = useQuery({
    queryKey: ['account-report-meta', accountId],
    queryFn: () => fetchAccountReportMeta(accountId),
    enabled: !!accountId,
    staleTime: 30_000,
  });

  const report = reportData?.report;
  const freshness = reportData?.freshness;
  const actions = actionsData?.actions ?? [];
  const recoverable = actionsData?.total_recoverable_wk ?? 0;
  const { syncNow, isSyncing } = useSyncNow(accountId);

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['fix-actions', accountId] });
    qc.invalidateQueries({ queryKey: ['account-report-meta', accountId] });
  }, [qc, accountId]);

  const showFlash = useCallback((msg: string) => {
    setFlash(msg);
    window.setTimeout(() => setFlash((cur) => (cur === msg ? null : cur)), 3200);
  }, []);

  // ── Decide (Approve / Approve once / Deny) ─────────────────────────
  // Match the PlansPanel idiom: per-row busy spinner, refetch on success.
  // The three buttons route through the backend's existing plan/approval +
  // scope-guard path — the strip is a shortcut to it, never a direct write.
  const decide = useCallback(
    async (a: FixAction, decision: FixDecision) => {
      setBusyKey(a.finding_key);
      try {
        const res = await decideFixAction(accountId, a.finding_key, decision);
        if (res.error) {
          showFlash(res.error);
        } else if (decision === 'deny') {
          showFlash('Finding dismissed. It returns only if a re-audit changes it.');
        } else if (res.requires_approval) {
          showFlash('Parked for your sign-off. Approve it from the Plans tab.');
        } else if (res.fired) {
          showFlash('Approved and running now.');
        } else {
          showFlash('Approved and scheduled.');
        }
      } catch {
        showFlash('Something went wrong. Nothing was changed.');
      } finally {
        setBusyKey(null);
        refresh();
      }
    },
    [accountId, refresh, showFlash],
  );

  // ── Run again — account-wide audit (reuses POST /api/workflows/run SSE) ─
  // Fires an account-wide Team Audit (campaign_id:null → account mode). We
  // optimistically show "auditing…", tail the SSE only to know when it lands,
  // then refetch so the fresh report + fix list replace the stale one.
  const runAgain = useCallback(async () => {
    if (auditing || !accountId) return;
    setAuditing(true);
    showFlash('Auditing the account… this can take a couple of minutes.');
    try {
      const res = await fetch('/api/workflows/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId, campaign_id: null, campaign_name: null }),
      });
      const reader = res.body?.getReader();
      if (!reader) throw new Error('no stream');
      const decoder = new TextDecoder();
      let buffer = '';
      let done = false;
      while (!done) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const ev = JSON.parse(raw) as { type?: string; message?: string };
            if (ev.type === 'workflow_done') { done = true; }
            if (ev.type === 'error') { done = true; showFlash(ev.message || 'Audit failed.'); }
          } catch { /* skip partial */ }
        }
      }
      showFlash('Audit complete. Fix list refreshed.');
    } catch {
      // The run itself is decoupled from this stream on the backend; a dropped
      // connection doesn't cancel it. Refetch anyway to pick up whatever landed.
      showFlash('Lost the live stream. Refreshing the fix list.');
    } finally {
      setAuditing(false);
      refresh();
    }
  }, [accountId, auditing, refresh, showFlash]);

  const reviewInChat = useCallback((a: FixAction) => {
    const camp = a.campaign_name || (a.campaign_ids[0] ? `campaign ${a.campaign_ids[0]}` : 'the account');
    const impact = a.dollar_impact_wk ? ` (est. ${money(a.dollar_impact_wk)}/wk)` : '';
    const text =
      `Let's review this finding from the account audit for ${camp}${impact}:\n\n` +
      `"${a.title}"\n\n${a.detail || a.diff_preview}\n\nWhat do you recommend, and should I approve it?`;
    window.dispatchEvent(new CustomEvent('home-chat:open', { detail: { text, roleId: 'director' } }));
  }, []);

  // ── Zero-state (kept from 13.5) ────────────────────────────────────
  // While loading OR when there are genuinely no findings, render the calm
  // placeholder — this is the ONE section allowed a designed empty state
  // (brief §7), since its absence would look broken on the page's lead.
  if (actionsLoading || actions.length === 0) {
    const nextAudit = report?.generated_at
      ? `Last audited ${stalenessLabel(report).replace('audited ', '')}.`
      : 'The next account audit will surface the biggest recoverable spend here.';
    return (
      <section aria-label="Needs attention" className="rounded-xl border border-border bg-card px-5 py-6">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-success-soft">
            <ShieldCheck className="h-4 w-4 text-success" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold text-foreground">
              {actionsLoading ? 'Checking the account…' : 'No open findings'}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              {actionsLoading
                ? 'Reading the latest audit and fresh signals.'
                : `${nextAudit} Each finding lands here ranked by dollar impact — with a one-click action.`}
            </p>
          </div>
          {!actionsLoading && accountId && (
            <button
              onClick={runAgain}
              disabled={auditing || isSyncing}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-secondary/40 hover:text-foreground disabled:opacity-60"
            >
              {auditing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
              {auditing ? 'Auditing…' : 'Run again'}
            </button>
          )}
        </div>
      </section>
    );
  }

  const stale = !!report?.is_stale && !!report?.exists;
  const staleTxt = stalenessLabel(report);

  return (
    <section aria-label="Needs attention">
      {/* Header — count · total recoverable · staleness · Run again */}
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="flex items-baseline gap-2.5">
          <h2 className="text-sm font-semibold text-foreground">Needs attention</h2>
          {recoverable > 0 && (
            <span className="text-xs text-muted-foreground">
              Total recoverable: <span className="font-semibold text-foreground tabular-nums">{money(recoverable)}/wk</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {/* Data-age chip (A3): the age of the METRICS the audit ran on — a
              separate dimension from the "audited Xh ago" AUDIT age beside it. */}
          {freshness && (() => {
            const fState = toFreshnessState(freshness.state);
            const canSync = fState === 'stale' || fState === 'error';
            return (
              <FreshnessChip
                state={fState}
                dataThroughDate={freshness.data_through_date}
                ageMinutes={freshness.age_minutes}
                detail={freshness.detail}
                syncing={isSyncing}
                onSyncNow={canSync ? syncNow : undefined}
              />
            );
          })()}
          {staleTxt && (() => {
            // The audit label cross-references the data-through date when the
            // METRICS the audit ran on are stale — surfacing the quiet danger of
            // an audit that's recent but computed on old numbers. Amber then, or
            // amber if the AUDIT itself is old (existing `stale` flag).
            const fState = freshness ? toFreshnessState(freshness.state) : null;
            const dataStale = fState === 'stale' || fState === 'error';
            const through = dataStale ? formatThroughDate(freshness?.data_through_date) : null;
            const amber = stale || (dataStale && !!through);
            if (dataStale && through) {
              return (
                <span className={cn('inline-flex items-center gap-1 text-[11px] tabular-nums', 'text-warning')}>
                  {`${staleTxt} · on data through ${through}`}
                  <InfoHover title="Audited on stale data" label="Why this audit may be out of date">
                    This audit is recent but the metrics it analyzed only go through {through}. Run it again after a fresh sync for current findings.
                  </InfoHover>
                </span>
              );
            }
            return (
              <span
                className={cn('text-[11px] tabular-nums', amber ? 'text-warning' : 'text-subtle')}
                title={stale ? 'This audit is getting old. Run it again for fresh findings.' : undefined}
              >
                {staleTxt}
              </span>
            );
          })()}
          <button
            onClick={runAgain}
            disabled={auditing || isSyncing}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-secondary/40 hover:text-foreground disabled:opacity-60"
          >
            {auditing ? <Loader2 className="h-3 w-3 animate-spin" /> : <RefreshCw className="h-3 w-3" />}
            {auditing ? 'Auditing…' : 'Run again'}
          </button>
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="divide-y divide-border">
          {actions.map((a) => (
            <FixRow
              key={a.finding_key}
              action={a}
              expanded={expanded === a.finding_key}
              busy={busyKey === a.finding_key}
              onToggle={() => setExpanded((k) => (k === a.finding_key ? null : a.finding_key))}
              onDecide={(d) => decide(a, d)}
              onReview={() => reviewInChat(a)}
            />
          ))}
        </div>
      </div>

      {/* Trust line under the write surface (brief §8). */}
      <p className="mt-2 text-[11px] text-subtle">Every write is reviewed. Every write is reversible.</p>

      {/* Transient inline feedback (the app has no toast system — matches the
          Settings inline-message idiom). */}
      {flash && (
        <p className="mt-1 text-[11px] text-muted-foreground" role="status">{flash}</p>
      )}
    </section>
  );
}

// ── One fix-list row ─────────────────────────────────────────────────

function FixRow({
  action: a, expanded, busy, onToggle, onDecide, onReview,
}: {
  action: FixAction;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  onDecide: (d: FixDecision) => void;
  onReview: () => void;
}) {
  const Icon = CATEGORY_ICON[a.action_category] ?? Info;
  const chips = a.campaign_ids.length > 0
    ? [a.campaign_name || `Campaign ${a.campaign_ids[0]}`]
    : [];
  const evidence = a.detail || a.diff_preview;

  return (
    <div className={cn('transition-colors', expanded && 'bg-secondary/30')}>
      {/* Summary line — the whole line toggles the disclosure. */}
      <button
        onClick={onToggle}
        aria-expanded={expanded}
        className="grid w-full grid-cols-[auto_1fr_auto_auto] items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-secondary/40"
      >
        <span
          className={cn(
            'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg',
            a.actionable ? 'bg-accent-soft text-accent' : 'bg-secondary text-muted-foreground',
          )}
        >
          <Icon className="h-3.5 w-3.5" />
        </span>

        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm text-foreground">{a.title}</span>
          {a.source === 'signal' && (
            <span className="hidden shrink-0 items-center gap-1 rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline-flex">
              last 7d
              <InfoHover title="Fast signal" label="What the last-7-days window means">
                Fast signals scan the last 7 days of local metrics. Wasted spend is money spent with zero conversions over that window.
              </InfoHover>
            </span>
          )}
          {chips.map((c) => (
            <span
              key={c}
              className="hidden shrink-0 truncate rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline-block sm:max-w-[160px]"
              title={c}
            >
              {c}
            </span>
          ))}
          {!a.actionable && (
            <span className="hidden shrink-0 items-center gap-1 text-[10px] text-subtle md:inline-flex">
              <Info className="h-3 w-3" /> advisory
            </span>
          )}
        </span>

        <span
          className={cn(
            'w-20 text-right text-sm tabular-nums',
            a.dollar_impact_wk && a.dollar_impact_wk > 0 ? 'font-semibold text-foreground' : 'text-subtle',
          )}
          title={a.dollar_impact_wk ? `Estimated recoverable ${money(a.dollar_impact_wk)} per week` : 'Not quantified'}
        >
          {impactLabel(a.dollar_impact_wk)}
        </span>

        <ChevronDown
          className={cn('h-4 w-4 shrink-0 text-subtle transition-transform', expanded && 'rotate-180')}
        />
      </button>

      {/* Disclosure — evidence + controls. Nothing verbose visible by default. */}
      {expanded && (
        <div className="px-4 pb-3.5 pl-14">
          {evidence && (
            <p className="mb-3 whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">{evidence}</p>
          )}

          {a.actionable ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <RowButton onClick={() => onDecide('approve')} busy={busy} variant="primary">Approve</RowButton>
              <RowButton onClick={() => onDecide('approve_once')} busy={busy} variant="outline">Approve once</RowButton>
              <RowButton onClick={() => onDecide('deny')} busy={busy} variant="ghost-danger">Deny</RowButton>
              <button
                onClick={onReview}
                disabled={busy}
                className="inline-flex h-6 items-center gap-1 rounded px-2 text-xs text-muted-foreground transition-colors hover:text-accent disabled:opacity-60"
              >
                <MessageSquare className="h-3 w-3" /> Review in chat
              </button>
              {a.requires_approval && (
                <span className="ml-1 inline-flex items-center gap-1 text-[10px] text-subtle" title="A money-affecting change. Approving parks it for your sign-off in the Plans tab before anything is written.">
                  <Lock className="h-3 w-3" /> needs sign-off
                </span>
              )}
            </div>
          ) : (
            <div className="flex items-start gap-1.5 text-[11px] text-subtle">
              <Info className="mt-0.5 h-3 w-3 shrink-0" />
              <span>{a.advisory_reason || 'Advisory only. No single reversible action to automate.'}</span>
              <button
                onClick={onReview}
                className="ml-1 shrink-0 text-accent transition-colors hover:underline"
              >
                Review in chat
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RowButton({
  children, onClick, busy, variant,
}: {
  children: React.ReactNode;
  onClick: () => void;
  busy: boolean;
  variant: 'primary' | 'outline' | 'ghost-danger';
}) {
  const base = 'inline-flex h-6 items-center gap-1 rounded px-2 text-xs font-medium transition-colors disabled:opacity-60';
  const styles =
    variant === 'primary'
      ? 'bg-accent text-on-accent hover:bg-accent-hover'
      : variant === 'outline'
        ? 'border border-border text-foreground hover:bg-secondary/50'
        : 'text-muted-foreground hover:text-danger';
  return (
    <button onClick={onClick} disabled={busy} className={cn(base, styles)}>
      {busy && <Loader2 className="h-3 w-3 animate-spin" />}
      {children}
    </button>
  );
}
