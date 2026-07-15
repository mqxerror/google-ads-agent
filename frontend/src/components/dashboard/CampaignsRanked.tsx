/**
 * CampaignsRanked — the home page's ranked campaigns section (Epic 13,
 * Story 13.8, upgrading the 13.5 shell).
 *
 * A compact ranked TABLE (not a card grid). DEFAULTS to ACTIVE (ENABLED)
 * campaigns only (operator 2026-07-05: a campaign paused a year ago must not
 * clutter the home) — an "Active N / All N" toggle reveals paused/removed on
 * demand. Rows are capped (~6) with a "View all" disclosure to keep the home
 * short. Sorted: spending campaigns first, dormant zero-spend ENABLED ones
 * last (de-emphasized, never a fabricated "stopped" flag — no activity/date
 * field exists on the campaign object). Columns: name · status · spend · conv
 * · CPA · threshold flag.
 * Threshold flags are derived HONESTLY from the campaigns payload only
 * (no invented target numbers):
 *   - "No conversions" — an ENABLED campaign with real spend and zero
 *     conversions in the window (pure waste; always defensible).
 *   - "High CPA" — CPA more than 2× the account's blended CPA, and only
 *     when a real blended baseline exists (≥1 converting campaign with
 *     spend). A relative, data-derived threshold — never a fabricated
 *     absolute.
 * There is NO trend spark column: the campaigns endpoint carries no
 * per-day field, so we show the columns without fabricating a sparkline
 * (brief §7 / the story's "if a daily field is available" clause).
 *
 * When ≥1 campaign is flagged, ONE bulk-action bar appears (brief §4).
 * "Pause…" routes through the EXISTING approval-gated plans path
 * (`createPlan`, action_category:'status', mode:'approval') — one plan per
 * selected campaign, parked in the Plans tab for sign-off. It is NEVER a
 * direct Google Ads mutate from the home page (Story 13.3 rule).
 *
 * Clicking a row opens that campaign (the same navigation the sidebar tree
 * uses). Zero-state discipline (§7): no campaigns → the section renders
 * nothing.
 */

import { useMemo, useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Check, Loader2, Power, X } from 'lucide-react';
import { fetchCampaigns, fetchCampaignsFreshness, createPlan } from '@/lib/api';
import { useAppStore } from '@/stores/appStore';
import { formatMicros } from '@/lib/formatters';
import { windowFor } from './HomeDateRangePicker';
import { cn } from '@/lib/utils';
import FreshnessChip from './FreshnessChip';
import InfoHover from './InfoHover';
import { toFreshnessState } from './KpiCards';
import { useSyncNow } from '@/hooks/useSyncNow';
import type { Campaign } from '@/types';

interface CampaignsRankedProps {
  accountId: string;
  rangeDays: number;
}

const STATUS_META: Record<Campaign['status'], { dot: string; label: string }> = {
  ENABLED: { dot: 'bg-status-enabled', label: 'Active' },
  PAUSED: { dot: 'bg-status-paused', label: 'Paused' },
  REMOVED: { dot: 'bg-status-removed', label: 'Removed' },
};

/** Below-target flag for one campaign, or null when nothing is honestly wrong.
 *  `blendedCpa` is the account-wide cost/conv baseline (null when nobody has
 *  converted yet — then we never raise a High-CPA flag). */
function thresholdFlag(c: Campaign, blendedCpa: number | null): { label: string; title: string } | null {
  const spend = c.metrics.costMicros / 1_000_000;
  const spent = spend > 1; // ignore rounding dust
  if (c.status === 'ENABLED' && spent && c.metrics.conversions === 0) {
    return { label: 'No conversions', title: `Spending ${formatMicros(c.metrics.costMicros)} in this window with 0 conversions.` };
  }
  if (
    c.status === 'ENABLED' &&
    spent &&
    c.metrics.conversions > 0 &&
    blendedCpa !== null &&
    blendedCpa > 0 &&
    c.metrics.cpa > blendedCpa * 2
  ) {
    return {
      label: 'High CPA',
      title: `CPA $${c.metrics.cpa.toFixed(0)} is more than 2× the account average ($${blendedCpa.toFixed(0)}).`,
    };
  }
  return null;
}

/** True when a campaign reported nothing in the window — no spend, no
 *  conversions, no impressions. New campaigns can take a cycle to report, so we
 *  show a calm "no data yet" chip instead of an empty dud dash. */
function hasNoData(c: Campaign): boolean {
  return c.metrics.costMicros === 0 && c.metrics.conversions === 0 && c.metrics.impressions === 0;
}

function cpaLabel(c: Campaign): string {
  return c.metrics.conversions > 0 ? `$${c.metrics.cpa.toFixed(0)}` : '—';
}

function convLabel(n: number): string {
  return n.toLocaleString('en-US', { maximumFractionDigits: n > 0 && n < 10 ? 1 : 0 });
}

export default function CampaignsRanked({ accountId, rangeDays }: CampaignsRankedProps) {
  const { setSelectedCampaign } = useAppStore();
  const { dateFrom, dateTo } = useMemo(() => windowFor(rangeDays), [rangeDays]);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', accountId, dateFrom, dateTo],
    queryFn: () => fetchCampaigns(accountId, dateFrom, dateTo),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  // Freshness rides a SEPARATE query key (A3): the /campaigns body is a bare
  // array consumed by the Sidebar via ['campaigns'], so we read the envelope
  // from the X-Data-Freshness header via a companion fetch instead of touching
  // that shape. See fetchCampaignsFreshness.
  const { data: freshness } = useQuery({
    queryKey: ['campaigns-freshness', accountId],
    queryFn: () => fetchCampaignsFreshness(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });
  const { syncNow, isSyncing } = useSyncNow(accountId);

  // Account blended CPA baseline from campaigns that actually converted with
  // spend — the honest reference for the relative High-CPA flag.
  const blendedCpa = useMemo<number | null>(() => {
    let cost = 0;
    let conv = 0;
    for (const c of campaigns) {
      if (c.metrics.conversions > 0) {
        cost += c.metrics.costMicros / 1_000_000;
        conv += c.metrics.conversions;
      }
    }
    return conv > 0 ? cost / conv : null;
  }, [campaigns]);

  // Active-only by default (operator: "a campaign stopped a year ago still
  // shows"). `scope` toggles ENABLED-only ↔ every status. No activity/date
  // field exists on the campaign object, so "active" = status ENABLED and
  // nothing is fabricated. Within ENABLED, spending campaigns rank above
  // zero-spend dormant ones (de-emphasize, never a fake "stopped" flag).
  const [scope, setScope] = useState<'active' | 'all'>('active');
  const [showAll, setShowAll] = useState(false);
  const ROW_CAP = 6;

  const enabledCount = useMemo(() => campaigns.filter((c) => c.status === 'ENABLED').length, [campaigns]);

  const ranked = useMemo(() => {
    const rank = (c: Campaign) => (c.status === 'ENABLED' ? 0 : c.status === 'PAUSED' ? 1 : 2);
    const scoped = scope === 'active' ? campaigns.filter((c) => c.status === 'ENABLED') : campaigns;
    return [...scoped]
      .sort((a, b) => {
        const r = rank(a) - rank(b);
        if (r !== 0) return r;
        // Zero-spend ENABLED campaigns sink below spenders (dormant, last).
        const aSpends = a.metrics.costMicros > 1_000_000 ? 0 : 1;
        const bSpends = b.metrics.costMicros > 1_000_000 ? 0 : 1;
        if (aSpends !== bSpends) return aSpends - bSpends;
        return b.metrics.costMicros - a.metrics.costMicros;
      })
      .map((c) => ({ campaign: c, flag: thresholdFlag(c, blendedCpa) }));
  }, [campaigns, blendedCpa, scope]);

  const flaggedCount = useMemo(() => ranked.filter((r) => r.flag !== null).length, [ranked]);
  // Only ENABLED, flagged campaigns are eligible to bulk-pause.
  const pausable = useMemo(
    () => ranked.filter((r) => r.flag !== null && r.campaign.status === 'ENABLED').map((r) => r.campaign),
    [ranked],
  );

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllFlagged = useCallback(() => {
    setSelected((prev) => {
      const ids = pausable.map((c) => c.id);
      const allChosen = ids.length > 0 && ids.every((id) => prev.has(id));
      return allChosen ? new Set() : new Set(ids);
    });
  }, [pausable]);

  // Route selected pauses through the guarded plan path — one approval-gated
  // status plan per campaign. Never a direct mutate.
  const pauseSelected = useCallback(async () => {
    const targets = pausable.filter((c) => selected.has(c.id));
    if (targets.length === 0 || busy) return;
    setBusy(true);
    try {
      for (const c of targets) {
        await createPlan({
          account_id: accountId,
          campaign_id: c.id,
          campaign_name: c.name,
          title: `Pause ${c.name}`,
          action_detail: `Pause campaign "${c.name}" — flagged below target on the homepage (${formatMicros(c.metrics.costMicros)} spend, ${convLabel(c.metrics.conversions)} conv this window).`,
          action_category: 'status',
          mode: 'approval',
          schedule_type: 'once',
          context_snippet: 'Bulk pause requested from the homepage campaigns table.',
        });
      }
      setSelected(new Set());
      setFlash(
        targets.length === 1
          ? 'Parked 1 pause for your sign-off. Approve it from the Plans tab.'
          : `Parked ${targets.length} pauses for your sign-off. Approve them from the Plans tab.`,
      );
    } catch {
      setFlash('Something went wrong. Nothing was changed.');
    } finally {
      setBusy(false);
      window.setTimeout(() => setFlash(null), 4000);
    }
  }, [pausable, selected, busy, accountId]);

  // Zero-state discipline: no campaigns at all → nothing. (A non-empty account
  // whose ENABLED set is empty still renders so the operator can switch to All.)
  if (campaigns.length === 0) return null;

  const selectedCount = pausable.filter((c) => selected.has(c.id)).length;
  const showSelect = flaggedCount > 0;
  const visibleRanked = showAll ? ranked : ranked.slice(0, ROW_CAP);
  const hiddenCount = ranked.length - visibleRanked.length;

  return (
    <section aria-label="Campaigns">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2.5">
          <h2 className="text-sm font-semibold text-foreground">Campaigns</h2>
          {/* Active / All scope — active-only by default so a long-paused
              campaign no longer clutters the home. */}
          <div className="flex items-center gap-1 text-[11px]">
            <button
              onClick={() => { setScope('active'); setShowAll(false); }}
              className={cn(
                'rounded px-1.5 py-0.5 transition-colors',
                scope === 'active' ? 'bg-secondary font-medium text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              Active {enabledCount}
            </button>
            <button
              onClick={() => { setScope('all'); setShowAll(false); }}
              className={cn(
                'rounded px-1.5 py-0.5 transition-colors',
                scope === 'all' ? 'bg-secondary font-medium text-foreground' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              All {campaigns.length}
            </button>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {freshness && (() => {
            const state = toFreshnessState(freshness.state);
            const canSync = state === 'stale' || state === 'error';
            return (
              <FreshnessChip
                state={state}
                dataThroughDate={freshness.data_through_date}
                ageMinutes={freshness.age_minutes}
                detail={freshness.detail}
                syncing={isSyncing}
                onSyncNow={canSync ? syncNow : undefined}
              />
            );
          })()}
          <span className="text-[11px] text-muted-foreground">
            {flaggedCount > 0 ? `${flaggedCount} flagged · ` : ''}{ranked.length} shown
            <span className="text-subtle"> · last {rangeDays}d</span>
          </span>
        </div>
      </div>

      {/* One bulk-action bar — only when flags exist (brief §4). Its action
          routes through createPlan (approval-gated), never a direct write. */}
      {showSelect && pausable.length > 0 && (
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-secondary/30 px-3 py-2">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5 text-warning" />
            <span>
              {selectedCount > 0
                ? `${selectedCount} selected`
                : `${pausable.length} active ${pausable.length === 1 ? 'campaign is' : 'campaigns are'} below target`}
            </span>
            <button
              onClick={selectAllFlagged}
              className="text-accent transition-colors hover:underline"
            >
              {pausable.length > 0 && pausable.every((c) => selected.has(c.id)) ? 'Clear' : 'Pick all flagged'}
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            {selectedCount > 0 && (
              <button
                onClick={() => setSelected(new Set())}
                disabled={busy}
                className="inline-flex h-7 items-center gap-1 rounded px-2 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-60"
              >
                <X className="h-3 w-3" /> Cancel
              </button>
            )}
            <button
              onClick={pauseSelected}
              disabled={busy || selectedCount === 0}
              className="inline-flex h-7 items-center gap-1.5 rounded bg-accent px-2.5 text-xs font-medium text-on-accent transition-colors hover:bg-accent-hover disabled:opacity-50"
              title="Parks an approval-gated pause plan for each selected campaign. Nothing is paused until you sign off in the Plans tab."
            >
              {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Power className="h-3 w-3" />}
              {selectedCount > 0 ? `Pause ${selectedCount}` : 'Pause selected'}
            </button>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {/* Column header — quiet; row dividers do the separation. */}
        <div
          className={cn(
            'grid items-center gap-4 px-4 py-2 text-[10px] font-medium uppercase tracking-wide text-subtle',
            showSelect
              ? 'grid-cols-[auto_1fr_auto_auto_auto_auto]'
              : 'grid-cols-[1fr_auto_auto_auto_auto]',
          )}
        >
          {showSelect && <span className="w-4" aria-hidden />}
          <span>Campaign</span>
          <span className="w-24 text-right">Spend</span>
          <span className="w-14 text-right">Conv</span>
          <span className="w-16 text-right">CPA</span>
          <span className="inline-flex w-24 items-center justify-end gap-1">
            Flag
            <InfoHover title="Flag" label="About the Flag column">
              Flags spotlight below-target active campaigns. No conversions means
              real spend with zero conversions this window. High CPA means cost
              per conversion over 2× the account average.
            </InfoHover>
          </span>
        </div>

        <div className="divide-y divide-border">
          {visibleRanked.map(({ campaign: c, flag }) => {
            const meta = STATUS_META[c.status];
            const canSelect = showSelect && flag !== null && c.status === 'ENABLED';
            const isSelected = selected.has(c.id);
            return (
              <div
                key={c.id}
                className={cn(
                  'grid items-center gap-4 px-4 py-3 transition-colors hover:bg-secondary/40',
                  showSelect
                    ? 'grid-cols-[auto_1fr_auto_auto_auto_auto]'
                    : 'grid-cols-[1fr_auto_auto_auto_auto]',
                  isSelected && 'bg-accent-soft/50',
                )}
              >
                {showSelect && (
                  <div className="w-4">
                    {canSelect ? (
                      <button
                        onClick={() => toggle(c.id)}
                        role="checkbox"
                        aria-checked={isSelected}
                        aria-label={`Select ${c.name} to pause`}
                        className={cn(
                          'flex h-4 w-4 items-center justify-center rounded border transition-colors',
                          isSelected
                            ? 'border-accent bg-accent text-on-accent'
                            : 'border-border hover:border-accent',
                        )}
                      >
                        {isSelected && <Check className="h-3 w-3" />}
                      </button>
                    ) : (
                      <span className="block h-4 w-4" aria-hidden />
                    )}
                  </div>
                )}

                <button
                  onClick={() => setSelectedCampaign(c.id)}
                  className="flex min-w-0 items-center gap-2.5 text-left"
                >
                  <span className={cn('h-2 w-2 shrink-0 rounded-full', meta.dot)} title={meta.label} />
                  <span className="truncate text-sm text-foreground hover:underline">{c.name}</span>
                  <span className="shrink-0 text-[10px] text-muted-foreground">{meta.label}</span>
                </button>

                <span className="w-24 text-right text-sm tabular-nums text-foreground">
                  {formatMicros(c.metrics.costMicros)}
                </span>
                <span className="w-14 text-right text-sm tabular-nums text-muted-foreground">
                  {convLabel(c.metrics.conversions)}
                </span>
                <span className="w-16 text-right text-sm tabular-nums text-muted-foreground">
                  {cpaLabel(c)}
                </span>
                <span className="flex w-24 justify-end">
                  {flag ? (
                    <span
                      className="inline-flex items-center gap-1 rounded bg-warning-soft px-1.5 py-0.5 text-[10px] font-medium text-warning"
                      title={flag.title}
                    >
                      <AlertTriangle className="h-2.5 w-2.5" />
                      {flag.label}
                    </span>
                  ) : hasNoData(c) ? (
                    <span
                      className="inline-flex items-center rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground"
                      title="This campaign has no impressions, spend, or conversions in the selected window. New campaigns can take a cycle to report."
                    >
                      no data yet
                    </span>
                  ) : (
                    <span className="text-[11px] text-subtle">—</span>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Row cap disclosure — keep the home short; reveal the rest on demand. */}
      {hiddenCount > 0 && (
        <button
          onClick={() => setShowAll(true)}
          className="mt-1.5 text-[11px] text-accent transition-colors hover:underline"
        >
          View all {ranked.length}
        </button>
      )}
      {showAll && ranked.length > ROW_CAP && (
        <button
          onClick={() => setShowAll(false)}
          className="mt-1.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
        >
          Show less
        </button>
      )}

      {/* Trust line under the write surface (brief §8). */}
      <p className="mt-2 text-[11px] text-subtle">Every write is reviewed. Every write is reversible.</p>
      {flash && (
        <p className="mt-1 text-[11px] text-muted-foreground" role="status">{flash}</p>
      )}
    </section>
  );
}
