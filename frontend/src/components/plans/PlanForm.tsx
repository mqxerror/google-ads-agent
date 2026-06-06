import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  defaultModeForCategory,
} from './planHelpers';
import type {
  CreatePlanBody,
  PlanActionCategory,
  PlanMode,
  PlanScheduleType,
} from '@/lib/api';

export interface PlanFormDraft {
  title?: string;
  action_detail?: string;
  action_category?: PlanActionCategory;
  mode?: PlanMode;
  /** ISO timestamp suggested for a one-time run. */
  suggested_run_at?: string | null;
  recurrence?: string | null;
  /** Originating chat text, carried through to context_snippet. */
  context_snippet?: string | null;
  conversation_id?: string | null;
}

interface PlanFormProps {
  accountId: string;
  campaignId?: string | null;
  campaignName?: string | null;
  draft?: PlanFormDraft;
  onCancel: () => void;
  onSave: (body: CreatePlanBody) => Promise<void>;
}

type Freq = 'daily' | 'weekly' | 'monthly';
const DAYS: { v: string; label: string }[] = [
  { v: 'mon', label: 'Mon' }, { v: 'tue', label: 'Tue' }, { v: 'wed', label: 'Wed' },
  { v: 'thu', label: 'Thu' }, { v: 'fri', label: 'Fri' }, { v: 'sat', label: 'Sat' },
  { v: 'sun', label: 'Sun' },
];

// Split an ISO timestamp into the <input type="date"> / <input type="time"> values.
function splitIso(iso?: string | null): { date: string; time: string } {
  if (!iso) return { date: '', time: '09:00' };
  const norm = iso.includes('T') ? iso : iso.replace(' ', 'T');
  const withZone = /[Z+]|[+-]\d{2}:\d{2}$/.test(norm) ? norm : norm + 'Z';
  const d = new Date(withZone);
  if (!Number.isFinite(d.getTime())) return { date: '', time: '09:00' };
  const pad = (n: number) => String(n).padStart(2, '0');
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  };
}

// Parse an existing recurrence string back into builder state.
function splitRecurrence(rec?: string | null): { freq: Freq; day: string; dom: string; time: string } {
  const fallback = { freq: 'weekly' as Freq, day: 'mon', dom: '1', time: '09:00' };
  if (!rec) return fallback;
  const parts = rec.split(':');
  const freq = parts[0] as Freq;
  if (freq === 'daily') return { ...fallback, freq, time: parts.slice(1).join(':') || '09:00' };
  if (freq === 'weekly') return { ...fallback, freq, day: parts[1] || 'mon', time: parts.slice(2).join(':') || '09:00' };
  if (freq === 'monthly') return { ...fallback, freq, dom: parts[1] || '1', time: parts.slice(2).join(':') || '09:00' };
  return fallback;
}

export default function PlanForm({
  accountId, campaignId, campaignName, draft, onCancel, onSave,
}: PlanFormProps) {
  const [title, setTitle] = useState(draft?.title ?? '');
  const [actionDetail, setActionDetail] = useState(draft?.action_detail ?? '');
  const [category, setCategory] = useState<PlanActionCategory>(draft?.action_category ?? 'other');
  const [modeTouched, setModeTouched] = useState(!!draft?.mode);
  const [mode, setMode] = useState<PlanMode>(draft?.mode ?? defaultModeForCategory(draft?.action_category ?? 'other'));

  const initRun = splitIso(draft?.suggested_run_at);
  const initRec = splitRecurrence(draft?.recurrence);
  const [scheduleType, setScheduleType] = useState<PlanScheduleType>(draft?.recurrence ? 'recurring' : 'once');
  const [onceDate, setOnceDate] = useState(initRun.date);
  const [onceTime, setOnceTime] = useState(initRun.time);
  const [freq, setFreq] = useState<Freq>(initRec.freq);
  const [recDay, setRecDay] = useState(initRec.day);
  const [recDom, setRecDom] = useState(initRec.dom);
  const [recTime, setRecTime] = useState(initRec.time);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  // Category change re-derives the suggested mode until the operator overrides it.
  const onCategoryChange = (c: PlanActionCategory) => {
    setCategory(c);
    if (!modeTouched) setMode(defaultModeForCategory(c));
  };

  const composeRecurrence = (): string => {
    const [hh, mm] = (recTime || '09:00').split(':');
    const time = `${hh}:${mm}`;
    if (freq === 'daily') return `daily:${time}`;
    if (freq === 'weekly') return `weekly:${recDay}:${time}`;
    return `monthly:${recDom}:${time}`;
  };

  const handleSave = async () => {
    setError(null);
    if (!title.trim()) { setError('Add a title.'); return; }
    let runAt: string | null = null;
    let recurrence: string | null = null;
    if (scheduleType === 'once') {
      if (!onceDate) { setError('Pick a date for the one-time run.'); return; }
      // Local date+time → ISO. new Date(local string) is treated as local time.
      const local = new Date(`${onceDate}T${onceTime || '09:00'}`);
      if (!Number.isFinite(local.getTime())) { setError('Invalid date or time.'); return; }
      runAt = local.toISOString();
    } else {
      recurrence = composeRecurrence();
    }

    const body: CreatePlanBody = {
      account_id: accountId,
      campaign_id: campaignId ?? undefined,
      campaign_name: campaignName ?? undefined,
      conversation_id: draft?.conversation_id ?? undefined,
      title: title.trim(),
      action_detail: actionDetail.trim(),
      action_category: category,
      mode,
      schedule_type: scheduleType,
      run_at: runAt,
      recurrence,
      timezone,
      context_snippet: draft?.context_snippet ?? undefined,
    };

    setSaving(true);
    try {
      await onSave(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the plan.');
      setSaving(false);
    }
  };

  const fieldCls = 'w-full rounded-md border border-border bg-surface-2 px-2.5 py-1.5 text-sm text-text focus:border-accent focus:outline-none';
  const labelCls = 'block text-[11px] font-medium uppercase tracking-wide text-muted-foreground mb-1';

  return (
    <div className="rounded-lg border border-border bg-surface p-4 space-y-3">
      <div>
        <label className={labelCls}>Title</label>
        <input className={fieldCls} value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Raise budget to $150/day if CPA holds" autoFocus />
      </div>

      <div>
        <label className={labelCls}>What should happen</label>
        <textarea className={cn(fieldCls, 'resize-none')} rows={3} value={actionDetail}
          onChange={(e) => setActionDetail(e.target.value)}
          placeholder="Describe the action in plain words. The team uses this when the plan runs." />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>Category</label>
          <select className={fieldCls} value={category}
            onChange={(e) => onCategoryChange(e.target.value as PlanActionCategory)}>
            {CATEGORY_ORDER.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelCls}>Mode</label>
          <div className="flex gap-1.5">
            {(['auto', 'approval'] as PlanMode[]).map((m) => (
              <button key={m} type="button"
                onClick={() => { setMode(m); setModeTouched(true); }}
                className={cn(
                  'flex-1 rounded-md border px-2 py-1.5 text-xs capitalize transition-colors',
                  mode === m ? 'border-accent bg-accent-soft text-accent' : 'border-border text-muted-foreground hover:bg-surface-3'
                )}>
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className={labelCls}>Schedule</label>
        <div className="flex gap-1.5 mb-2">
          {(['once', 'recurring'] as PlanScheduleType[]).map((s) => (
            <button key={s} type="button" onClick={() => setScheduleType(s)}
              className={cn(
                'rounded-full border px-3 py-1 text-xs capitalize transition-colors',
                scheduleType === s ? 'border-accent bg-accent-soft text-accent' : 'border-border text-muted-foreground hover:bg-surface-3'
              )}>
              {s === 'once' ? 'One time' : 'Recurring'}
            </button>
          ))}
        </div>

        {scheduleType === 'once' ? (
          <div className="flex gap-2">
            <input type="date" className={fieldCls} value={onceDate} onChange={(e) => setOnceDate(e.target.value)} />
            <input type="time" className={cn(fieldCls, 'w-32')} value={onceTime} onChange={(e) => setOnceTime(e.target.value)} />
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex gap-1.5">
              {(['daily', 'weekly', 'monthly'] as Freq[]).map((f) => (
                <button key={f} type="button" onClick={() => setFreq(f)}
                  className={cn(
                    'rounded-md border px-2.5 py-1 text-xs capitalize transition-colors',
                    freq === f ? 'border-accent bg-accent-soft text-accent' : 'border-border text-muted-foreground hover:bg-surface-3'
                  )}>
                  {f}
                </button>
              ))}
            </div>
            <div className="flex gap-2 items-center">
              {freq === 'weekly' && (
                <select className={cn(fieldCls, 'w-32')} value={recDay} onChange={(e) => setRecDay(e.target.value)}>
                  {DAYS.map((d) => <option key={d.v} value={d.v}>{d.label}</option>)}
                </select>
              )}
              {freq === 'monthly' && (
                <select className={cn(fieldCls, 'w-32')} value={recDom} onChange={(e) => setRecDom(e.target.value)}>
                  {Array.from({ length: 28 }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={String(n)}>Day {n}</option>
                  ))}
                </select>
              )}
              <input type="time" className={cn(fieldCls, 'w-32')} value={recTime} onChange={(e) => setRecTime(e.target.value)} />
            </div>
          </div>
        )}
      </div>

      {error && <p className="text-xs text-danger">{error}</p>}

      <div className="flex items-center justify-end gap-2 pt-1">
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={saving}>Cancel</Button>
        <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
          {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          Save plan
        </Button>
      </div>
    </div>
  );
}
