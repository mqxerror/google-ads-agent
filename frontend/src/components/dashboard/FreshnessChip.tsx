/**
 * FreshnessChip — the shared data-age primitive (Dashboard v2.1, Epic A / A3).
 *
 * Every home section mounts this so the operator can tell, at a glance, how
 * fresh the numbers are — instead of trusting silently-stale figures (the
 * plan's core complaint: "ALWAYS STALE DATA, and not clear"). It is metadata,
 * NOT a banner: small, quiet, one line, DESIGN.md tokens only.
 *
 * States (spec: plan §1.6 / §3):
 *   fresh   → subtle "live · synced 42m ago" (or "live · just now" if <2min)
 *   syncing → a pulsing dot + "syncing…"
 *   stale   → amber "data through Jul 8" + a visible [Sync now] control
 *   error   → amber, `detail` surfaced as a tooltip, still offers [Sync now]
 *
 * Freshness is judged by `data_through_date`, never by a synced_at stamp (that
 * stamp lies — plan RC-5). The [Sync now] affordance triggers `onSyncNow`.
 */

import { RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

export type FreshnessState = 'fresh' | 'syncing' | 'stale' | 'error';

interface FreshnessChipProps {
  state: FreshnessState;
  /** MAX(date) that data actually covers — the honest anchor for stale copy. */
  dataThroughDate?: string | null;
  /** Minutes since the last successful verified sync (drives "synced Nm ago"). */
  ageMinutes?: number | null;
  /** Triggers the manual "Sync now" mutation. Shown for stale/error. */
  onSyncNow?: () => void;
  /** True while a sync mutation is in flight — forces the syncing look + disables. */
  syncing?: boolean;
  /** Error explanation, surfaced as the chip's tooltip in the error state. */
  detail?: string | null;
}

/** "Jul 8" from an ISO date (YYYY-MM-DD). Returns the raw string on parse fail. */
function formatThroughDate(iso?: string | null): string | null {
  if (!iso) return null;
  // Parse as a plain calendar date (no timezone shift): the wire value is a
  // date, not an instant.
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** "just now" / "42m ago" / "3h ago" / "2d ago" from minutes. */
function formatAge(mins?: number | null): string {
  if (mins == null || !Number.isFinite(mins)) return 'just now';
  if (mins < 2) return 'just now';
  if (mins < 60) return `${Math.round(mins)}m ago`;
  const hrs = mins / 60;
  if (hrs < 48) return `${Math.round(hrs)}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export default function FreshnessChip({
  state,
  dataThroughDate,
  ageMinutes,
  onSyncNow,
  syncing = false,
  detail,
}: FreshnessChipProps) {
  // An in-flight mutation always reads as "syncing", whatever the last envelope
  // said, so the chip reacts the instant Sync now is pressed.
  const effective: FreshnessState = syncing ? 'syncing' : state;

  if (effective === 'syncing') {
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] text-subtle" role="status">
        <span className="studio-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
        syncing…
      </span>
    );
  }

  if (effective === 'fresh') {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-subtle" title="Verified against Google Ads">
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" aria-hidden />
        live · synced {formatAge(ageMinutes)}
      </span>
    );
  }

  // stale | error — amber, and offer the visible Sync now control.
  const through = formatThroughDate(dataThroughDate);
  const label =
    effective === 'error'
      ? 'sync failed'
      : through
        ? `data through ${through}`
        : 'data may be stale';
  const tooltip =
    effective === 'error'
      ? detail || 'The last sync failed. Try Sync now.'
      : 'This data is older than a day. Sync now for fresh numbers.';

  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-warning" title={tooltip}>
      {label}
      {onSyncNow && (
        <button
          type="button"
          onClick={onSyncNow}
          disabled={syncing}
          className={cn(
            'inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium text-warning transition-colors',
            'bg-warning-soft hover:bg-warning-soft/70 disabled:opacity-60',
          )}
        >
          <RefreshCw className="h-2.5 w-2.5" aria-hidden />
          Sync now
        </button>
      )}
    </span>
  );
}
