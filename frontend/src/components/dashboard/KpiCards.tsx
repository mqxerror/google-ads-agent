/**
 * KpiCards — the home page's context-rich metric row (Epic 13).
 *
 * Story 13.8 rewire: this now reads the purpose-built period-over-period
 * endpoint `GET /accounts/:id/metrics/overview?days=N` (verified live
 * 2026-07-04) instead of the former manual two-fetch rollup of
 * `fetchAccountChart`. The server returns, for the header's window:
 *   metrics.{spend,conversions,cpa,conv_rate} = {value, prev_value, delta_pct}
 *   series[] = per-day {date, spend, conversions, cpa, conv_rate}
 * so each card shows value + Δ% vs the prior equal window + a sparkline
 * of the current window's daily series.
 *
 * Honesty rules (brief §6-7), enforced from the REAL contract:
 *  - delta_pct is null when the prior window is empty/zero → show NO delta,
 *    never a fabricated one.
 *  - a metric value of null → a quiet dash, not "0".
 *  - conv_rate is a FRACTION on the wire (0.0358) → ×100 for display.
 *  - CPA/spend deltas invert colour (lower = green).
 *  - three-state row (brief §7 amendment): fake zeros stay banned, but a broken
 *    pipeline (stale/error) still renders the section + amber chip so staleness
 *    is VISIBLE, and a healthy-but-quiet window renders the header plus one calm
 *    "No activity in this window" line. Only a truly empty account (no cards)
 *    renders nothing.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ResponsiveContainer, LineChart, Line } from 'recharts';
import { fetchMetricsOverview, type MetricPoint, type MetricsOverview } from '@/lib/api';
import { cn } from '@/lib/utils';
import FreshnessChip, { type FreshnessState } from './FreshnessChip';
import InfoHover from './InfoHover';
import { useSyncNow } from '@/hooks/useSyncNow';

/** Coerce the wire `state` string to a known FreshnessState (unknown → stale). */
export function toFreshnessState(s?: string | null): FreshnessState {
  return s === 'fresh' || s === 'syncing' || s === 'error' ? s : 'stale';
}

interface KpiCardsProps {
  accountId: string;
  rangeDays: number;
}

type MetricKey = 'spend' | 'conversions' | 'cpa' | 'conv_rate';

interface MetricDef {
  key: MetricKey;
  label: string;
  /** true = lower is better (invert delta colour). */
  invert: boolean;
  /** display formatter; receives the already-scaled value (conv_rate ×100). */
  format: (v: number) => string;
  /** true when the wire value is a fraction that must be ×100 for display. */
  scalePercent?: boolean;
  /** one-line honest definition shown in the card's InfoHover. */
  definition: string;
  /** true for the lagging metrics (conversions, CPA) that Google restates. */
  lags?: boolean;
}

const METRICS: MetricDef[] = [
  { key: 'spend', label: 'Spend', invert: true, definition: 'What you paid in this window.', format: (v) => `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}` },
  { key: 'conversions', label: 'Conversions', invert: false, lags: true, definition: 'Recorded conversions in this window.', format: (v) => v.toLocaleString('en-US', { maximumFractionDigits: v < 10 ? 1 : 0 }) },
  { key: 'cpa', label: 'CPA', invert: true, lags: true, definition: 'Average cost per conversion.', format: (v) => `$${v.toFixed(2)}` },
  { key: 'conv_rate', label: 'Conv rate', invert: false, definition: 'Share of clicks that converted.', format: (v) => `${v.toFixed(2)}%`, scalePercent: true },
];

/** A quiet dash for a metric with no value in the window. */
const DASH = '—'; // em dash char (display only — not UI copy prose)

/**
 * "Jul 5" from an ISO date (YYYY-MM-DD), parsed as a plain calendar date with
 * NO timezone shift (mirrors FreshnessChip's formatThroughDate). Null on miss.
 */
function formatWindowDate(iso?: string | null): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Derive the two human-readable window labels ("Jul 5 to Jul 11") from the REAL
 * window/prev_window on the wire. Returns null for either label whose dates are
 * missing/unparseable, so callers fall back to the "{rangeDays}d window"
 * phrasing rather than inventing dates.
 */
function deriveWindowLabels(data?: MetricsOverview): {
  windowLabel: string | null;
  priorLabel: string | null;
} {
  const wStart = formatWindowDate(data?.window?.start);
  const wEnd = formatWindowDate(data?.window?.end);
  const pStart = formatWindowDate(data?.prev_window?.start);
  const pEnd = formatWindowDate(data?.prev_window?.end);
  return {
    windowLabel: wStart && wEnd ? `${wStart} to ${wEnd}` : null,
    priorLabel: pStart && pEnd ? `${pStart} to ${pEnd}` : null,
  };
}

interface CardData extends MetricDef {
  value: number | null;
  delta: number | null;
  series: { v: number }[] | null;
}

function buildCards(data: MetricsOverview): CardData[] {
  return METRICS.map((m) => {
    const point: MetricPoint | undefined = data.metrics?.[m.key];
    const rawValue = point?.value ?? null;
    const value = rawValue === null ? null : m.scalePercent ? rawValue * 100 : rawValue;

    // Delta ONLY when the server gives a non-null delta_pct (null = prior
    // window empty/zero → never fabricate).
    const delta = typeof point?.delta_pct === 'number' ? point.delta_pct : null;

    // Sparkline from the daily series for this metric. Keep only days with a
    // genuine numeric value; draw nothing if the window has no positive data.
    const raw = (data.series ?? [])
      .map((d) => d[m.key])
      .filter((v): v is number => typeof v === 'number');
    const scaled = m.scalePercent ? raw.map((v) => v * 100) : raw;
    const hasSeries = scaled.length > 1 && scaled.some((v) => v > 0);
    const series = hasSeries ? scaled.map((v) => ({ v })) : null;

    return { ...m, value, delta, series };
  });
}

export default function KpiCards({ accountId, rangeDays }: KpiCardsProps) {
  const { data } = useQuery({
    queryKey: ['metrics-overview', accountId, rangeDays],
    queryFn: () => fetchMetricsOverview(accountId, rangeDays),
    staleTime: 120_000,
    enabled: !!accountId,
  });

  const { syncNow, isSyncing } = useSyncNow(accountId);
  const cards = useMemo<CardData[]>(() => (data ? buildCards(data) : []), [data]);
  const { windowLabel, priorLabel } = useMemo(() => deriveWindowLabels(data), [data]);

  const fresh = data?.freshness;
  const state = toFreshnessState(fresh?.state);
  const canSync = state === 'stale' || state === 'error';

  // ── Three-state row (brief §7 amendment) ──
  //   (a) EMPTY ACCOUNT — no metric definitions at all → render nothing.
  //   (b) PIPELINE STALE/ERROR — pipeline broken → render the FULL section so
  //       the amber chip makes staleness VISIBLE (never hidden), whether or not
  //       any card has a value (quiet dashes under a broken pipeline are honest).
  //   (c) HEALTHY BUT QUIET — healthy pipeline, no data in this window → render
  //       the header + one calm line, NOT four dud cards.
  //   Otherwise (healthy + has data) → the normal happy path.
  const isEmpty = cards.length === 0;
  const healthy = state === 'fresh' || state === 'syncing';
  const anyValue = cards.some((c) => c.value !== null);

  if (isEmpty) return null;

  const header = (
    <div className="mb-1.5 flex items-baseline justify-between gap-3">
      <h2 className="text-sm font-semibold text-foreground">Metrics</h2>
      <FreshnessChip
        state={state}
        dataThroughDate={fresh?.data_through_date}
        ageMinutes={fresh?.age_minutes}
        detail={fresh?.detail}
        syncing={isSyncing}
        onSyncNow={canSync ? syncNow : undefined}
      />
    </div>
  );

  // (c) Healthy pipeline but nothing in this window — quiet, honest, one line.
  if (healthy && !anyValue) {
    return (
      <section aria-label="Key metrics">
        {header}
        <p className="text-[11px] text-muted-foreground">No activity in this window</p>
      </section>
    );
  }

  // (b) broken pipeline, or the happy path — render the full cards grid.
  return (
    <section aria-label="Key metrics">
      {/* Row header — quiet label + the freshness chip (A3). */}
      {header}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {cards.map((c) => (
        <div key={c.key} className="rounded-xl border border-border bg-card px-4 py-3.5">
          <div className="flex items-baseline justify-between">
            <span className="inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              <span>{c.label}</span>
              <InfoHover title={c.label} label={`About ${c.label}`} className="normal-case">
                <span className="block">{c.definition}</span>
                <span className="mt-1 block">
                  {windowLabel && priorLabel
                    ? `${windowLabel} vs ${priorLabel}`
                    : `${rangeDays}d window`}
                </span>
                <span className="mt-1 block">ENABLED campaigns only.</span>
                {c.lags && (
                  <span className="mt-1 block">Google restates conversions for several days.</span>
                )}
              </InfoHover>
            </span>
            <span className="text-[10px] text-subtle">{rangeDays}d</span>
          </div>
          <div className="mt-1.5 text-[22px] font-semibold leading-none tabular-nums text-foreground">
            {c.value === null ? <span className="text-subtle">{DASH}</span> : c.format(c.value)}
          </div>
          <div className="mt-2 flex h-7 items-end justify-between gap-2">
            {c.delta !== null ? (
              <DeltaBadge delta={c.delta} invert={c.invert} />
            ) : (
              <span className="text-[10px] text-subtle">vs prior {rangeDays}d</span>
            )}
            {c.series && (
              <div className="h-7 w-16 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={c.series} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
                    <Line
                      type="monotone"
                      dataKey="v"
                      stroke="var(--accent)"
                      strokeWidth={1.5}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      ))}
      </div>
    </section>
  );
}

function DeltaBadge({ delta, invert }: { delta: number; invert: boolean }) {
  const rounded = Math.round(delta * 10) / 10;
  if (rounded === 0) {
    return <span className="text-[11px] font-medium text-muted-foreground">0%</span>;
  }
  // "Good" = up for volume metrics, down for cost/CPA metrics.
  const good = invert ? rounded < 0 : rounded > 0;
  return (
    <span className={cn('text-[11px] font-medium tabular-nums', good ? 'text-success' : 'text-danger')}>
      {rounded > 0 ? '+' : ''}{rounded}%
    </span>
  );
}
