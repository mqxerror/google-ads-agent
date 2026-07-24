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
  /** IDs traceable to a MEMORY / account-records source (not re-verified live
   *  this turn): SOFT-labeled in place rather than hard-rewritten (item 3). */
  soft_labeled?: { claim: string; reason: string }[];
}

/** A "degrades, never blocks" input was unavailable this turn (item 2). Recall,
 *  landing-page fetch, live conversion registry, plan tool-grant, video-director
 *  consult — each emits one of these so the ledger names what was missing
 *  (amber, survives collapse) and the Director's answer says so too. */
export interface DegradePayload {
  stage: 'recall' | 'landing_page' | 'conversion_registry' | 'plan_reask' | 'consult' | string;
  /** Short label for the missing capability (e.g. "Prior-work recall"). */
  what: string;
  /** One line: what the answer is missing as a result. */
  impact: string;
  detail?: string;
}

/** A non-identical message arrived while a turn was still running on this
 *  conversation, so it was QUEUED to start after the running turn finishes
 *  (item 4 — never two live turns on one conversation). */
export interface TurnQueuedPayload {
  message?: string;
  behind_turn_id?: string;
}

/** Anti-sycophancy — the Director DECLARED that today's recommendation reverses
 *  a PRIOR POSITION (piece 2). `reason:"evidence"` names the genuinely-new fact;
 *  `reason:"deference"` is a labeled flip to the user's judgment with the
 *  recommendation that STANDS. Rendered quiet for evidence, amber for deference;
 *  survives the post-completion collapse. */
export interface PositionChangePayload {
  prior: string;
  new: string;
  reason: 'evidence' | 'deference' | string;
  /** Present when reason=evidence: the new fact + when it became known. */
  evidence?: string;
  /** Present when reason=deference: the recommendation that stands. */
  stands_as?: string;
}

/** Anti-sycophancy ENFORCEMENT — the answer reversed a prior directional
 *  position but the Director did NOT emit a position_change declaration. Loud by
 *  design (a silent flip is the whole failure being guarded); survives collapse. */
export interface PositionReversalWarningPayload {
  prior: string;
  new: string;
  detail?: string;
}

/** A budget threshold was crossed mid-turn. Two flavors, keyed by `kind`:
 *  - 'notice' — the $5 WATCH level was crossed; the turn KEEPS running. Purely
 *    informational (Wassim: on CLI/subscription, no hard limit — just SHOW when a
 *    turn gets expensive). `cap_usd` carries the WATCH level, `cost` the running
 *    estimate. Rendered as a quiet one-line amber chip.
 *  - 'stop'   — the runaway BACKSTOP was hit; DISPATCH was cut short and a
 *    COMPLETE wrap-up was synthesized from state (the turn never ends
 *    mid-sentence). Rendered as the prominent wrap-up banner.
 *  Absent `kind` (legacy events) is treated as 'stop'. */
export interface BudgetNoticePayload {
  kind?: 'notice' | 'stop' | string;
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
  /** Best-effort spend before the kill (a NOTE, not billing). Add-on §5. */
  cost_on_kill?: number;
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
  | 'degrade'
  | 'turn_queued'
  | 'position_change'
  | 'position_reversal_warning'
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
  'degrade',
  'turn_queued',
  'position_change',
  'position_reversal_warning',
  'turn_done',
  'turn_error',
  'turn_stopped',
]);

export function isV2Event(ev: { type?: string }): boolean {
  return !!ev.type && V2_EVENT_TYPES.has(ev.type);
}
