// Chat Orchestration v2 — event protocol types (§4.3 envelope + §4.4 vocabulary).
//
// Every SSE `data:` line in a v2 turn stream is ONE JSON object matching
// `OrchestrationEvent`. v1 event types (routing/text/tool_call/…) keep flowing
// inside the SAME envelope for direct-mode turns and are handled separately in
// ChatPanel; this module models the v2 vocabulary that feeds the ledger.
//
// Source of truth: research/chat-orchestration-v2-plan.md §4.3 / §4.4 and
// research/chat-orch-v2-build-contract.md.

/** Provenance tag on a specialist finding's source (§7.1). */
export interface FindingSource {
  tag: string; // LIVE_API | LOCAL_STORE | MEMORY | PAGE_FETCH | USER
  ts?: string;
  detail?: string;
}

/** One structured claim a specialist returns (§5.6). */
export interface Finding {
  id: string;
  claim: string;
  severity?: string;
  confidence?: number;
  sources?: FindingSource[];
  disconfirmed_by?: string;
}

// ---- v2 payloads (discriminated by the envelope `type`) --------------------

export interface TurnStartPayload {
  mode: 'direct' | 'orchestrated' | 'delegated';
  campaign_id?: string | null;
  campaign_name?: string | null;
  model?: string;
}

export interface DirectorThoughtPayload {
  text: string;
  stage?: string; // triage | recall | plan | resolve | synth
}

export interface MemoryRecallPayload {
  source: string;
  ref_id?: string;
  role_id?: string;
  age_days?: number;
  staleness?: 'fresh' | 'stale' | string;
  decision: 'reuse' | 'reverify' | 'ignore' | string;
  summary?: string;
}

export interface VerificationPayload {
  kind: 'landing_page' | 'ids' | 'metrics' | string;
  status: 'verified' | 'failed' | 'skipped' | string;
  detail?: string;
}

export interface PlanSpecialist {
  call_id: string;
  role_id: string;
  role_name?: string;
  task?: string;
  model?: string;
  tools?: string[];
  reason?: string;
  reused_from?: string;
}

export interface PlanPayload {
  specialists: PlanSpecialist[];
  parallel_groups?: string[][];
}

export interface AgentCalledPayload {
  call_id: string;
  role_id: string;
  role_name?: string;
  task?: string;
  model?: string;
  tools?: string[];
  reused_from?: string;
}

export interface AgentProgressPayload {
  call_id: string;
  kind: 'text' | 'tool';
  content?: string;
  tool?: { source?: string; name?: string; input_summary?: string };
}

export interface AgentResultPayload {
  call_id: string;
  role_id?: string;
  status: 'ok' | 'failed' | 'stopped' | string;
  cost?: number;
  duration_ms?: number;
  findings?: Finding[];
  summary?: string;
}

export interface ConflictPayload {
  id: string;
  between: string[];
  topic: string;
  positions?: { call_id: string; stance: string }[];
}

export interface DecisionPayload {
  conflict_id?: string;
  ruling: string;
  rationale?: string;
  decided_by?: string;
}

export interface FinalDonePayload {
  message_id?: string;
  cost_total?: number;
  duration_ms?: number;
  agents_used?: number;
  conflicts_resolved?: number;
}

export interface ClaimGatePayload {
  checked: number;
  passed: number;
  /** Claims the gate could NOT verify and rewrote in place (unverified IDs,
   *  unbacked page-state assertions). */
  rewritten?: { claim: string; reason: string }[];
  /** Claims the gate surfaced but did NOT rewrite (unmatched material numbers;
   *  page-state claims when no fetch ran this turn). */
  flagged?: { claim: string; reason: string }[];
}

/** The turn budget (cost or wall-clock) was hit mid-turn. DISPATCH is cut short
 *  and a COMPLETE wrap-up is synthesized from state — the turn never ends
 *  mid-sentence. Rendered as a visible ledger notice. */
export interface BudgetNoticePayload {
  reason: 'cost' | 'time' | string;
  cost: number;
  cap_usd: number;
  elapsed_s: number;
  cap_s: number;
  specialists_done: number;
  specialists_total: number;
}

export interface TurnDonePayload {
  stop_reason?: string;
  cost?: number;
  [k: string]: unknown;
}

export interface TurnStoppedPayload {
  stopped_by?: 'user' | string;
  calls_killed?: string[];
  partial_persisted?: boolean;
  /** Specialists whose task involved a write. `stopped_before_write` means an
   *  approved write may not have executed — the user MUST be warned. Empty array
   *  is the common safe case (no write was in flight). */
  specialists?: Array<{
    role_id?: string;
    role_name?: string;
    disposition: 'completed' | 'stopped_before_write';
  }>;
}

export interface TurnErrorPayload {
  message?: string;
  [k: string]: unknown;
}

/** The v2 type string set (used for narrowing in the ledger). */
export type OrchestrationEventType =
  | 'turn_start'
  | 'director_thought'
  | 'memory_recall'
  | 'verification'
  | 'plan'
  | 'agent_called'
  | 'agent_progress'
  | 'agent_result'
  | 'conflict'
  | 'decision'
  | 'final_start'
  | 'final_chunk'
  | 'final_done'
  | 'claim_gate'
  | 'budget_notice'
  | 'turn_done'
  | 'turn_error'
  | 'turn_stopped';

/** The v2 SSE envelope (§4.3). `payload` is intentionally loose — the ledger
 *  narrows per `type` at read time. v1 events flow through the same shape with
 *  a v1 `type` and are handled outside this module. */
export interface OrchestrationEvent<P = Record<string, unknown>> {
  v?: number;
  conversation_id?: string;
  turn_id?: string;
  seq?: number;
  ts?: string;
  type: string;
  payload?: P;
}

/** The exact set of v2 types — anything else (v1 routing/text/tool_call/…) is
 *  NOT rendered by the ledger. */
export const V2_EVENT_TYPES: ReadonlySet<string> = new Set<OrchestrationEventType>([
  'turn_start',
  'director_thought',
  'memory_recall',
  'verification',
  'plan',
  'agent_called',
  'agent_progress',
  'agent_result',
  'conflict',
  'decision',
  'final_start',
  'final_chunk',
  'final_done',
  'claim_gate',
  'budget_notice',
  'turn_done',
  'turn_error',
  'turn_stopped',
]);

export function isV2Event(ev: { type?: string }): boolean {
  return !!ev.type && V2_EVENT_TYPES.has(ev.type);
}
