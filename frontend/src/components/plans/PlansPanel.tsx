import { useState, useCallback, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Plus, ChevronDown, ChevronRight, Loader2, MessageSquare,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  fetchPlans, createPlan, updatePlan, deletePlan,
  approvePlan, skipPlan, snoozePlan, runPlanNow,
} from '@/lib/api';
import type { Plan, CreatePlanBody } from '@/lib/api';
import PlanForm, { type PlanFormDraft } from './PlanForm';
import {
  groupPlans, statusVisual, relativeTime, shortDate, recurrenceLabel,
  nextRunTs, CATEGORY_LABELS, takePendingScheduleDraft,
} from './planHelpers';

interface PlansPanelProps {
  accountId: string;
  campaignId: string;
  campaignName?: string;
}

export default function PlansPanel({ accountId, campaignId, campaignName }: PlansPanelProps) {
  const qc = useQueryClient();
  const queryKey = ['plans', accountId, campaignId];

  const { data: plans = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => fetchPlans(accountId, campaignId),
    enabled: !!accountId && !!campaignId,
    refetchInterval: 20_000,        // running → done transitions surface
    refetchOnWindowFocus: true,
  });

  const refetch = useCallback(() => { qc.invalidateQueries({ queryKey }); }, [qc, accountId, campaignId]); // eslint-disable-line react-hooks/exhaustive-deps

  // New-plan inline form (header affordance + chat "Schedule this" event).
  const [showNew, setShowNew] = useState(false);
  const [newDraft, setNewDraft] = useState<PlanFormDraft | undefined>(undefined);

  // "Schedule this" from chat: claim a draft stashed before this tab mounted,
  // and also listen for the live event (panel already open case).
  useEffect(() => {
    const pending = takePendingScheduleDraft<PlanFormDraft>();
    if (pending) { setNewDraft(pending); setShowNew(true); }
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<PlanFormDraft>).detail;
      setNewDraft(detail || undefined);
      setShowNew(true);
    };
    window.addEventListener('plans:schedule', handler as EventListener);
    return () => window.removeEventListener('plans:schedule', handler as EventListener);
  }, []);

  const handleCreate = async (body: CreatePlanBody) => {
    await createPlan(body);
    setShowNew(false);
    setNewDraft(undefined);
    refetch();
  };

  const groups = groupPlans(plans);

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold">Scheduled Plans</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Decisions your team will act on later. Schedule from chat, or add one by hand.
          </p>
        </div>
        {!showNew && (
          <Button size="sm" className="gap-1.5 shrink-0" onClick={() => { setNewDraft(undefined); setShowNew(true); }}>
            <Plus className="h-4 w-4" /> New plan
          </Button>
        )}
      </div>

      {showNew && (
        <PlanForm
          accountId={accountId}
          campaignId={campaignId}
          campaignName={campaignName}
          draft={newDraft}
          onCancel={() => { setShowNew(false); setNewDraft(undefined); }}
          onSave={handleCreate}
        />
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading plans…
        </div>
      )}

      {!isLoading && plans.length === 0 && !showNew && (
        <div className="rounded-lg border border-border bg-secondary/20 p-6 text-center">
          <p className="text-sm text-text">No plans yet.</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
            Decide something with your team in chat, then "Schedule this" — or add one manually.
          </p>
          <Button size="sm" variant="outline" className="gap-1.5 mt-3" onClick={() => setShowNew(true)}>
            <Plus className="h-4 w-4" /> New plan
          </Button>
        </div>
      )}

      {groups.map((g) => (
        <PlanGroupSection
          key={g.key}
          title={g.title}
          plans={g.plans}
          defaultCollapsed={g.defaultCollapsed}
          accountId={accountId}
          campaignId={campaignId}
          campaignName={campaignName}
          onChanged={refetch}
        />
      ))}
    </div>
  );
}

function PlanGroupSection({
  title, plans, defaultCollapsed, accountId, campaignId, campaignName, onChanged,
}: {
  title: string;
  plans: Plan[];
  defaultCollapsed?: boolean;
  accountId: string;
  campaignId: string;
  campaignName?: string;
  onChanged: () => void;
}) {
  const [collapsed, setCollapsed] = useState(!!defaultCollapsed);
  return (
    <div className="space-y-1">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-text transition-colors"
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        {title}
        <span className="text-subtle font-normal">({plans.length})</span>
      </button>
      {!collapsed && (
        <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
          {plans.map((p) => (
            <PlanRow key={p.id} plan={p} accountId={accountId} campaignId={campaignId}
              campaignName={campaignName} onChanged={onChanged} />
          ))}
        </div>
      )}
    </div>
  );
}

function PlanRow({
  plan, accountId, campaignId, campaignName, onChanged,
}: {
  plan: Plan;
  accountId: string;
  campaignId: string;
  campaignName?: string;
  onChanged: () => void;
}) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(plan.status === 'awaiting_approval' || plan.status === 'failed');
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const sv = statusVisual(plan.status);
  const isRecurring = plan.schedule_type === 'recurring';
  const scheduleChip = isRecurring
    ? recurrenceLabel(plan.recurrence)
    : shortDate(plan.next_run_at || plan.run_at);
  const nextTs = nextRunTs(plan);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    try { await fn(); onChanged(); }
    catch (e) { console.error('plan action failed', e); }
    finally { setBusy(null); }
  };

  const onSaveEdit = async (body: CreatePlanBody) => {
    // PlanForm hands a CreatePlanBody; map the editable subset onto PATCH.
    await updatePlan(plan.id, {
      title: body.title,
      action_detail: body.action_detail,
      action_category: body.action_category,
      mode: body.mode,
      run_at: body.run_at,
      recurrence: body.recurrence,
    });
    setEditing(false);
    onChanged();
  };

  if (editing) {
    const draft: PlanFormDraft = {
      title: plan.title,
      action_detail: plan.action_detail,
      action_category: plan.action_category,
      mode: plan.mode,
      suggested_run_at: plan.run_at,
      recurrence: plan.recurrence,
    };
    return (
      <div className="p-2">
        <PlanForm
          accountId={accountId}
          campaignId={campaignId}
          campaignName={campaignName}
          draft={draft}
          onCancel={() => setEditing(false)}
          onSave={onSaveEdit}
        />
      </div>
    );
  }

  return (
    <div className={cn('bg-surface', expanded && 'bg-surface-2/40')}>
      {/* Quiet header row */}
      <button
        onClick={() => setExpanded((x) => !x)}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-surface-2 transition-colors"
      >
        <span className={cn('h-2 w-2 shrink-0 rounded-full', sv.dot, sv.pulse && 'studio-pulse')}
          aria-label={sv.label} />
        <span className="flex-1 min-w-0">
          <span className="text-sm text-text truncate block">{plan.title}</span>
          <span className="flex items-center gap-2 mt-0.5 text-[11px] text-muted-foreground">
            <span className="text-text/70">{scheduleChip}</span>
            <span className={cn('rounded px-1 py-px text-[10px] font-medium',
              plan.mode === 'auto' ? 'bg-surface-3 text-muted-foreground' : 'bg-warning-soft text-warning')}>
              {plan.mode}
            </span>
            {nextTs !== null && plan.status !== 'done' && plan.status !== 'paused' && (
              <span className="text-subtle">{relativeTime(plan.next_run_at || plan.run_at)}</span>
            )}
            {typeof plan.last_cost === 'number' && plan.last_cost > 0 && (
              <span className="text-subtle">${plan.last_cost.toFixed(2)}</span>
            )}
          </span>
        </span>
        {expanded ? <ChevronDown className="h-4 w-4 text-subtle shrink-0" /> : <ChevronRight className="h-4 w-4 text-subtle shrink-0" />}
      </button>

      {expanded && (
        <div className="px-3 pb-3 pl-8 space-y-3">
          {plan.action_detail && (
            <p className="text-[13px] text-text/90 whitespace-pre-wrap">{plan.action_detail}</p>
          )}

          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
            <dt className="text-muted-foreground">Category</dt>
            <dd className="text-text">{CATEGORY_LABELS[plan.action_category]}</dd>
            <dt className="text-muted-foreground">Schedule</dt>
            <dd className="text-text">
              {isRecurring ? recurrenceLabel(plan.recurrence) : `One time · ${shortDate(plan.run_at)}`}
              {nextTs !== null && plan.status !== 'done' && (
                <span className="text-subtle"> · next {relativeTime(plan.next_run_at || plan.run_at)}</span>
              )}
            </dd>
            {typeof plan.run_count === 'number' && plan.run_count > 0 && (
              <>
                <dt className="text-muted-foreground">Runs</dt>
                <dd className="text-text">{plan.run_count}</dd>
              </>
            )}
          </dl>

          {plan.context_snippet && (
            <div className="rounded-md border border-border bg-surface-2 p-2">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">From the conversation</p>
              <p className="text-[12px] text-text/80 line-clamp-4 whitespace-pre-wrap">{plan.context_snippet}</p>
            </div>
          )}

          {plan.status === 'awaiting_approval' && plan.proposed_change && (
            <div className="rounded-md border border-warning/40 bg-warning-soft/40 p-2">
              <p className="text-[10px] uppercase tracking-wide text-warning mb-1">Proposed change</p>
              <div className="studio-prose text-[12px]">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{plan.proposed_change}</ReactMarkdown>
              </div>
            </div>
          )}

          {plan.last_result && (
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Last result</p>
              <div className="studio-prose text-[12px]">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{plan.last_result}</ReactMarkdown>
              </div>
            </div>
          )}

          {plan.conversation_id && (
            <button
              onClick={() => navigate(`/c/${plan.conversation_id}`)}
              className="inline-flex items-center gap-1 text-[11px] text-accent hover:text-accent-hover"
            >
              <MessageSquare className="h-3 w-3" /> view in chat
            </button>
          )}

          {/* Per-row actions by state */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {plan.status === 'awaiting_approval' && (
              <>
                <Button size="xs" onClick={() => act('approve', () => approvePlan(plan.id))} disabled={!!busy}>
                  {busy === 'approve' ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Approve
                </Button>
                <Button size="xs" variant="outline" onClick={() => act('skip', () => skipPlan(plan.id))} disabled={!!busy}>Skip</Button>
                <Button size="xs" variant="outline" onClick={() => act('snooze', () => snoozePlan(plan.id, 24))} disabled={!!busy}>Snooze 24h</Button>
              </>
            )}
            {plan.status === 'failed' && (
              <Button size="xs" onClick={() => act('retry', () => runPlanNow(plan.id))} disabled={!!busy}>
                {busy === 'retry' ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Retry
              </Button>
            )}
            {plan.status === 'done' && (
              <Button size="xs" variant="outline" onClick={() => act('run', () => runPlanNow(plan.id))} disabled={!!busy}>Run now</Button>
            )}
            {(plan.status === 'scheduled' || plan.status === 'due') && (
              <Button size="xs" variant="outline" onClick={() => act('pause', () => updatePlan(plan.id, { status: 'paused' }))} disabled={!!busy}>Pause</Button>
            )}
            {plan.status === 'paused' && (
              <Button size="xs" variant="outline" onClick={() => act('resume', () => updatePlan(plan.id, { status: 'scheduled' }))} disabled={!!busy}>Resume</Button>
            )}
            <Button size="xs" variant="ghost" onClick={() => setEditing(true)} disabled={!!busy}>Edit</Button>
            <Button size="xs" variant="ghost" className="text-muted-foreground hover:text-danger"
              onClick={() => { if (confirm('Delete this plan?')) act('delete', () => deletePlan(plan.id)); }} disabled={!!busy}>
              Delete
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
