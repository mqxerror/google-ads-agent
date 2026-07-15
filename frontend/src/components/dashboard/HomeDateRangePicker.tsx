/**
 * HomeDateRangePicker — the home header's window control (Epic 13,
 * Story 13.5). Drives the KPI cards + campaigns section window via the
 * app store (`homeRangeDays`, persisted to localStorage). 7d default.
 *
 * Quiet ghost tabs, matching the PerformanceChart period selector
 * idiom — no new visual language.
 */

import { useAppStore } from '@/stores/appStore';
import { cn } from '@/lib/utils';

const OPTIONS = [
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
];

export default function HomeDateRangePicker() {
  const { homeRangeDays, setHomeRangeDays } = useAppStore();
  return (
    <div className="inline-flex items-center gap-0.5 rounded-md bg-secondary/50 p-0.5" role="group" aria-label="Date range">
      {OPTIONS.map((opt) => (
        <button
          key={opt.days}
          onClick={() => setHomeRangeDays(opt.days)}
          className={cn(
            'px-2.5 py-1 text-[11px] rounded transition-colors',
            homeRangeDays === opt.days
              ? 'bg-card text-foreground font-medium'
              : 'text-muted-foreground hover:text-foreground'
          )}
          style={homeRangeDays === opt.days ? { boxShadow: 'var(--shadow-resting)' } : undefined}
          aria-pressed={homeRangeDays === opt.days}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/** Compute {dateFrom, dateTo} (YYYY-MM-DD) for a rolling window of N days
 *  ending today, inclusive. Shared so KPI + campaigns query the same range. */
export function windowFor(days: number): { dateFrom: string; dateTo: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - days + 1);
  return {
    dateFrom: from.toISOString().split('T')[0],
    dateTo: to.toISOString().split('T')[0],
  };
}
