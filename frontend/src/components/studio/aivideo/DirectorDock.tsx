/**
 * DirectorDock — the right-hand chat panel. It renders the SAME event array the
 * page accumulates off streamTurn:
 *   - consult / thoughts / specialists  → OrchestrationLedger (reused verbatim)
 *   - concepts                          → 3 angle rows (dot identity, clickable)
 *   - storyboard                        → one "Storyboard ready - N scenes" line
 *   - text                              → streaming studio-prose with a caret
 * The composer sends iterations via draftVideoProject; Stop calls stopTurn.
 * Collapsible to a 40px spine.
 */

import { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronRight, ChevronLeft, Send, Square, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import AgentAvatar from '@/components/chat/AgentAvatar';
import OrchestrationLedger from '@/components/chat/OrchestrationLedger';
import type { OrchestrationEvent } from '@/types/orchestration';

interface ConceptVariant {
  angle: string;
  logline: string;
  rationale?: string;
}

interface SceneFailure {
  scene_index: number;
  error_class: string;
  message: string;
}

// "run"/"quota" failures whose message mentions credits/quota read as a
// spend problem; everything else surfaces its real message.
function looksLikeQuota(errClass: string, message: string): boolean {
  const m = (message || '').toLowerCase();
  return (
    errClass === 'quota' ||
    ((errClass === 'run' || errClass === 'other') &&
      /(credit|quota|insufficient|balance|top ?up|out of)/.test(m))
  );
}

interface DirectorDockProps {
  events: OrchestrationEvent[];
  turnRunning: boolean;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onPickAngle: (angle: string) => void;
  onSend: (message: string) => void;
  onStop: () => void;
  // CHANGE 1: when the last turn_error is a retryable draft-stage timeout,
  // the dock renders a Retry button that re-fires the SAME draft POST.
  retryableDraftTimeout?: boolean;
  onRetryDraft?: () => void;
}

const ANGLE_DOT: Record<string, string> = {
  'problem-led': 'bg-warning',
  aspirational: 'bg-success',
  'social-proof': 'bg-accent',
};

export default function DirectorDock({
  events,
  turnRunning,
  collapsed,
  onToggleCollapse,
  onPickAngle,
  onSend,
  onStop,
  retryableDraftTimeout = false,
  onRetryDraft,
}: DirectorDockProps) {
  const [draft, setDraft] = useState('');

  // Derived views over the same event array.
  const concepts = useMemo<ConceptVariant[]>(() => {
    // last concepts event wins
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'concepts') {
        const p = events[i].payload as { variants?: ConceptVariant[] };
        return p.variants ?? [];
      }
    }
    return [];
  }, [events]);

  const storyboardSceneCount = useMemo<number | null>(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'storyboard') {
        const p = events[i].payload as { scenes?: unknown[] };
        return p.scenes?.length ?? 0;
      }
    }
    return null;
  }, [events]);

  // Latest streaming prose (concatenate contiguous text payloads is overkill —
  // the backend emits growing `content`; take the last text event's content).
  const streamingText = useMemo<string>(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'text') {
        const p = events[i].payload as { content?: string; text?: string };
        return p.content ?? p.text ?? '';
      }
    }
    return '';
  }, [events]);

  const errorText = useMemo<string | null>(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'turn_error') {
        const p = events[i].payload as { message?: string };
        return p.message ?? 'The draft run hit an error.';
      }
    }
    return null;
  }, [events]);

  // ── render-failure classification (new SSE fields) ─────────────────
  // Terminal all-fail: type:"error", stage:"error", scene_failures:[…].
  // Fields may ride in payload OR at the envelope top level — read both.
  const renderFailure = useMemo<{ message: string; failures: SceneFailure[] } | null>(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i] as unknown as {
        type?: string; stage?: string; message?: string; scene_failures?: SceneFailure[];
        payload?: { stage?: string; message?: string; scene_failures?: SceneFailure[] };
      };
      const stage = ev.payload?.stage ?? ev.stage;
      const failures = ev.payload?.scene_failures ?? ev.scene_failures;
      if (ev.type === 'error' && stage === 'error' && Array.isArray(failures)) {
        return { message: ev.payload?.message ?? ev.message ?? 'All scenes failed to render.', failures };
      }
    }
    return null;
  }, [events]);

  // Partial: per-scene skip status events (reel still produced).
  const skippedScenes = useMemo<SceneFailure[]>(() => {
    const out: SceneFailure[] = [];
    for (const ev of events as unknown as Array<{
      type?: string; stage?: string; error_class?: string; message?: string; scene_index?: number;
      payload?: { stage?: string; error_class?: string; message?: string; scene_index?: number };
    }>) {
      const stage = ev.payload?.stage ?? ev.stage;
      if (ev.type === 'status' && stage === 'scene-skipped') {
        out.push({
          scene_index: ev.payload?.scene_index ?? ev.scene_index ?? -1,
          error_class: ev.payload?.error_class ?? ev.error_class ?? 'other',
          message: ev.payload?.message ?? ev.message ?? '',
        });
      }
    }
    return out;
  }, [events]);

  // Auth is dead if the terminal failure OR any skipped scene is class "auth".
  const authFailure = useMemo<boolean>(() => {
    if (renderFailure?.failures.some((f) => f.error_class === 'auth')) return true;
    if (!renderFailure && skippedScenes.some((f) => f.error_class === 'auth')) return true;
    return false;
  }, [renderFailure, skippedScenes]);

  if (collapsed) {
    return (
      <div className="flex w-10 shrink-0 flex-col items-center border-l border-border bg-surface py-3">
        <button
          onClick={onToggleCollapse}
          title="Open Video Director"
          className="rounded p-1 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-text"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span
          className="mt-3 text-[10px] font-semibold uppercase tracking-wide text-subtle"
          style={{ writingMode: 'vertical-rl' }}
        >
          Video Director
        </span>
      </div>
    );
  }

  return (
    <div className="flex w-[360px] shrink-0 flex-col border-l border-border bg-surface">
      {/* header */}
      <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
        <AgentAvatar roleId="video_director" size="md" showStatus isWorking={turnRunning} />
        <span className="text-sm font-medium text-text">Video Director</span>
        <button
          onClick={onToggleCollapse}
          title="Collapse"
          className="ml-auto rounded p-1 text-subtle transition-colors hover:bg-surface-2 hover:text-text"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      {/* body */}
      <div className="min-h-0 flex-1 space-y-3 overflow-auto px-3 py-3">
        {events.length === 0 && !turnRunning && (
          <p className="text-[11px] text-subtle">
            Draft a video from the brief on the left, then talk to the Director here to iterate.
          </p>
        )}

        {/* consult / thoughts / specialists */}
        <OrchestrationLedger events={events} isComplete={!turnRunning && events.length > 0} />

        {/* concepts — dot-identity rows, clickable to pick an angle */}
        {concepts.length > 0 && (
          <div className="space-y-1.5">
            <p className="label-section">Concepts</p>
            {concepts.map((v) => (
              <button
                key={v.angle}
                onClick={() => onPickAngle(v.angle)}
                disabled={turnRunning}
                className="flex w-full items-start gap-2 rounded-md border border-border bg-card px-2.5 py-2 text-left transition-colors hover:bg-surface-2 disabled:opacity-50"
              >
                <span
                  className={cn(
                    'mt-1 h-2 w-2 shrink-0 rounded-full',
                    ANGLE_DOT[v.angle] ?? 'bg-subtle',
                  )}
                />
                <span className="min-w-0">
                  <span className="block text-[12.5px] font-medium text-text">{v.logline}</span>
                  {v.rationale && (
                    <span className="mt-0.5 block text-[11px] text-muted-foreground">
                      {v.rationale}
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* storyboard ready line */}
        {storyboardSceneCount !== null && (
          <p className="text-[12px] text-success">
            Storyboard ready - {storyboardSceneCount} scenes
          </p>
        )}

        {/* streaming prose */}
        {streamingText && (
          <div className="studio-prose text-[12.5px]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
            {turnRunning && <span className="studio-caret">|</span>}
          </div>
        )}

        {errorText && !turnRunning && (
          <div className="space-y-1.5 rounded border border-danger/40 bg-danger-soft px-2 py-1.5">
            <p className="text-[11px] text-danger">{errorText}</p>
            {retryableDraftTimeout && onRetryDraft && (
              <button
                onClick={onRetryDraft}
                className="inline-flex items-center gap-1.5 rounded border border-strong bg-accent px-2.5 py-1 text-[11px] font-medium text-on-accent transition-opacity hover:opacity-90"
              >
                <RotateCcw className="h-3 w-3" />
                Retry draft
              </button>
            )}
          </div>
        )}

        {/* honest render failures (auth / quota / param) */}
        {authFailure && (
          <div className="rounded border border-warning/40 bg-warning-soft px-2 py-1.5 text-[11px] text-warning">
            Higgsfield CLI is not logged in on this Mac. Run{' '}
            <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[10.5px] text-text">
              higgsfield auth login
            </code>{' '}
            in Terminal, then retry.
          </div>
        )}

        {/* terminal all-fail — cause-aware message (auth handled above) */}
        {renderFailure && !authFailure && (
          <p className="rounded border border-danger/40 bg-danger-soft px-2 py-1.5 text-[11px] text-danger">
            {renderFailure.failures.some((f) => looksLikeQuota(f.error_class, f.message))
              ? 'Insufficient Higgsfield credits.'
              : renderFailure.message}
          </p>
        )}

        {/* partial — reel produced, some scenes skipped: compact chips */}
        {!renderFailure && skippedScenes.length > 0 && (
          <div className="space-y-1">
            <p className="label-section">Scenes skipped</p>
            <div className="flex flex-wrap gap-1.5">
              {skippedScenes.map((f, i) => (
                <span
                  key={`${f.scene_index}-${i}`}
                  title={f.message || undefined}
                  className="inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning-soft px-2 py-0.5 text-[10.5px] text-warning"
                >
                  {f.scene_index >= 0 ? `Scene ${f.scene_index + 1}` : 'Scene'}
                  <span className="font-mono text-[9.5px] opacity-80">{f.error_class}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* composer */}
      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (draft.trim() && !turnRunning) {
                  onSend(draft.trim());
                  setDraft('');
                }
              }
            }}
            rows={2}
            placeholder="Ask the Director to adjust the storyboard..."
            className="min-w-0 flex-1 resize-none rounded border border-border bg-card px-2 py-1.5 text-[12.5px] text-text outline-none focus:border-strong"
          />
          {turnRunning ? (
            <button
              onClick={onStop}
              title="Stop"
              className="shrink-0 rounded border border-border p-2 text-danger transition-colors hover:bg-danger-soft"
            >
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={() => {
                if (draft.trim()) {
                  onSend(draft.trim());
                  setDraft('');
                }
              }}
              disabled={!draft.trim()}
              title="Send"
              className="shrink-0 rounded border border-strong bg-accent p-2 text-on-accent transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
