import { useState, useEffect, type ComponentPropsWithoutRef } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronRight, ChevronDown, Check, Loader2, Trash2, Terminal, CalendarPlus } from 'lucide-react';
import { cn } from '@/lib/utils';
import ToolCallBlock from './ToolCallBlock';
import AgentAvatar from './AgentAvatar';
import OrchestrationLedger from './OrchestrationLedger';
import { getAgentProfile } from '@/lib/agentProfiles';
import { getToolDescription } from '@/lib/toolDescriptions';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { extractPlan, fetchTurnEvents } from '@/lib/api';
import { setPendingScheduleDraft } from '@/components/plans/planHelpers';
import type { PlanFormDraft } from '@/components/plans/PlanForm';
import type { ChatMessage as ChatMessageType, ToolCall } from '@/types';
import type { OrchestrationEvent } from '@/types/orchestration';

/** Markdown component map shared by every render path so links open safely
 *  and there's no layout shift between streaming and persisted bubbles. */
const mdComponents: Components = {
  a: ({ node: _node, ...props }: ComponentPropsWithoutRef<'a'> & { node?: unknown }) => (
    <a {...props} target="_blank" rel="noreferrer" />
  ),
};

interface ChatMessageProps {
  message: ChatMessageType;
  onDelete?: (messageId: string) => void;
  /** True when this is the active assistant turn currently streaming tokens.
   *  Renders a gentle `.studio-caret` after the prose. */
  isStreaming?: boolean;
  /** Conversation this message belongs to. Required for the "Send to
   *  Claude Code" action — when set, an extra hover button appears on
   *  assistant messages that flips `awaits_claude_code=1` on the
   *  conversation so Claude Code (the user's terminal session) sees
   *  the handoff via MCP. */
  conversationId?: string;
  /** v2 orchestration (story 3.2). Live-accumulated turn events for THIS
   *  message's turn, supplied by ChatPanel while the turn streams. When absent
   *  but `message.turnId` is set (history replay), the ledger lazily fetches
   *  `/turns/{id}/events`. */
  turnEvents?: OrchestrationEvent[];
  /** Terminal flag for the live turn — feeds the ledger's collapsed summary. */
  turnComplete?: boolean;
  /** Per-specialist stop (story 3.4). Present only for a LIVE turn; undefined in
   *  history replay so per-row stop buttons hide (the ledger handles undefined). */
  onStopCall?: (callId: string) => void;
}

/** Internal tools the user doesn't care about (chain-of-thought noise) */
const INTERNAL_TOOLS = new Set(['ToolSearch', 'Read', 'Glob', 'Grep', 'Write', 'Edit', 'Bash', 'Agent', 'Task', 'TodoWrite']);

function isActionTool(tc: ToolCall) {
  return !INTERNAL_TOOLS.has(tc.name);
}

function ToolCallsSummary({ toolCalls }: { toolCalls: ToolCall[] }) {
  const [showAll, setShowAll] = useState(false);

  const actions = toolCalls.filter(isActionTool);
  const internal = toolCalls.filter((tc) => !isActionTool(tc));

  const allDone = toolCalls.every((tc) => tc.status !== 'pending');
  const hasError = toolCalls.some((tc) => tc.status === 'error');
  const pendingCount = toolCalls.filter((tc) => tc.status === 'pending').length;

  // Quiet state dot (pending pulse / error / done) — no boxed glyphs.
  const stateDot = !allDone ? (
    <span className="studio-pulse h-2 w-2 shrink-0 rounded-full bg-subtle" aria-label="running" />
  ) : hasError ? (
    <span className="h-2 w-2 shrink-0 rounded-full bg-danger" aria-label="error" />
  ) : (
    <span className="h-2 w-2 shrink-0 rounded-full bg-success" aria-label="done" />
  );

  const statusText = !allDone
    ? `${pendingCount} running`
    : hasError
      ? 'error'
      : 'done';

  // Summary label
  const actionNames = actions.map((a) => a.name);
  const uniqueActions = [...new Set(actionNames)];
  const summaryText =
    actions.length === 0
      ? `${internal.length} internal operation${internal.length !== 1 ? 's' : ''}`
      : uniqueActions.length <= 3
        ? uniqueActions.join(', ')
        : `${uniqueActions.slice(0, 2).join(', ')} +${uniqueActions.length - 2} more`;

  return (
    <div className="mt-2 text-xs">
      {/* Quiet collapsible summary row — a dot, a count, the calm summary. */}
      <button
        onClick={() => setShowAll(!showAll)}
        className="group -mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-2 transition-colors duration-150"
      >
        {stateDot}
        <span className="text-muted-foreground truncate">
          {actions.length > 0 && (
            <span className="font-medium text-text">{actions.length} tool{actions.length !== 1 ? 's' : ''}</span>
          )}
          {actions.length > 0 && internal.length > 0 && ' · '}
          {internal.length > 0 && <span>{internal.length} internal</span>}
          <span className="ml-1.5 text-subtle">— {summaryText}</span>
        </span>
        <span className={cn('ml-auto shrink-0', hasError && allDone ? 'text-danger' : 'text-muted-foreground')}>
          {statusText}
        </span>
        <span className="shrink-0 text-[10px] text-subtle transition-transform duration-150 group-hover:text-muted">
          {showAll ? '▾' : '▸'}
        </span>
      </button>

      {/* Expanded: action tools inline, internal tools nested */}
      {showAll && (
        <div className="mt-1 ml-3 border-l border-border pl-3">
          {actions.length > 0 && (
            <div className="space-y-0.5 py-1">
              {actions.map((tc) => (
                <ToolCallBlock key={tc.id} toolCall={tc} />
              ))}
            </div>
          )}
          {internal.length > 0 && <InternalToolsGroup tools={internal} />}
        </div>
      )}
    </div>
  );
}

function InternalToolsGroup({ tools }: { tools: ToolCall[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-0.5 border-t border-border pt-0.5">
      <button
        onClick={() => setExpanded(!expanded)}
        className="-mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1 text-[10px] text-muted-foreground hover:bg-surface-2 transition-colors"
      >
        {expanded ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
        <span>{tools.length} internal operation{tools.length !== 1 ? 's' : ''} (ToolSearch, etc.)</span>
      </button>
      {expanded && (
        <div className="pb-1 space-y-0.5">
          {tools.map((tc) => (
            <ToolCallBlock key={tc.id} toolCall={tc} compact />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatMessage({ message, onDelete, conversationId, isStreaming, turnEvents, turnComplete, onStopCall }: ChatMessageProps) {
  const [handoffState, setHandoffState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [scheduleState, setScheduleState] = useState<'idle' | 'loading' | 'error'>('idle');
  const accountId = useClientAccountId();
  const { selectedCampaignId } = useAppStore();

  // v2 orchestration ledger (story 3.2). A bubble carrying a `turnId` renders
  // the OrchestrationLedger. Live turns get their events from ChatPanel via
  // `turnEvents`; a persisted history bubble (turnId set, no live events)
  // lazily fetches the replay from `/turns/{id}/events`.
  const hasLiveEvents = !!turnEvents && turnEvents.length > 0;
  const [replayEvents, setReplayEvents] = useState<OrchestrationEvent[] | null>(null);
  useEffect(() => {
    if (!message.turnId || hasLiveEvents || !conversationId) return;
    let cancelled = false;
    fetchTurnEvents(conversationId, message.turnId)
      .then((evs) => { if (!cancelled) setReplayEvents(evs); })
      .catch(() => { if (!cancelled) setReplayEvents([]); });
    return () => { cancelled = true; };
  }, [message.turnId, conversationId, hasLiveEvents]);

  const ledgerEvents = hasLiveEvents ? turnEvents! : (replayEvents ?? []);
  // Live turns pass an explicit complete flag; a history-replayed turn is always
  // terminal (it's persisted). onStopCall is undefined on history replay, so the
  // ledger hides per-row stops there (its contract).
  const ledgerComplete = hasLiveEvents ? !!turnComplete : true;
  const showLedger = !!message.turnId && ledgerEvents.length > 0;

  // "Schedule this" — ask the backend to draft a plan from this message, then
  // hand the draft to PlansPanel's inline form via a window event. The campaign
  // view picks it up and opens its Plans tab prefilled. No big modal.
  const scheduleThis = async () => {
    if (scheduleState === 'loading') return;
    setScheduleState('loading');
    try {
      const d = await extractPlan({
        account_id: accountId,
        campaign_id: selectedCampaignId ?? undefined,
        text: message.content,
      });
      const draft: PlanFormDraft = {
        title: d.title,
        action_detail: d.action_detail,
        action_category: d.action_category,
        mode: d.mode,
        suggested_run_at: d.suggested_run_at,
        recurrence: d.recurrence,
        context_snippet: message.content,
        conversation_id: conversationId ?? null,
      };
      setPendingScheduleDraft(draft);                 // claimed by PlansPanel on mount
      window.dispatchEvent(new CustomEvent('plans:open-tab'));
      window.dispatchEvent(new CustomEvent<PlanFormDraft>('plans:schedule', { detail: draft }));
      setScheduleState('idle');
    } catch (e) {
      console.error('schedule extract failed', e);
      setScheduleState('error');
      setTimeout(() => setScheduleState('idle'), 4000);
    }
  };

  const sendToClaudeCode = async () => {
    if (!conversationId || handoffState === 'sending') return;
    setHandoffState('sending');
    const note = window.prompt('Optional note for Claude Code (what should it do with this thread?):') ?? undefined;
    try {
      const res = await fetch(`/api/conversations/${conversationId}/handoff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(note ? { note } : {}),
      });
      if (!res.ok) throw new Error(await res.text());
      setHandoffState('sent');
      setTimeout(() => setHandoffState('idle'), 4000);
    } catch (e) {
      console.error('handoff failed', e);
      setHandoffState('error');
      setTimeout(() => setHandoffState('idle'), 4000);
    }
  };
  const isUser = message.role === 'user';
  const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;
  const roleName = message.agentRoleName;
  const roleId = message.agentRole;
  const [showActions, setShowActions] = useState(false);

  // ----- Shared body (prose + video + tool rows) ------------------------------
  const body = (
    <>
      {isUser ? (
        <div className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</div>
      ) : (
        <div>
          {/* v2 orchestration ledger — sits ABOVE the Director prose (§6.1). Only
              on turns that carry a turnId AND have events; direct-mode turns
              render exactly as before (no ledger, no layout shift). */}
          {showLedger && (
            <OrchestrationLedger
              events={ledgerEvents}
              isComplete={ledgerComplete}
              onStopCall={onStopCall}
            />
          )}
          <TeamOrRegularContent content={message.content} />
          {isStreaming && <span className="studio-caret ml-0.5 align-baseline">▍</span>}
        </div>
      )}

      {/* Inline rendered video ad */}
      {message.videoUrl && (
        <div className="mt-2 rounded-[12px] overflow-hidden border border-border bg-black">
          <video
            src={message.videoUrl}
            poster={message.videoThumbnail}
            controls
            preload="metadata"
            className="w-full max-h-[360px] bg-black"
          />
          <div className="flex items-center justify-between px-2 py-1 bg-surface-2 text-[10px]">
            <span className="text-muted-foreground">Video ad</span>
            <a href={message.videoUrl} download className="text-accent hover:text-accent-hover">
              Download MP4
            </a>
          </div>
        </div>
      )}

      {/* Live activity — a quiet pulsing line for what's happening RIGHT NOW. */}
      {hasToolCalls && message.toolCalls!.some((tc) => tc.status === 'pending') && (() => {
        const toolCalls = message.toolCalls!;
        const pending = toolCalls.filter((tc) => tc.status === 'pending');
        const latestPending = pending[pending.length - 1];
        if (!latestPending) return null;
        return (
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="studio-pulse h-2 w-2 shrink-0 rounded-full bg-accent" aria-hidden="true" />
            <span className="font-medium text-text truncate">{getToolDescription(latestPending.name)}</span>
            <span className="text-subtle">— {pending.length} running</span>
          </div>
        );
      })()}
      {hasToolCalls && <ToolCallsSummary toolCalls={message.toolCalls!} />}
    </>
  );

  return (
    <div
      className={cn('px-3 py-2 group relative', isUser ? 'flex justify-end' : '')}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {/* Delete button — appears on hover */}
      {showActions && onDelete && (
        <button
          onClick={() => onDelete(message.id)}
          className={cn(
            'absolute top-2 z-10 p-1 rounded-md bg-surface-3 text-muted-foreground hover:bg-danger-soft hover:text-danger transition-colors',
            isUser ? 'left-2' : 'right-2'
          )}
          title="Delete message"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      )}

      {/* "Schedule this" — assistant messages only. Drafts a plan from the turn. */}
      {showActions && !isUser && (
        <button
          onClick={scheduleThis}
          disabled={scheduleState === 'loading'}
          className={cn(
            'absolute top-2 z-10 flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] font-medium transition-colors',
            conversationId ? 'right-[9rem]' : 'right-2',
            scheduleState === 'error'
              ? 'bg-danger-soft text-danger'
              : 'bg-surface-3 text-muted-foreground hover:bg-accent-soft hover:text-accent'
          )}
          title="Draft a scheduled plan from this message"
        >
          {scheduleState === 'loading' ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <CalendarPlus className="h-3 w-3" />
          )}
          {scheduleState === 'error' ? 'Failed' : 'Schedule'}
        </button>
      )}

      {/* "Send to Claude Code" button — assistant messages only, requires conversationId */}
      {showActions && !isUser && conversationId && (
        <button
          onClick={sendToClaudeCode}
          disabled={handoffState === 'sending'}
          className={cn(
            'absolute top-2 z-10 flex items-center gap-1 px-1.5 py-1 rounded-md text-[10px] font-medium transition-colors',
            'right-10',  // sits left of the delete button (right-2)
            handoffState === 'sent'
              ? 'bg-success-soft text-success'
              : handoffState === 'error'
                ? 'bg-danger-soft text-danger'
                : 'bg-surface-3 text-muted-foreground hover:bg-accent-soft hover:text-accent'
          )}
          title="Hand this thread off to Wassim's Claude Code session for execution"
        >
          {handoffState === 'sending' ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : handoffState === 'sent' ? (
            <Check className="h-3 w-3" />
          ) : (
            <Terminal className="h-3 w-3" />
          )}
          {handoffState === 'sent' ? 'Sent' : handoffState === 'error' ? 'Failed' : 'Claude Code'}
        </button>
      )}

      {isUser ? (
        /* User turn — compact accent-soft bubble, right-aligned. */
        <div
          className={cn(
            'max-w-[82%] rounded-[10px] bg-accent-soft px-4 py-2.5 text-text',
            message.isPending && 'opacity-60'
          )}
        >
          {message.isPending && (
            <span className="text-[10px] font-medium text-muted-foreground block mb-1">Queued</span>
          )}
          {body}
        </div>
      ) : (
        /* Assistant turn — avatar lane + hairline left gutter, no card. */
        <div className="flex gap-3">
          <AgentAvatar roleId={roleId} size="sm" showStatus isWorking={message.isPending} />
          <div className="min-w-0 flex-1 space-y-2 border-l border-border pl-4">
            <div className="flex items-center gap-1.5 -mt-0.5">
              <span className="text-xs font-semibold text-text">
                {getAgentProfile(roleId).name}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {roleName || getAgentProfile(roleId).title}
              </span>
              {message.createdAt && (
                <span className="text-[9px] text-subtle ml-auto">
                  {formatRelativeTime(message.createdAt)}
                </span>
              )}
            </div>
            {body}
          </div>
        </div>
      )}
    </div>
  );
}


function TeamOrRegularContent({ content }: { content: string }) {
  // Check if this is a team session response with ---ROLE: markers
  const rolePattern = /---ROLE:\s*(\w+)---\n([\s\S]*?)(?=---END ROLE---|---ROLE:|$)/g;
  const matches = [...content.matchAll(rolePattern)];

  if (matches.length >= 2) {
    // Team session — render each role as a separate card
    // Extract any content before the first role marker (preamble)
    const firstMarkerIdx = content.indexOf('---ROLE:');
    const preamble = firstMarkerIdx > 0 ? content.slice(0, firstMarkerIdx).trim() : '';
    // Extract any content after the last ---END ROLE--- (consensus)
    const lastEndIdx = content.lastIndexOf('---END ROLE---');
    const epilogue = lastEndIdx > 0 ? content.slice(lastEndIdx + 14).trim() : '';

    return (
      <div className="space-y-3">
        {preamble && (
          <div className="studio-prose break-words">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{preamble}</ReactMarkdown>
          </div>
        )}
        {matches.map((match, i) => {
          const roleId = match[1].trim();
          const roleContent = match[2].replace(/---END ROLE---/g, '').trim();
          return (
            /* Each specialist as an avatar-lane + hairline gutter, like the
               main assistant turn — quiet identity, no filled card. */
            <div key={i} className="flex gap-3">
              <AgentAvatar roleId={roleId} size="sm" />
              <div className="min-w-0 flex-1 border-l border-border pl-4">
                <div className="flex items-center gap-1.5 mb-1.5 -mt-0.5">
                  <span className="text-xs font-semibold text-text">{getAgentProfile(roleId).name}</span>
                  <span className="text-[10px] text-muted-foreground">{getAgentProfile(roleId).title}</span>
                </div>
                <div className="studio-prose break-words">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{roleContent}</ReactMarkdown>
                </div>
              </div>
            </div>
          );
        })}
        {epilogue && (
          <div className="flex gap-3 border-t border-border pt-3 mt-1">
            <AgentAvatar roleId="director" size="sm" />
            <div className="min-w-0 flex-1 border-l border-border pl-4">
              <div className="flex items-center gap-1.5 mb-1.5 -mt-0.5">
                <span className="text-xs font-semibold text-text">{getAgentProfile('director').name}</span>
                <span className="text-[10px] text-muted-foreground">Consensus</span>
              </div>
              <div className="studio-prose break-words">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{epilogue}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Regular message — render as markdown
  return (
    <div className="studio-prose break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>{content}</ReactMarkdown>
    </div>
  );
}

function formatRelativeTime(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    return `${diffDays}d ago`;
  } catch {
    return '';
  }
}
