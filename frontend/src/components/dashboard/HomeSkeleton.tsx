/**
 * HomeSkeleton (Dashboard v2.1, C4) — in-layout loading placeholders for the
 * home sections, so the first paint reserves the real geometry instead of a
 * spinner or a blank flash that reflows when data lands (budget: skeleton →
 * content under 300ms; all four home queries are local SQLite).
 *
 * Heights mirror the live sections so nothing jumps:
 *   strip   ~88px   (FixListStrip card)
 *   KPI row ~96px    (4 cards, 2×2 below sm)
 *   table   6 × 40px rows (CampaignsRanked)
 *
 * Uses the existing `studio-pulse` (a subtle, calm pulse — DESIGN.md §Reusable
 * chat utilities) and OKLCH tokens only. No new colours, no spinners.
 */

import { cn } from '@/lib/utils';

/** One muted, pulsing bar. `w`/`h` are Tailwind classes so callers stay token-safe. */
function Bar({ className }: { className?: string }) {
  return <div className={cn('studio-pulse rounded bg-secondary', className)} />;
}

/** Needs-attention strip placeholder — a single ~88px card. */
export function FixListSkeleton() {
  return (
    <section aria-label="Loading needs attention" aria-busy="true">
      <div className="mb-2 flex items-baseline justify-between">
        <Bar className="h-4 w-32" />
        <Bar className="h-3 w-20" />
      </div>
      <div className="flex h-[88px] items-center gap-3 rounded-xl border border-border bg-card px-5">
        <div className="studio-pulse h-9 w-9 shrink-0 rounded-lg bg-secondary" />
        <div className="min-w-0 flex-1 space-y-2">
          <Bar className="h-3.5 w-40" />
          <Bar className="h-3 w-64 max-w-full" />
        </div>
      </div>
    </section>
  );
}

/** KPI row placeholder — four ~96px cards, 2×2 below sm (matches KpiCards grid). */
export function KpiCardsSkeleton() {
  return (
    <section aria-label="Loading metrics" aria-busy="true">
      <div className="mb-1.5 flex items-baseline justify-between">
        <Bar className="h-4 w-20" />
        <Bar className="h-3 w-24" />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-[96px] rounded-xl border border-border bg-card px-4 py-3.5">
            <Bar className="h-3 w-16" />
            <Bar className="mt-3 h-5 w-20" />
            <Bar className="mt-3 h-3 w-14" />
          </div>
        ))}
      </div>
    </section>
  );
}

/** Ranked-table placeholder — six 40px rows under a quiet header. */
export function CampaignsRankedSkeleton() {
  return (
    <section aria-label="Loading campaigns" aria-busy="true">
      <div className="mb-2 flex items-baseline justify-between">
        <Bar className="h-4 w-24" />
        <Bar className="h-3 w-28" />
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="divide-y divide-border">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex h-10 items-center gap-4 px-4">
              <div className="studio-pulse h-2 w-2 shrink-0 rounded-full bg-secondary" />
              <Bar className="h-3 flex-1" />
              <Bar className="h-3 w-16" />
              <Bar className="h-3 w-10" />
              <Bar className="h-3 w-12" />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/** Full home placeholder — strip + KPI row + table, in reading order. */
export default function HomeSkeleton() {
  return (
    <div className="space-y-4">
      <FixListSkeleton />
      <KpiCardsSkeleton />
      <CampaignsRankedSkeleton />
    </div>
  );
}
