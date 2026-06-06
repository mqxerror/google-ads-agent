import type { Plan, PlanStatus, PlanActionCategory } from '@/lib/api';

// ── Pending "Schedule this" draft handoff ────────────────────────
// The Plans tab unmounts when inactive, so a draft fired from chat before the
// tab mounts would be missed by an event listener alone. We stash the latest
// draft here so PlansPanel can claim it on mount, and ALSO dispatch the event
// for the already-mounted case. Whichever wins, the form opens once.
let pendingScheduleDraft: unknown | null = null;
export function setPendingScheduleDraft(d: unknown) { pendingScheduleDraft = d; }
export function takePendingScheduleDraft<T>(): T | null {
  const d = pendingScheduleDraft as T | null;
  pendingScheduleDraft = null;
  return d;
}

// SQLite stores 'YYYY-MM-DD HH:MM:SS' in UTC — append Z so JS parses as UTC.
function parseTs(iso?: string | null): number | null {
  if (!iso) return null;
  const norm = iso.includes('T') ? iso : iso.replace(' ', 'T');
  const withZone = /[Z+]|[+-]\d{2}:\d{2}$/.test(norm) ? norm : norm + 'Z';
  const t = new Date(withZone).getTime();
  return Number.isFinite(t) ? t : null;
}

/** Relative time that works for past AND future timestamps. */
export function relativeTime(iso?: string | null): string {
  const t = parseTs(iso);
  if (t === null) return '';
  const diffSec = (t - Date.now()) / 1000;
  const abs = Math.abs(diffSec);
  const fmt = (n: number, unit: string) =>
    diffSec >= 0 ? `in ${n} ${unit}${n !== 1 ? 's' : ''}` : `${n} ${unit}${n !== 1 ? 's' : ''} ago`;
  if (abs < 45) return diffSec >= 0 ? 'soon' : 'just now';
  if (abs < 3600) return fmt(Math.round(abs / 60), 'min');
  if (abs < 86400) return fmt(Math.round(abs / 3600), 'hr');
  if (abs < 86400 * 30) return fmt(Math.round(abs / 86400), 'day');
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Short absolute date for a one-time schedule, e.g. "Jun 22". */
export function shortDate(iso?: string | null): string {
  const t = parseTs(iso);
  if (t === null) return '';
  return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

const DAY_LABELS: Record<string, string> = {
  mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun',
};

/** Turn a recurrence string ("weekly:mon:09:00") into a human chip. */
export function recurrenceLabel(recurrence?: string | null): string {
  if (!recurrence) return '';
  const parts = recurrence.split(':');
  const freq = parts[0];
  if (freq === 'daily') {
    const time = parts.slice(1).join(':');
    return time ? `daily · ${time}` : 'daily';
  }
  if (freq === 'weekly') {
    const day = DAY_LABELS[(parts[1] || '').toLowerCase()] || parts[1] || '';
    return day ? `weekly · ${day}` : 'weekly';
  }
  if (freq === 'monthly') {
    const dom = parts[1];
    return dom ? `monthly · ${dom}` : 'monthly';
  }
  return recurrence;
}

/** When this plan next happens (recurring uses next_run_at, once uses run_at). */
export function nextRunTs(p: Plan): number | null {
  return parseTs(p.next_run_at) ?? parseTs(p.run_at);
}

export const CATEGORY_LABELS: Record<PlanActionCategory, string> = {
  budget: 'Budget',
  bids: 'Bids',
  status: 'Status',
  geo: 'Geo',
  search_terms: 'Search terms',
  audit: 'Audit',
  report: 'Report',
  other: 'Other',
};

export const CATEGORY_ORDER: PlanActionCategory[] = [
  'budget', 'bids', 'status', 'geo', 'search_terms', 'audit', 'report', 'other',
];

/** Categories that change the account default to approval; read-only ones to auto. */
export function defaultModeForCategory(cat: PlanActionCategory): 'auto' | 'approval' {
  return cat === 'audit' || cat === 'report' ? 'auto' : 'approval';
}

export interface StatusVisual {
  /** Tailwind background class for the leading dot. */
  dot: string;
  /** Whether the dot should pulse (.studio-pulse). */
  pulse: boolean;
  label: string;
}

export function statusVisual(status: PlanStatus): StatusVisual {
  switch (status) {
    case 'due':
    case 'running':
      return { dot: 'bg-accent', pulse: true, label: status === 'running' ? 'Running' : 'Due' };
    case 'awaiting_approval':
      return { dot: 'bg-warning', pulse: false, label: 'Awaiting approval' };
    case 'done':
      return { dot: 'bg-success', pulse: false, label: 'Done' };
    case 'failed':
      return { dot: 'bg-danger', pulse: false, label: 'Failed' };
    case 'paused':
      return { dot: 'bg-muted opacity-60', pulse: false, label: 'Paused' };
    case 'scheduled':
    default:
      return { dot: 'bg-subtle', pulse: false, label: 'Scheduled' };
  }
}

export type PlanGroupKey = 'needs_you' | 'today' | 'this_week' | 'later' | 'recurring' | 'done';

export interface PlanGroup {
  key: PlanGroupKey;
  title: string;
  plans: Plan[];
  defaultCollapsed?: boolean;
}

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

/** Group plans into the design's sections, in order. */
export function groupPlans(plans: Plan[]): PlanGroup[] {
  const now = new Date();
  const todayStart = startOfDay(now);
  const tomorrowStart = todayStart + 86400_000;
  const weekEnd = todayStart + 86400_000 * 7;

  const needsYou: Plan[] = [];
  const today: Plan[] = [];
  const thisWeek: Plan[] = [];
  const later: Plan[] = [];
  const recurring: Plan[] = [];
  const done: Plan[] = [];

  for (const p of plans) {
    if (p.status === 'awaiting_approval' || p.status === 'failed') {
      needsYou.push(p);
      continue;
    }
    if (p.status === 'done') {
      done.push(p);
      continue;
    }
    if (p.schedule_type === 'recurring') {
      recurring.push(p);
      continue;
    }
    const t = nextRunTs(p);
    if (t === null) { later.push(p); continue; }
    if (t < tomorrowStart) today.push(p);
    else if (t < weekEnd) thisWeek.push(p);
    else later.push(p);
  }

  const byNext = (a: Plan, b: Plan) => (nextRunTs(a) ?? Infinity) - (nextRunTs(b) ?? Infinity);
  needsYou.sort(byNext);
  today.sort(byNext);
  thisWeek.sort(byNext);
  later.sort(byNext);
  recurring.sort(byNext);
  done.sort((a, b) => (parseTs(b.last_run_at) ?? 0) - (parseTs(a.last_run_at) ?? 0));

  const groups: PlanGroup[] = [
    { key: 'needs_you', title: 'Needs you', plans: needsYou },
    { key: 'today', title: 'Today', plans: today },
    { key: 'this_week', title: 'This week', plans: thisWeek },
    { key: 'later', title: 'Later', plans: later },
    { key: 'recurring', title: 'Recurring', plans: recurring },
    { key: 'done', title: 'Done', plans: done, defaultCollapsed: true },
  ];
  return groups.filter((g) => g.plans.length > 0);
}

export function countNeedsAttention(plans: Plan[]): number {
  return plans.filter((p) => p.status === 'awaiting_approval' || p.status === 'failed').length;
}

/** Group upcoming (cross-campaign) plans by calendar day for the dashboard. */
export function groupByDay(plans: Plan[]): { dayLabel: string; plans: Plan[] }[] {
  const buckets = new Map<string, Plan[]>();
  const sorted = [...plans].sort((a, b) => (nextRunTs(a) ?? Infinity) - (nextRunTs(b) ?? Infinity));
  for (const p of sorted) {
    const t = nextRunTs(p);
    const key = t === null ? 'Unscheduled' : dayLabelFor(t);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(p);
  }
  return Array.from(buckets.entries()).map(([dayLabel, ps]) => ({ dayLabel, plans: ps }));
}

function dayLabelFor(t: number): string {
  const d = new Date(t);
  const ds = startOfDay(d);
  const todayStart = startOfDay(new Date());
  if (ds === todayStart) return 'Today';
  if (ds === todayStart + 86400_000) return 'Tomorrow';
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}
