/**
 * LiveHeadChip — the campaign header's live-truth badge (Dashboard v2.1, B4 / PART 2).
 *
 * One quiet line that tells the operator whether the status / bidding / budget
 * shown next to it is verified account-truth RIGHT NOW, or a cached fallback we
 * couldn't confirm. It consumes `/live-head` (a tiny live GAQL read, 60s server
 * TTL) via a poll:
 *
 *   state 'live'       → green "✓ live · 12s" (age since verified_at).
 *   state 'unverified' → amber "couldn't verify · showing data from {time}",
 *                        NEVER silent (fixes RC-8's "app says Maximize
 *                        Conversions when the account says Maximize Clicks").
 *
 * DESIGN.md tokens only (text-subtle / text-warning / bg-status-*). It is
 * metadata, not a banner: small, single line, no border, no fill.
 */

import { cn } from '@/lib/utils';
import type { LiveHead } from '@/lib/api';

interface LiveHeadChipProps {
  head?: LiveHead;
  /** True while the first live read is in flight (no envelope yet). */
  loading?: boolean;
}

/** "just now" / "12s" / "4m" / "2h" from an ISO instant. */
function formatVerifiedAge(iso?: string | null): string {
  if (!iso) return 'just now';
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return 'just now';
  const secs = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (secs < 5) return 'just now';
  if (secs < 60) return `${secs}s`;
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h`;
  return `${Math.round(hrs / 24)}d`;
}

/** "Jul 11, 14:02" from an ISO/SQLite timestamp. Returns the raw string on fail. */
function formatSyncedAt(raw?: string | null): string | null {
  if (!raw) return null;
  const d = new Date(raw.includes('T') ? raw : raw.replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return raw;
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function LiveHeadChip({ head, loading = false }: LiveHeadChipProps) {
  if (loading && !head) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[11px] text-subtle" role="status">
        <span className="studio-pulse h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
        verifying…
      </span>
    );
  }

  if (!head) return null;

  if (head.state === 'live') {
    return (
      <span
        className="inline-flex items-center gap-1 text-[11px] text-success"
        title="Verified live against Google Ads"
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-success" aria-hidden />
        live · {formatVerifiedAge(head.verified_at)}
      </span>
    );
  }

  // unverified — amber, and say exactly how old the fallback data is. Never silent.
  const syncedAt = formatSyncedAt(head.fallback?.last_synced_at);
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-[11px] text-warning')}
      title="A live read of this campaign failed. Showing the last synced roster values, not verified account state."
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning" aria-hidden />
      {syncedAt ? `couldn't verify · showing data from ${syncedAt}` : "couldn't verify · showing last-known data"}
    </span>
  );
}
