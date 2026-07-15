import { useMemo, useState } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ChevronRight,
  ChevronDown,
  Square,
  Gavel,
  History as HistoryIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { getAgentProfile } from '@/lib/agentProfiles';
import AgentAvatar from '@/components/chat/AgentAvatar';
import type {
  OrchestrationEvent,
  MemoryRecallPayload,
  VerificationPayload,
  AgentCalledPayload,
  AgentProgressPayload,
  AgentResultPayload,
  DirectorThoughtPayload,
  PlanPayload,
  ConflictPayload,
  DecisionPayload,
  ClaimGatePayload,
  FinalDonePayload,
  Finding,
} from '@/types/orchestration';

// ---------------------------------------------------------------------------
// OrchestrationLedger — the live-activity renderer for Chat Orchestration v2
// (Epic 3: story 3.1 rows · 3.2 post-completion collapse · 3.4 per-row stop).
//
// Pure render over an ordered v2 event list. Used LIVE (accumulating events off
// the turn SSE) and in HISTORY replay (events fetched from chat_turn_events).
// Every element maps to a real backend event; nothing is invented (DESIGN.md
// §99-104). The Director's prose is rendered by ChatMessage, NOT here.
// ---------------------------------------------------------------------------

export interface OrchestrationLedgerProps {
  /** Ordered v2 events for ONE turn (live-accumulated OR history-replayed).
   *  ONLY v2 types are passed (final_chunk/final_start/final_done may be present
   *  but the Director prose itself is rendered by ChatMessage, NOT here). */
  events: OrchestrationEvent[];
  /** Terminal when turn_done/turn_error/turn_stopped/final_done seen. When true,
   *  render the collapsed one-line summary row (story 3.2), expandable. */
  isComplete: boolean;
  /** Wired to the per-specialist stop endpoint (story 2.6/3.4). Present only for
   *  a LIVE turn; undefined in history replay → per-row stop buttons hidden.
   *  callId = the specialist's call_id. */
  onStopCall?: (callId: string) => void;
}

/** Links open safely; matches the ChatMessage markdown contract. */
const mdComponents: Components = {
  a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
};

// ---- render model ----------------------------------------------------------

interface RecallChild {
  key: string;
  roleId?: string;
  source: string;
  ageDays?: number;
  staleness?: string;
  decision: string;
  summary?: string;
}

interface SpecialistRow {
  kind: 'specialist';
  order: number;
  callId: string;
  roleId?: string;
  roleName?: string;
  task?: string;
  reason?: string;
  reusedFrom?: string;
  textPreview: string;
  tools: { key: string; source?: string; name?: string; input?: string }[];
  status: 'running' | 'ok' | 'failed' | 'stopped' | string;
  cost?: number;
  durationMs?: number;
  findings: Finding[];
  summary?: string;
}

interface RecallRow {
  kind: 'recall';
  order: number;
  found: number;
  stale: number;
  ts?: string;
  children: RecallChild[];
}

interface VerifyRow {
  kind: 'verify';
  order: number;
  key: string;
  status: string;
  detail?: string;
}

interface ThoughtRow {
  kind: 'thought';
  order: number;
  key: string;
  text: string;
}

/** One disagreeing specialist's stance, with the call_id resolved to a role
 *  name at BUILD time so the row stays a pure renderer (story 3.3). */
interface ConflictPosition {
  callId: string;
  roleName: string;
  stance: string;
}

interface ConflictRow {
  kind: 'conflict';
  order: number;
  key: string;
  id: string;
  topic: string;
  between: string[];
  positions: ConflictPosition[];
}

interface DecisionRow {
  kind: 'decision';
  order: number;
  key: string;
  ruling: string;
  rationale?: string;
  conflictId?: string;
  /** Topic of the conflict this decision resolves, joined by conflict_id. */
  resolvesTopic?: string;
}

interface ClaimGateRow {
  kind: 'claim_gate';
  order: number;
  key: string;
  checked: number;
  passed: number;
  rewritten: { claim: string; reason: string }[];
  flagged: { claim: string; reason: string }[];
}

type LedgerRow =
  | RecallRow
  | VerifyRow
  | SpecialistRow
  | ThoughtRow
  | ConflictRow
  | DecisionRow
  | ClaimGateRow;

interface LedgerModel {
  rows: LedgerRow[];
  specialistCount: number; // distinct completed specialist call_ids
  conflictCount: number;
  totalCost: number;
  totalDurationMs: number;
  finalDone?: FinalDonePayload;
}

// Narrow the loose envelope payload to the per-type shape.
function payloadOf<T>(ev: OrchestrationEvent): T {
  return (ev.payload ?? {}) as T;
}

// Story 1.4 (frontend half) — tail-window cap on the streamed text preview so
// token-level agent_progress can't grow the row's textPreview without bound.
// The visible 3-line CSS clamp (SpecialistLedgerRow) is the VISUAL cap; this is
// the MEMORY cap. A bit above the ~500 the plan cites for tool_results so the
// clamped 3 lines always have content.
const PREVIEW_TAIL_CHARS = 600;

function fmtTs(ts?: string): string {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function buildModel(events: OrchestrationEvent[]): LedgerModel {
  const rows: LedgerRow[] = [];

  // The single aggregated "Checked prior work" row — created lazily on first recall.
  let recallRow: RecallRow | null = null;
  // Specialist rows keyed by call_id so progress/result mutate the same row.
  const specialists = new Map<string, SpecialistRow>();
  const conflicts = new Set<string>();
  // conflict_id → topic, so a decision can name the conflict it resolves (3.3).
  const conflictTopics = new Map<string, string>();

  // Resolve a specialist call_id → display role name via the specialists Map
  // (built as plan/agent_called land), falling back to the persona profile or
  // the raw call_id. Build-time resolution keeps the conflict row a pure renderer.
  const resolveRoleName = (callId: string): string => {
    const row = specialists.get(callId);
    if (row?.roleName) return row.roleName;
    if (row?.roleId) return getAgentProfile(row.roleId).name;
    return callId;
  };
  let finalDone: FinalDonePayload | undefined;
  let totalCost = 0;
  let totalDurationMs = 0;

  events.forEach((ev, idx) => {
    switch (ev.type) {
      case 'director_thought': {
        const p = payloadOf<DirectorThoughtPayload>(ev);
        if (p.text) {
          rows.push({ kind: 'thought', order: idx, key: `th-${idx}`, text: p.text });
        }
        break;
      }

      case 'memory_recall': {
        const p = payloadOf<MemoryRecallPayload>(ev);
        if (!recallRow) {
          recallRow = { kind: 'recall', order: idx, found: 0, stale: 0, ts: ev.ts, children: [] };
          rows.push(recallRow);
        }
        // Aggregate: `found` counts entries the Director actually considered
        // (reuse/reverify — not the ones it dropped as `ignore`).
        if (p.decision !== 'ignore') recallRow.found += 1;
        if (p.staleness === 'stale') recallRow.stale += 1;
        recallRow.ts = recallRow.ts ?? ev.ts;
        recallRow.children.push({
          key: `rc-${idx}`,
          roleId: p.role_id,
          source: p.source,
          ageDays: p.age_days,
          staleness: p.staleness,
          decision: p.decision,
          summary: p.summary,
        });
        break;
      }

      case 'verification': {
        const p = payloadOf<VerificationPayload>(ev);
        rows.push({
          kind: 'verify',
          order: idx,
          key: `vf-${idx}`,
          status: p.status,
          detail: p.detail,
        });
        break;
      }

      case 'plan': {
        // Pre-seed specialist rows so a row shows BEFORE agent_called lands
        // (mirrors WorkflowPanel's plan case). agent_called then fills details.
        const p = payloadOf<PlanPayload>(ev);
        for (const s of p.specialists ?? []) {
          if (specialists.has(s.call_id)) continue;
          const row: SpecialistRow = {
            kind: 'specialist',
            order: idx,
            callId: s.call_id,
            roleId: s.role_id,
            roleName: s.role_name,
            task: s.task,
            reason: s.reason,
            reusedFrom: s.reused_from,
            textPreview: '',
            tools: [],
            status: 'running',
            findings: [],
          };
          specialists.set(s.call_id, row);
          rows.push(row);
        }
        break;
      }

      case 'agent_called': {
        const p = payloadOf<AgentCalledPayload>(ev);
        const existing = specialists.get(p.call_id);
        if (existing) {
          existing.roleId = p.role_id ?? existing.roleId;
          existing.roleName = p.role_name ?? existing.roleName;
          existing.task = p.task ?? existing.task;
          existing.reusedFrom = p.reused_from ?? existing.reusedFrom;
          existing.status = 'running';
        } else {
          const row: SpecialistRow = {
            kind: 'specialist',
            order: idx,
            callId: p.call_id,
            roleId: p.role_id,
            roleName: p.role_name,
            task: p.task,
            reusedFrom: p.reused_from,
            textPreview: '',
            tools: [],
            status: 'running',
            findings: [],
          };
          specialists.set(p.call_id, row);
          rows.push(row);
        }
        break;
      }

      case 'agent_progress': {
        const p = payloadOf<AgentProgressPayload>(ev);
        const row = specialists.get(p.call_id);
        if (!row) break;
        if (p.kind === 'tool' && p.tool) {
          row.tools.push({
            key: `tl-${idx}`,
            source: p.tool.source,
            name: p.tool.name,
            input: p.tool.input_summary,
          });
        } else if (p.content) {
          // Story 1.4: keep only the last PREVIEW_TAIL_CHARS chars. Handles
          // content-per-token (new backend partials) and content-per-block (old)
          // identically — it's just concat + tail-slice.
          row.textPreview = (row.textPreview + p.content).slice(-PREVIEW_TAIL_CHARS);
        }
        break;
      }

      case 'agent_result': {
        const p = payloadOf<AgentResultPayload>(ev);
        const row = specialists.get(p.call_id);
        if (row) {
          row.status = p.status;
          row.cost = p.cost;
          row.durationMs = p.duration_ms;
          row.findings = p.findings ?? [];
          row.summary = p.summary;
          row.roleId = p.role_id ?? row.roleId;
        }
        if (typeof p.cost === 'number') totalCost += p.cost;
        if (typeof p.duration_ms === 'number') totalDurationMs += p.duration_ms;
        break;
      }

      case 'conflict': {
        const p = payloadOf<ConflictPayload>(ev);
        conflicts.add(p.id);
        if (p.topic) conflictTopics.set(p.id, p.topic);
        // Resolve each disagreeing specialist's call_id → role name at BUILD
        // time so the row is a pure renderer (story 3.3).
        const positions: ConflictPosition[] = (p.positions ?? []).map((pos) => ({
          callId: pos.call_id,
          roleName: resolveRoleName(pos.call_id),
          stance: pos.stance,
        }));
        rows.push({
          kind: 'conflict',
          order: idx,
          key: `cf-${idx}`,
          id: p.id,
          topic: p.topic,
          between: p.between ?? [],
          positions,
        });
        break;
      }

      case 'decision': {
        const p = payloadOf<DecisionPayload>(ev);
        if (p.ruling) {
          rows.push({
            kind: 'decision',
            order: idx,
            key: `dc-${idx}`,
            ruling: p.ruling,
            rationale: p.rationale,
            conflictId: p.conflict_id,
            // Join decision → conflict by conflict_id when present.
            resolvesTopic: p.conflict_id ? conflictTopics.get(p.conflict_id) : undefined,
          });
        }
        break;
      }

      case 'claim_gate': {
        const p = payloadOf<ClaimGatePayload>(ev);
        rows.push({
          kind: 'claim_gate',
          order: idx,
          key: `cg-${idx}`,
          checked: p.checked,
          passed: p.passed,
          rewritten: p.rewritten ?? [],
          flagged: p.flagged ?? [],
        });
        break;
      }

      case 'final_done': {
        finalDone = payloadOf<FinalDonePayload>(ev);
        break;
      }

      default:
        // turn_start / final_start / final_chunk / turn_done / turn_error /
        // turn_stopped and any v1 leak → nothing to render in the ledger.
        break;
    }
  });

  const completedSpecialists = [...specialists.values()].filter(
    (s) => s.status !== 'running'
  ).length;

  return {
    rows,
    specialistCount: completedSpecialists || specialists.size,
    conflictCount: conflicts.size,
    totalCost,
    totalDurationMs,
    finalDone,
  };
}

// ---- small presentational atoms -------------------------------------------

type DotTone = 'pending' | 'success' | 'danger' | 'neutral';

function Dot({ tone }: { tone: DotTone }) {
  return (
    <span
      className={cn(
        'h-2 w-2 shrink-0 rounded-full',
        tone === 'pending' && 'studio-pulse bg-accent',
        tone === 'success' && 'bg-success',
        tone === 'danger' && 'bg-danger',
        tone === 'neutral' && 'bg-subtle'
      )}
      aria-hidden="true"
    />
  );
}

function Caret({ open }: { open: boolean }) {
  return open ? (
    <ChevronDown className="h-3 w-3 shrink-0 text-subtle" />
  ) : (
    <ChevronRight className="h-3 w-3 shrink-0 text-subtle" />
  );
}

/** One quiet ledger line — a dot, content, optional trailing meta. */
function Row({
  children,
  onClick,
  className,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  const base =
    '-mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors duration-150';
  if (onClick) {
    return (
      <button onClick={onClick} className={cn(base, 'hover:bg-surface-2', className)}>
        {children}
      </button>
    );
  }
  return <div className={cn(base, className)}>{children}</div>;
}

function Indent({ children }: { children: React.ReactNode }) {
  return <div className="ml-3 border-l border-border pl-3">{children}</div>;
}

// ---- recall row ------------------------------------------------------------

function RecallLedgerRow({ row }: { row: RecallRow }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <Row onClick={() => setOpen((o) => !o)}>
        <Dot tone="success" />
        <span className="font-medium text-text">Checked prior work</span>
        <span className="text-subtle">
          {row.found} found
          {row.stale > 0 ? ` · ${row.stale} stale` : ''}
        </span>
        {row.ts && <span className="ml-auto shrink-0 text-[10px] text-subtle">{fmtTs(row.ts)}</span>}
        <span className={cn(row.ts ? 'ml-1' : 'ml-auto')}>
          <Caret open={open} />
        </span>
      </Row>
      {open && row.children.length > 0 && (
        <Indent>
          <div className="space-y-0.5 py-1">
            {row.children.map((c) => {
              if (c.decision === 'ignore') return null;
              const name = c.roleId ? getAgentProfile(c.roleId).name : c.source;
              return (
                <div key={c.key} className="flex items-start gap-2 text-[11px] leading-snug">
                  <span className="mt-0.5 shrink-0 font-medium text-text">{name}</span>
                  {typeof c.ageDays === 'number' && (
                    <span className="mt-0.5 shrink-0 text-subtle">{c.ageDays}d</span>
                  )}
                  {c.decision === 'reuse' && (
                    <span className="mt-0.5 shrink-0 text-subtle">reused</span>
                  )}
                  {c.decision === 'reverify' && (
                    <span className="mt-0.5 shrink-0 rounded-full bg-warning-soft px-1.5 py-0 text-[10px] text-warning">
                      re-verifying
                    </span>
                  )}
                  {c.summary && (
                    <span className="min-w-0 truncate text-muted-foreground">{c.summary}</span>
                  )}
                </div>
              );
            })}
          </div>
        </Indent>
      )}
    </div>
  );
}

// ---- verification row ------------------------------------------------------

function VerifyLedgerRow({ row }: { row: VerifyRow }) {
  const tone: DotTone =
    row.status === 'verified' ? 'success' : row.status === 'failed' ? 'danger' : 'neutral';
  const label = row.status === 'failed' ? 'Landing page check failed' : 'Verified landing page';
  return (
    <Row>
      <Dot tone={tone} />
      <span className="font-medium text-text">{label}</span>
      {row.detail && <span className="min-w-0 truncate text-muted-foreground">{row.detail}</span>}
    </Row>
  );
}

// ---- specialist row --------------------------------------------------------

function fmtDuration(ms?: number): string {
  if (typeof ms !== 'number' || ms <= 0) return '';
  return `${Math.round(ms / 1000)}s`;
}

function SpecialistLedgerRow({
  row,
  onStopCall,
}: {
  row: SpecialistRow;
  onStopCall?: (callId: string) => void;
}) {
  const running = row.status === 'running';
  // Expand state: seeded from running (auto-expand while streaming, auto-collapse
  // on result), but user-toggleable. Undefined = follow the auto default.
  const [override, setOverride] = useState<boolean | undefined>(undefined);
  const expanded = override ?? running;
  const profile = getAgentProfile(row.roleId);

  const tone: DotTone =
    row.status === 'ok'
      ? 'success'
      : row.status === 'failed' || row.status === 'stopped'
        ? 'danger'
        : 'pending';

  // Trailing meta — never a green check on failure/stopped (DESIGN.md:88).
  let meta: React.ReactNode = null;
  if (running) {
    meta = <span className="text-subtle">running</span>;
  } else if (row.status === 'ok') {
    const parts = ['done'];
    const dur = fmtDuration(row.durationMs);
    if (dur) parts.push(dur);
    if (typeof row.cost === 'number') parts.push(`$${row.cost.toFixed(2)}`);
    meta = <span className="text-subtle">{parts.join(' · ')}</span>;
  } else if (row.status === 'failed') {
    meta = <span className="text-danger">failed - Director proceeding without it</span>;
  } else if (row.status === 'stopped') {
    meta = <span className="text-danger">stopped by user - Director proceeding without it</span>;
  }

  const hasDetail =
    row.textPreview.trim().length > 0 ||
    row.tools.length > 0 ||
    row.findings.length > 0 ||
    !!row.summary ||
    !!row.task;

  return (
    <div>
      <div className="group -mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors duration-150 hover:bg-surface-2">
        <Dot tone={tone} />
        <AgentAvatar roleId={row.roleId} size="sm" showStatus isWorking={running} />
        <span className="min-w-0 shrink-0 truncate font-medium text-text">
          {row.roleName || profile.name}
        </span>
        <span className="shrink-0 text-[10px] text-muted-foreground">{profile.title}</span>
        {row.reusedFrom && <span className="shrink-0 text-[10px] text-subtle">reused</span>}
        <span className="ml-auto shrink-0">{meta}</span>

        {/* Per-row stop (story 3.4) — only while running AND live (onStopCall set). */}
        {running && onStopCall && (
          <button
            onClick={() => onStopCall(row.callId)}
            title="Stop this specialist"
            className="shrink-0 rounded p-0.5 text-subtle transition-colors hover:bg-danger-soft hover:text-danger"
          >
            <Square className="h-3 w-3" />
          </button>
        )}

        {hasDetail && (
          <button
            onClick={() => setOverride(!expanded)}
            title={expanded ? 'Collapse' : 'Expand'}
            className="shrink-0"
          >
            <Caret open={expanded} />
          </button>
        )}
      </div>

      {expanded && hasDetail && (
        <Indent>
          <div className="space-y-1.5 py-1">
            {row.task && <p className="text-[11px] italic text-muted-foreground">{row.task}</p>}
            {row.reason && <p className="text-[11px] text-subtle">{row.reason}</p>}

            {/* Streaming/text preview — clamped to 3 lines. */}
            {row.textPreview.trim() && (
              <div className="studio-prose max-h-[4.2rem] overflow-hidden text-[12px] [&_*]:line-clamp-3">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                  {row.textPreview}
                </ReactMarkdown>
              </div>
            )}

            {/* Quiet mono tool rows (agent_progress kind='tool'). */}
            {row.tools.map((t) => (
              <div
                key={t.key}
                className="flex items-center gap-2 font-mono text-[11px] text-muted-foreground"
              >
                <span className="text-subtle">{[t.source, t.name].filter(Boolean).join('·')}</span>
                {t.input && <span className="min-w-0 truncate text-subtle">{t.input}</span>}
              </div>
            ))}

            {row.summary && !running && (
              <p className="text-[11px] text-muted-foreground">{row.summary}</p>
            )}

            {/* Findings — quiet child rows: claim + severity + confidence/sources. */}
            {row.findings.length > 0 && (
              <div className="space-y-0.5 pt-0.5">
                {row.findings.map((f) => (
                  <FindingRow key={f.id} finding={f} />
                ))}
              </div>
            )}
          </div>
        </Indent>
      )}
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  const sourceHint = finding.sources?.map((s) => s.tag).join(', ');
  return (
    <div className="flex items-start gap-2 text-[11px] leading-snug">
      <Dot tone="neutral" />
      <span className="min-w-0 flex-1 text-muted-foreground">{finding.claim}</span>
      {finding.severity && (
        <span
          className={cn(
            'shrink-0 rounded-full px-1.5 py-0 text-[10px]',
            finding.severity === 'high'
              ? 'bg-danger-soft text-danger'
              : finding.severity === 'medium'
                ? 'bg-warning-soft text-warning'
                : 'bg-surface-3 text-subtle'
          )}
        >
          {finding.severity}
        </span>
      )}
      {typeof finding.confidence === 'number' && (
        <span className="shrink-0 text-[10px] text-subtle">
          {Math.round(finding.confidence * 100)}%
        </span>
      )}
      {sourceHint && <span className="shrink-0 text-[10px] text-subtle">{sourceHint}</span>}
    </div>
  );
}

// ---- claim gate row --------------------------------------------------------

function ClaimGateLedgerRow({ row }: { row: ClaimGateRow }) {
  const [open, setOpen] = useState(false);
  const issues = [
    ...row.rewritten.map((r) => ({ ...r, mode: 'rewritten' as const })),
    ...row.flagged.map((r) => ({ ...r, mode: 'flagged' as const })),
  ];
  const hasIssues = issues.length > 0;
  // Verified = quiet (neutral). Issues = calm warning, never danger-red — the
  // gate correcting itself is expected work, not a hard failure (DESIGN.md:99-104).
  const tone: DotTone = hasIssues ? 'neutral' : 'success';

  const summary = (
    <>
      <Dot tone={tone} />
      <span className="text-subtle">
        {row.passed}/{row.checked} claims verified
      </span>
      {hasIssues && (
        <span className="ml-1 shrink-0 rounded-full bg-warning-soft px-1.5 py-0 text-[10px] text-warning">
          {issues.length} corrected
        </span>
      )}
    </>
  );

  if (!hasIssues) {
    // Clean gate → a single quiet row, no expand affordance.
    return <Row>{summary}</Row>;
  }

  return (
    <div>
      <Row onClick={() => setOpen((o) => !o)}>
        {summary}
        <span className="ml-auto">
          <Caret open={open} />
        </span>
      </Row>
      {open && (
        <Indent>
          <div className="space-y-0.5 py-1">
            {issues.map((it, i) => (
              <div
                key={`cgi-${i}`}
                className="flex items-start gap-2 text-[11px] leading-snug"
              >
                <span
                  className={cn(
                    'mt-0.5 shrink-0 rounded-full px-1.5 py-0 text-[10px]',
                    'bg-warning-soft text-warning'
                  )}
                >
                  {it.mode === 'rewritten' ? 'rewritten' : 'flagged'}
                </span>
                <span className="min-w-0 shrink-0 truncate font-mono text-text">
                  {it.claim}
                </span>
                <span className="min-w-0 text-muted-foreground">{it.reason}</span>
              </div>
            ))}
          </div>
        </Indent>
      )}
    </div>
  );
}

// ---- conflict row (story 3.3) ----------------------------------------------

function ConflictLedgerRow({ row }: { row: ConflictRow }) {
  const [open, setOpen] = useState(false);
  const hasPositions = row.positions.length > 0;
  return (
    <div>
      <Row onClick={hasPositions ? () => setOpen((o) => !o) : undefined}>
        <Gavel className="h-3 w-3 shrink-0 text-subtle" />
        <span className="min-w-0 truncate font-medium text-text">Conflict: {row.topic}</span>
        {hasPositions && (
          <span className="shrink-0 text-subtle">
            {row.positions.length} position{row.positions.length === 1 ? '' : 's'}
          </span>
        )}
        {hasPositions && (
          <span className="ml-auto">
            <Caret open={open} />
          </span>
        )}
      </Row>
      {open && hasPositions && (
        <Indent>
          {/* Disagreeing specialists side-by-side (compact): {RoleName}: {stance}. */}
          <div className="space-y-0.5 py-1">
            {row.positions.map((pos, i) => (
              <div
                key={`cfp-${i}`}
                className="flex items-start gap-2 rounded-md border border-border bg-surface-2 px-2 py-1 text-[11px] leading-snug"
              >
                <span className="mt-0 shrink-0 font-medium text-text">{pos.roleName}</span>
                <span className="min-w-0 text-muted-foreground">{pos.stance}</span>
              </div>
            ))}
          </div>
        </Indent>
      )}
    </div>
  );
}

// ---- decision row (story 3.3) — the quiet "verdict" moment ------------------

function DecisionLedgerRow({ row }: { row: DecisionRow }) {
  const [open, setOpen] = useState(false);
  const hasDetail = !!row.rationale || !!row.resolvesTopic;
  return (
    <div>
      <Row onClick={hasDetail ? () => setOpen((o) => !o) : undefined}>
        <Gavel className="h-3 w-3 shrink-0 text-accent" />
        {/* The ruling in text-accent is the ONLY color lift (DESIGN.md). */}
        <span className="min-w-0 truncate font-medium text-accent">{row.ruling}</span>
        {hasDetail && (
          <span className="ml-auto">
            <Caret open={open} />
          </span>
        )}
      </Row>
      {open && hasDetail && (
        <Indent>
          <div className="space-y-0.5 py-1">
            {row.resolvesTopic && (
              <p className="text-[11px] text-subtle">resolves: {row.resolvesTopic}</p>
            )}
            {row.rationale && (
              <p className="text-[11px] text-muted-foreground">{row.rationale}</p>
            )}
          </div>
        </Indent>
      )}
    </div>
  );
}

// ---- one row dispatcher ----------------------------------------------------

function LedgerRowView({
  row,
  onStopCall,
}: {
  row: LedgerRow;
  onStopCall?: (callId: string) => void;
}) {
  switch (row.kind) {
    case 'recall':
      return <RecallLedgerRow row={row} />;
    case 'verify':
      return <VerifyLedgerRow row={row} />;
    case 'specialist':
      return <SpecialistLedgerRow row={row} onStopCall={onStopCall} />;
    case 'thought':
      return (
        <Row>
          <Dot tone="neutral" />
          <span className="italic text-muted-foreground">{row.text}</span>
        </Row>
      );
    // ---- story 3.3 — conflict + decision rows (collapsed-by-default). --------
    case 'conflict':
      return <ConflictLedgerRow row={row} />;
    case 'decision':
      return <DecisionLedgerRow row={row} />;
    case 'claim_gate':
      return <ClaimGateLedgerRow row={row} />;
    default:
      return null;
  }
}

// ---- summary (story 3.2) ---------------------------------------------------

function SummaryLine({ model }: { model: LedgerModel }) {
  const n = model.finalDone?.agents_used ?? model.specialistCount;
  const k = model.finalDone?.conflicts_resolved ?? model.conflictCount;
  const durMs = model.finalDone?.duration_ms ?? model.totalDurationMs;
  const cost = model.finalDone?.cost_total ?? model.totalCost;

  const parts = ['Orchestrated', `${n} specialist${n === 1 ? '' : 's'}`];
  if (k > 0) parts.push(`${k} conflict${k === 1 ? '' : 's'}`);
  const dur = fmtDuration(durMs);
  if (dur) parts.push(dur);
  if (cost > 0) parts.push(`$${cost.toFixed(2)}`);

  return (
    <span className="text-muted-foreground">
      <span className="font-medium text-text">{parts[0]}</span>
      {parts.length > 1 && ` · ${parts.slice(1).join(' · ')}`}
    </span>
  );
}

// ---- component -------------------------------------------------------------

export default function OrchestrationLedger({
  events,
  isComplete,
  onStopCall,
}: OrchestrationLedgerProps): React.ReactElement | null {
  const model = useMemo(() => buildModel(events), [events]);

  // Post-completion collapse (story 3.2): start collapsed once complete; the
  // user can expand to the full historical ledger and collapse again.
  const [collapsed, setCollapsed] = useState(isComplete);

  // Nothing renderable and not complete → render nothing (contract).
  if (model.rows.length === 0 && !isComplete) return null;
  if (model.rows.length === 0) return null;

  if (isComplete && collapsed) {
    return (
      <div className="mt-1 text-xs">
        <Row onClick={() => setCollapsed(false)} className="hover:bg-surface-2">
          <HistoryIcon className="h-3 w-3 shrink-0 text-muted-foreground" />
          <SummaryLine model={model} />
          <span className="ml-auto">
            <ChevronRight className="h-3 w-3 shrink-0 text-subtle" />
          </span>
        </Row>
      </div>
    );
  }

  return (
    <div className="mt-1 space-y-0.5 text-xs">
      {isComplete && (
        <Row onClick={() => setCollapsed(true)} className="hover:bg-surface-2">
          <ChevronDown className="h-3 w-3 shrink-0 text-subtle" />
          <SummaryLine model={model} />
        </Row>
      )}
      {model.rows.map((row) => (
        <LedgerRowView
          key={rowKey(row)}
          row={row}
          onStopCall={onStopCall}
        />
      ))}
    </div>
  );
}

function rowKey(row: LedgerRow): string {
  switch (row.kind) {
    case 'specialist':
      return `sp-${row.callId}`;
    case 'recall':
      return `recall-${row.order}`;
    default:
      return row.key;
  }
}
