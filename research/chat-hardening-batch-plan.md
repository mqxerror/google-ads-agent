# Chat Hardening Batch — approved-for-later (Wassim, 2026-07-21 "save it as task or plan for later")

Origin: post-upgrade hidden-issues review (see memory `project-v2-builds-2026-07-12` + session
transcript 2026-07-21). Verified findings + remaining risk register. Execute as ONE Opus build
when Wassim says go ("harden it").

## Batch scope (~1 day)
1. **Global subprocess semaphore** (CONFIRMED gap): chat_orchestrator.py:1080 and
   workflow_orchestrator.py:631 each hold their own `asyncio.Semaphore(_MAX_PARALLEL)` —
   replace with ONE shared cross-component gate (chat + Team Audit + scheduler + video
   director) so concurrent load can't stampede 8+ CLI subprocesses.
2. **Degrade-visibility pass**: every "degrades, never blocks" path (consult timeout,
   landing-page fetch fail, conversion-registry fail, recall fail) must emit a PROMINENT
   ledger event + a Director-answer caveat line — the passive-audit lesson (warnings that
   don't gate are noise; degrades that don't announce are future incidents).
3. **Claim-gate memory-source handling**: a TRUE stored fact (e.g. GTM-K6864NBH from
   guidelines) currently gets rewritten "[not verified this session]" — false positives
   train the user to ignore the gate. Fix: MEMORY-sourced IDs get a soft label
   ("from account records, not re-verified this turn"), rewrite reserved for IDs with NO
   source at all. Keep absence/state/mechanism rules from Jul 21.
4. **Same-conversation turn serialization**: non-identical message during a running turn —
   define queue semantics (queue + notify), kill the interleaved-writeback risk
   (chat.py second-send seam deferred since Epic 0).
5. (Cheap add-ons if in budget) chat_turn_events retention policy (e.g. 90d prune);
   cost-on-kill accounting note.

## Explicitly NOT in this batch (separate tracks)
- Epic 6 persona overhaul (RULE-0: symbol ban, program fact-sheets, step-zero CRM check,
  few-shots — WAITING ON WASSIM'S EXAMPLE ANSWERS).
- Epic 7 eval harness (replay all 2026-07 incidents as regression suite).
- Recall pruning/scoring (design piece — fold into Epic 6/7 planning).
- Old-path divergence (Team Audit tab + scheduled audits lack claim gate/live registry/
  provenance) — biggest remaining structural item; route scheduled runs through the
  orchestrator per chat-orchestration-v2-plan §12 item 5.

Gates as always: suite green (319 baseline), no restarts by builder, feature-log rows.
