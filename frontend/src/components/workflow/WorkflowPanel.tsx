import { useState, useRef, useCallback, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Play, Loader2, CheckCircle2, ChevronDown, ChevronRight, Sparkles, Users, Gavel, Database, History, GitCompare, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getAgentProfile } from '@/lib/agentProfiles';

interface WorkflowPanelProps {
  accountId: string;
  campaignId: string;
  campaignName?: string;
}

type PhaseKey = 'prefetch' | 'plan' | 'specialists' | 'debate' | 'synthesis';
type PhaseStatus = 'pending' | 'running' | 'done';

interface AgentCard {
  roleId: string; roleName: string; phase: PhaseKey; task: string;
  text: string; tools: string[]; done: boolean; cost: number;
}
interface RunSummary {
  id: string; goal: string; status: string; timeframe: string | null;
  cost: number; budget: number; created_at: string; has_output: number;
}

const PHASE_META: { key: PhaseKey; label: string; icon: typeof Database }[] = [
  { key: 'prefetch', label: 'Pre-fetch', icon: Database },
  { key: 'plan', label: 'Director plans', icon: Sparkles },
  { key: 'specialists', label: 'Specialists', icon: Users },
  { key: 'debate', label: 'Debate', icon: Gavel },
  { key: 'synthesis', label: 'Final plan', icon: CheckCircle2 },
];

const TIMEFRAMES = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'lifetime'] as const;
type Timeframe = typeof TIMEFRAMES[number];

const lsKey = (campaignId: string) => `workflow-last-run:${campaignId}`;

export default function WorkflowPanel({ accountId, campaignId, campaignName }: WorkflowPanelProps) {
  const [running, setRunning] = useState(false);
  const [timeframe, setTimeframe] = useState<Timeframe>('weekly');
  const [goal, setGoal] = useState(
    'Full daily + weekly + ad-copy audit, then team-reconcile the reports into one prioritised action plan, resolving any conflicts.'
  );
  const [, setPhaseLabels] = useState<Record<string, string>>({});
  const [phaseStatus, setPhaseStatus] = useState<Record<PhaseKey, PhaseStatus>>({
    prefetch: 'pending', plan: 'pending', specialists: 'pending', debate: 'pending', synthesis: 'pending',
  });
  const [agents, setAgents] = useState<Record<string, AgentCard>>({});
  const [debateFocus, setDebateFocus] = useState('');
  const [finalOutput, setFinalOutput] = useState('');
  const [spent, setSpent] = useState(0);
  const [budget, setBudget] = useState(0);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [, setActiveRunId] = useState<string | null>(null);

  // History + compare
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareData, setCompareData] = useState<any[] | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [finalOutput, agents]);

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`/api/workflows/runs?account_id=${accountId}&campaign_id=${campaignId}&limit=30`);
      setHistory(await res.json());
    } catch { /* ignore */ }
  }, [accountId, campaignId]);

  // Load history on mount + restore the last run for this campaign so a refresh
  // doesn't lose it (the data was always persisted server-side; we just reload).
  useEffect(() => {
    loadHistory();
    const last = localStorage.getItem(lsKey(campaignId));
    if (last) loadRun(last, /*silent*/ true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [campaignId]);

  const setPhase = useCallback((p: PhaseKey, s: PhaseStatus, label?: string) => {
    setPhaseStatus((prev) => ({ ...prev, [p]: s }));
    if (label) setPhaseLabels((prev) => ({ ...prev, [p]: label }));
  }, []);
  const toggle = (k: string) => setExpanded((prev) => ({ ...prev, [k]: !prev[k] }));

  function resetView() {
    setAgents({}); setFinalOutput(''); setDebateFocus(''); setSpent(0); setPhaseLabels({});
    setPhaseStatus({ prefetch: 'pending', plan: 'pending', specialists: 'pending', debate: 'pending', synthesis: 'pending' });
  }

  // Load a completed run from the DB into the view (history click / refresh restore).
  async function loadRun(runId: string, silent = false) {
    try {
      const res = await fetch(`/api/workflows/runs/${runId}`);
      const run = await res.json();
      if (run.error) { if (!silent) localStorage.removeItem(lsKey(campaignId)); return; }
      resetView();
      setActiveRunId(runId);
      setBudget(run.budget || 0);
      setSpent(run.cost || 0);
      if (run.timeframe) setTimeframe(run.timeframe);
      // Rebuild agent cards from persisted reports.
      const next: Record<string, AgentCard> = {};
      for (const r of run.reports || []) {
        if (r.phase === 'specialists' || r.phase === 'debate') {
          const profileName = r.role_name || r.role_id;
          next[`${r.phase}:${r.role_id}`] = {
            roleId: r.role_id, roleName: profileName, phase: r.phase,
            task: r.task || '', text: r.content || '', tools: [], done: true, cost: r.cost || 0,
          };
        }
      }
      setAgents(next);
      if (run.plan?.debate_focus) setDebateFocus(run.plan.debate_focus);
      setFinalOutput(run.final_output || '');
      // Mark phases done for a completed run.
      if (run.status === 'done') {
        setPhaseStatus({ prefetch: 'done', plan: 'done', specialists: 'done', debate: 'done', synthesis: 'done' });
      }
      setShowHistory(false);
      setCompareData(null);
    } catch { /* ignore */ }
  }

  const run = useCallback(async () => {
    setRunning(true);
    resetView();
    setCompareData(null);
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const res = await fetch('/api/workflows/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId, campaign_id: campaignId, campaign_name: campaignName, goal, timeframe }),
        signal: ac.signal,
      });
      const reader = res.body?.getReader();
      if (!reader) throw new Error('no stream');
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try { handleEvent(JSON.parse(raw)); } catch { /* skip */ }
        }
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === 'AbortError'))
        setFinalOutput((prev) => prev + `\n\n**Error:** ${e}`);
    } finally {
      setRunning(false);
      loadHistory();
    }
  }, [accountId, campaignId, campaignName, goal, timeframe, loadHistory]);

  function handleEvent(ev: any) {
    switch (ev.type) {
      case 'workflow_start':
        setBudget(ev.budget || 0);
        setActiveRunId(ev.run_id);
        if (ev.run_id) localStorage.setItem(lsKey(campaignId), ev.run_id);
        break;
      case 'phase':
        setPhase(ev.phase, ev.status === 'done' ? 'done' : 'running', ev.label);
        break;
      case 'plan': {
        setDebateFocus(ev.debate_focus || '');
        const next: Record<string, AgentCard> = {};
        for (const s of ev.specialists || [])
          next[`specialists:${s.role_id}`] = { roleId: s.role_id, roleName: s.role_name, phase: 'specialists', task: s.task, text: '', tools: s.tools || [], done: false, cost: 0 };
        setAgents((prev) => ({ ...prev, ...next }));
        break;
      }
      case 'agent_start': {
        const key = `${ev.phase}:${ev.role_id}`;
        setAgents((prev) => ({ ...prev, [key]: { roleId: ev.role_id, roleName: ev.role_name, phase: ev.phase, task: ev.task || prev[key]?.task || '', text: '', tools: prev[key]?.tools || [], done: false, cost: 0 } }));
        setExpanded((prev) => ({ ...prev, [key]: true }));
        break;
      }
      case 'agent_text': {
        const key = `${ev.phase}:${ev.role_id}`;
        setAgents((prev) => ({ ...prev, [key]: { ...(prev[key] || { roleId: ev.role_id, roleName: ev.role_id, phase: ev.phase, task: '', tools: [], done: false, cost: 0 }), text: (prev[key]?.text || '') + (ev.content || '') } }));
        break;
      }
      case 'agent_done': {
        const key = `${ev.phase}:${ev.role_id}`;
        setAgents((prev) => prev[key] ? { ...prev, [key]: { ...prev[key], done: true, cost: ev.cost || 0 } } : prev);
        break;
      }
      case 'budget':
        setSpent(ev.spent || 0); if (ev.budget) setBudget(ev.budget); break;
      case 'workflow_done':
        setFinalOutput(ev.final_output || ''); setSpent(ev.cost || 0); setPhase('synthesis', 'done'); break;
      case 'error':
        setFinalOutput((prev) => prev + `\n\n**Error:** ${ev.message}`); break;
    }
  }

  // Compare: load full detail for the selected run ids, show side by side.
  const toggleCompare = (id: string) => {
    setCompareIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : prev.length >= 2 ? [prev[1], id] : [...prev, id]);
  };
  const runCompare = async () => {
    if (compareIds.length < 2) return;
    const data = await Promise.all(compareIds.map((id) => fetch(`/api/workflows/runs/${id}`).then((r) => r.json())));
    setCompareData(data);
    setShowHistory(false);
  };

  const agentList = Object.entries(agents);
  const specialistAgents = agentList.filter(([, a]) => a.phase === 'specialists');
  const debateAgents = agentList.filter(([, a]) => a.phase === 'debate');

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      {/* Header / trigger */}
      <div className="rounded-lg border border-border p-4 bg-secondary/20">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h3 className="text-sm font-semibold flex items-center gap-2"><Users className="h-4 w-4" /> Team Audit Workflow</h3>
            <p className="text-xs text-muted-foreground mt-1">
              Director plans → specialists each report → team debates conflicts → Marketing Director delivers one reconciled plan. Reads pre-fetched local data (rate-limit safe).
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => { setShowHistory((s) => !s); loadHistory(); }}>
              <History className="h-4 w-4" /> History
            </Button>
            <Button onClick={run} disabled={running} size="sm" className="gap-2">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {running ? 'Running…' : 'Run Team Audit'}
            </Button>
          </div>
        </div>

        {/* Timeframe presets */}
        <div className="mt-3 flex items-center gap-1.5 flex-wrap">
          <span className="text-[11px] text-muted-foreground mr-1">Timeframe:</span>
          {TIMEFRAMES.map((tf) => (
            <button key={tf} disabled={running} onClick={() => setTimeframe(tf)}
              className={cn('rounded-full border px-2.5 py-0.5 text-[11px] capitalize transition-colors disabled:opacity-50',
                timeframe === tf ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-secondary')}>
              {tf}
            </button>
          ))}
        </div>

        <textarea value={goal} onChange={(e) => setGoal(e.target.value)} disabled={running} rows={2}
          className="mt-3 w-full text-xs rounded-md border border-border bg-background p-2 resize-none disabled:opacity-60" placeholder="Workflow goal…" />
        {(spent > 0 || budget > 0) && (
          <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
            <span>Spend: <b>${spent.toFixed(2)}</b> / ${budget.toFixed(0)}</span>
            <div className="flex-1 h-1 rounded-full bg-secondary overflow-hidden">
              <div className="h-full bg-primary transition-all" style={{ width: `${budget ? Math.min(100, (spent / budget) * 100) : 0}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* History drawer */}
      {showHistory && (
        <div className="rounded-lg border border-border p-3 space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Past Audits ({history.length})</h4>
            {compareIds.length === 2 && (
              <Button size="sm" variant="outline" className="gap-1.5 h-7" onClick={runCompare}>
                <GitCompare className="h-3.5 w-3.5" /> Compare 2
              </Button>
            )}
          </div>
          {history.length === 0 && <p className="text-xs text-muted-foreground">No past runs yet.</p>}
          {history.map((h) => (
            <div key={h.id} className={cn('flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs',
              compareIds.includes(h.id) ? 'border-primary bg-primary/5' : 'border-border')}>
              <input type="checkbox" checked={compareIds.includes(h.id)} onChange={() => toggleCompare(h.id)} className="shrink-0" />
              <button className="flex-1 text-left" onClick={() => loadRun(h.id)}>
                <span className="font-medium capitalize">{h.timeframe || 'audit'}</span>
                <span className="text-muted-foreground"> · {new Date(h.created_at + 'Z').toLocaleString()} · ${(h.cost || 0).toFixed(2)}</span>
                <span className={cn('ml-1', h.status === 'done' ? 'text-emerald-600 dark:text-emerald-400' : h.status === 'error' ? 'text-red-500' : 'text-amber-500')}>· {h.status}</span>
              </button>
            </div>
          ))}
          <p className="text-[10px] text-muted-foreground">Tick two runs to compare side by side. Click a run to reopen it.</p>
        </div>
      )}

      {/* Compare view */}
      {compareData && (
        <div className="rounded-lg border border-border p-3">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground flex items-center gap-1.5"><GitCompare className="h-3.5 w-3.5" /> Comparison</h4>
            <button onClick={() => setCompareData(null)}><X className="h-4 w-4 text-muted-foreground" /></button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {compareData.map((r) => (
              <div key={r.id} className="rounded-md border border-border p-2">
                <p className="text-[11px] font-medium capitalize mb-1">{r.timeframe || 'audit'} · {new Date(r.created_at + 'Z').toLocaleDateString()} · ${(r.cost || 0).toFixed(2)}</p>
                <div className="prose prose-sm dark:prose-invert max-w-none text-[12px] max-h-[480px] overflow-auto">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.final_output || '_no final plan_'}</ReactMarkdown>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phase tree */}
      {!compareData && (
        <>
          <div className="flex items-center gap-1 flex-wrap">
            {PHASE_META.map(({ key, label, icon: Icon }) => {
              const st = phaseStatus[key];
              return (
                <div key={key} className={cn('flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]',
                  st === 'done' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400',
                  st === 'running' && 'border-primary/50 bg-primary/10 text-primary',
                  st === 'pending' && 'border-border/60 text-muted-foreground')}>
                  {st === 'running' ? <Loader2 className="h-3 w-3 animate-spin" /> : st === 'done' ? <CheckCircle2 className="h-3 w-3" /> : <Icon className="h-3 w-3" />}
                  {label}
                </div>
              );
            })}
          </div>

          {specialistAgents.length > 0 && (
            <Section title="Specialist Reports">
              {specialistAgents.map(([key, a]) => <AgentBlock key={key} k={key} a={a} expanded={!!expanded[key]} toggle={toggle} />)}
            </Section>
          )}
          {debateAgents.length > 0 && (
            <Section title="Cross-Examination" subtitle={debateFocus}>
              {debateAgents.map(([key, a]) => <AgentBlock key={key} k={key} a={a} expanded={!!expanded[key]} toggle={toggle} />)}
            </Section>
          )}
          {finalOutput && (
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4">
              <div className="flex items-center gap-2 mb-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /><h3 className="text-sm font-semibold">Marketing Director — Final Reconciled Plan</h3></div>
              <div className="prose prose-sm dark:prose-invert max-w-none text-sm"><ReactMarkdown remarkPlugins={[remarkGfm]}>{finalOutput}</ReactMarkdown></div>
            </div>
          )}
        </>
      )}
      <div ref={endRef} />
    </div>
  );
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h4>
        {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5 italic">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function AgentBlock({ k, a, expanded, toggle }: { k: string; a: AgentCard; expanded: boolean; toggle: (k: string) => void }) {
  const p = getAgentProfile(a.roleId);
  return (
    <div className={cn('rounded-lg border p-3', a.done ? 'border-border' : 'border-primary/40 bg-primary/5')}>
      <button onClick={() => toggle(k)} className="w-full flex items-center gap-2 text-left">
        <span className="flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold shrink-0" style={{ background: p.bgColor, color: p.color, border: `1px solid ${p.borderColor}` }}>{p.initials}</span>
        <span className="text-sm font-medium flex-1">{a.roleName}</span>
        {a.cost > 0 && <span className="text-[10px] text-muted-foreground">${a.cost.toFixed(2)}</span>}
        {!a.done && <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />}
        {a.done && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
        {expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
      </button>
      {expanded && (
        <div className="mt-2 pl-8">
          {a.tools.length === 0 && a.phase === 'specialists' && <p className="text-[10px] text-muted-foreground mb-1">analysis-only · no API calls</p>}
          <div className="prose prose-sm dark:prose-invert max-w-none text-[13px]">
            {a.text ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{a.text}</ReactMarkdown> : <span className="text-xs text-muted-foreground italic">working…</span>}
          </div>
        </div>
      )}
    </div>
  );
}
