import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronRight, ChevronDown, Wrench, Check, X, Loader2, Trash2, Terminal } from 'lucide-react';
import { cn } from '@/lib/utils';
import ToolCallBlock from './ToolCallBlock';
import AgentAvatar from './AgentAvatar';
import { getAgentProfile } from '@/lib/agentProfiles';
import { getToolDescription, getSourceIcon } from '@/lib/toolDescriptions';
import type { ChatMessage as ChatMessageType, ToolCall } from '@/types';

interface ChatMessageProps {
  message: ChatMessageType;
  onDelete?: (messageId: string) => void;
  /** Conversation this message belongs to. Required for the "Send to
   *  Claude Code" action — when set, an extra hover button appears on
   *  assistant messages that flips `awaits_claude_code=1` on the
   *  conversation so Claude Code (the user's terminal session) sees
   *  the handoff via MCP. */
  conversationId?: string;
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

  // Status indicator
  const statusEl = !allDone ? (
    <span className="flex items-center gap-1 text-muted-foreground">
      <Loader2 className="h-3 w-3 animate-spin" />
      <span>{pendingCount} running</span>
    </span>
  ) : hasError ? (
    <span className="flex items-center gap-1 text-destructive">
      <X className="h-3 w-3" />
      <span>error</span>
    </span>
  ) : (
    <span className="flex items-center gap-1 text-status-enabled">
      <Check className="h-3 w-3" />
      <span>done</span>
    </span>
  );

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
    <div className="mt-2 border border-border/60 rounded-md text-xs overflow-hidden">
      {/* Compact summary bar */}
      <button
        onClick={() => setShowAll(!showAll)}
        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-secondary/40 transition-colors"
      >
        {showAll ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
        )}
        <Wrench className="h-3 w-3 text-muted-foreground shrink-0" />
        <span className="text-muted-foreground truncate">
          {actions.length > 0 && (
            <span className="font-medium text-foreground">{actions.length} tool{actions.length !== 1 ? 's' : ''}</span>
          )}
          {actions.length > 0 && internal.length > 0 && ' · '}
          {internal.length > 0 && (
            <span>{internal.length} internal</span>
          )}
          <span className="ml-1.5 text-muted-foreground/70">— {summaryText}</span>
        </span>
        <span className="ml-auto shrink-0">{statusEl}</span>
      </button>

      {/* Expanded: show action tools inline, internal tools nested */}
      {showAll && (
        <div className="border-t border-border/40">
          {/* Action tools (MCP calls, API calls) — always shown when expanded */}
          {actions.length > 0 && (
            <div className="px-1 py-1 space-y-0.5">
              {actions.map((tc) => (
                <ToolCallBlock key={tc.id} toolCall={tc} />
              ))}
            </div>
          )}

          {/* Internal tools (ToolSearch, Read, etc.) — extra nested */}
          {internal.length > 0 && (
            <InternalToolsGroup tools={internal} />
          )}
        </div>
      )}
    </div>
  );
}

function InternalToolsGroup({ tools }: { tools: ToolCall[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-t border-border/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-1 text-[10px] text-muted-foreground hover:bg-secondary/30 transition-colors"
      >
        {expanded ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
        <span>{tools.length} internal operation{tools.length !== 1 ? 's' : ''} (ToolSearch, etc.)</span>
      </button>
      {expanded && (
        <div className="px-1 pb-1 space-y-0.5">
          {tools.map((tc) => (
            <ToolCallBlock key={tc.id} toolCall={tc} compact />
          ))}
        </div>
      )}
    </div>
  );
}

const ROLE_ICONS: Record<string, string> = {
  briefcase: '💼', target: '🎯', search: '🔍', palette: '🎨',
  chart: '📊', eye: '👁️', code: '💻', rocket: '🚀',
};

const ROLE_COLORS: Record<string, string> = {
  director: 'bg-gray-500/20 text-gray-700 dark:text-gray-200 border border-gray-400/30',
  ppc_strategist: 'bg-orange-500/20 text-orange-700 dark:text-orange-300 border border-orange-400/30',
  search_term_hunter: 'bg-blue-500/20 text-blue-700 dark:text-blue-300 border border-blue-400/30',
  creative_director: 'bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-400/30',
  analytics_analyst: 'bg-green-500/20 text-green-700 dark:text-green-300 border border-green-400/30',
  competitor_intel: 'bg-red-500/20 text-red-700 dark:text-red-300 border border-red-400/30',
  gtm_specialist: 'bg-cyan-500/20 text-cyan-700 dark:text-cyan-300 border border-cyan-400/30',
  growth_hacker: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-300 border border-yellow-400/30',
};

export default function ChatMessage({ message, onDelete, conversationId }: ChatMessageProps) {
  const [handoffState, setHandoffState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

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
  const roleAvatar = message.agentRoleAvatar;
  const [showActions, setShowActions] = useState(false);

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
            'absolute top-2 z-10 p-1 rounded-md bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors',
            isUser ? 'left-2' : 'right-2'
          )}
          title="Delete message"
        >
          <Trash2 className="h-3 w-3" />
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
              ? 'bg-emerald-500/15 text-emerald-600'
              : handoffState === 'error'
                ? 'bg-destructive/10 text-destructive'
                : 'bg-blue-500/10 text-blue-600 hover:bg-blue-500/20'
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
      <div
        className={cn(
          'rounded-lg px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'max-w-[85%] bg-primary text-primary-foreground'
            : 'w-full bg-secondary/40 text-foreground',
          message.isPending && 'opacity-60 animate-pulse'
        )}
      >
        {/* Queued badge for pending messages */}
        {message.isPending && isUser && (
          <span className="text-[10px] font-medium opacity-70 block mb-1">Queued</span>
        )}
        {/* Agent identity header for assistant messages */}
        {!isUser && (
          <div className="flex items-center gap-2 mb-2.5 -mt-0.5">
            <AgentAvatar roleId={roleId} size="sm" showStatus isWorking={message.isPending} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold" style={{ color: getAgentProfile(roleId).color }}>
                  {getAgentProfile(roleId).name}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {roleName || getAgentProfile(roleId).title}
                </span>
              </div>
              {message.createdAt && (
                <span className="text-[9px] text-muted-foreground/60">
                  {formatRelativeTime(message.createdAt)}
                </span>
              )}
            </div>
          </div>
        )}

        {isUser ? (
          <div className="whitespace-pre-wrap">{message.content}</div>
        ) : (
          <TeamOrRegularContent content={message.content} />
        )}

        {/* Inline rendered video ad */}
        {message.videoUrl && (
          <div className="mt-2 rounded-lg overflow-hidden border border-border bg-black">
            <video
              src={message.videoUrl}
              poster={message.videoThumbnail}
              controls
              preload="metadata"
              className="w-full max-h-[360px] bg-black"
            />
            <div className="flex items-center justify-between px-2 py-1 bg-secondary/30 text-[10px]">
              <span className="text-muted-foreground">Video ad</span>
              <a href={message.videoUrl} download className="text-pink-400 hover:text-pink-300">
                Download MP4
              </a>
            </div>
          </div>
        )}

        {/* Live activity — show what's happening RIGHT NOW */}
        {hasToolCalls && message.toolCalls!.some(tc => tc.status === 'pending') && (() => {
          const toolCalls = message.toolCalls!;
          const pending = toolCalls.filter(tc => tc.status === 'pending');
          const completed = toolCalls.filter(tc => tc.status !== 'pending');
          const latestPending = pending[pending.length - 1];
          return (
            <div className="mt-2 bg-primary/5 border border-primary/20 rounded-lg p-2.5 space-y-1">
              {latestPending && (
                <div className="flex items-center gap-2 text-xs font-medium">
                  <Loader2 className="h-3 w-3 animate-spin text-primary" />
                  <span>{getToolDescription(latestPending.name)}</span>
                </div>
              )}
              <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>{getSourceIcon(latestPending?.source || '')} {latestPending?.source || 'agent'}</span>
                <span>✅ {completed.length} done</span>
                <span>⏳ {pending.length} running</span>
              </div>
            </div>
          );
        })()}
        {hasToolCalls && <ToolCallsSummary toolCalls={message.toolCalls!} />}
      </div>
    </div>
  );
}

const PROSE_CLASSES = `prose prose-sm prose-invert max-w-none
  [&_h1]:text-base [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2
  [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mt-4 [&_h2]:mb-2
  [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1
  [&_h4]:text-xs [&_h4]:font-semibold [&_h4]:mt-3 [&_h4]:mb-1 [&_h4]:text-muted-foreground
  [&_p]:my-1.5 [&_p]:text-sm
  [&_ul]:my-1.5 [&_ul]:pl-4 [&_ul]:text-sm
  [&_ol]:my-1.5 [&_ol]:pl-4 [&_ol]:text-sm
  [&_li]:my-0.5
  [&_strong]:text-foreground [&_strong]:font-semibold
  [&_hr]:my-3 [&_hr]:border-border
  [&_table]:text-xs [&_table]:w-full [&_table]:my-2
  [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-medium [&_th]:border-b [&_th]:border-border [&_th]:text-muted-foreground
  [&_td]:px-2 [&_td]:py-1 [&_td]:border-b [&_td]:border-border/50
  [&_code]:text-xs [&_code]:bg-background/50 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
  [&_pre]:bg-background/50 [&_pre]:rounded-md [&_pre]:p-3 [&_pre]:my-2 [&_pre]:overflow-x-auto
  [&_blockquote]:border-l-2 [&_blockquote]:border-primary/50 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground`;

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
          <div className={PROSE_CLASSES}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{preamble}</ReactMarkdown>
          </div>
        )}
        {matches.map((match, i) => {
          const roleId = match[1].trim();
          const roleContent = match[2].replace(/---END ROLE---/g, '').trim();
          const profile = getAgentProfile(roleId);
          return (
            <div
              key={i}
              className="border rounded-xl p-3 transition-colors"
              style={{ borderColor: profile.borderColor + '40', backgroundColor: profile.bgColor + '10' }}
            >
              <div className="flex items-center gap-2 mb-2">
                <AgentAvatar roleId={roleId} size="sm" />
                <span className="text-xs font-semibold" style={{ color: profile.color }}>
                  {profile.name}
                </span>
                <span className="text-[10px] text-muted-foreground">{profile.title}</span>
              </div>
              <div className={PROSE_CLASSES}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{roleContent}</ReactMarkdown>
              </div>
            </div>
          );
        })}
        {epilogue && (
          <div className="border-t border-border pt-3 mt-3">
            <div className="flex items-center gap-2 mb-2">
              <AgentAvatar roleId="director" size="sm" />
              <span className="text-xs font-semibold" style={{ color: getAgentProfile('director').color }}>
                {getAgentProfile('director').name}
              </span>
              <span className="text-[10px] text-muted-foreground">Consensus</span>
            </div>
            <div className={PROSE_CLASSES}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{epilogue}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Regular message — render as markdown
  return (
    <div className={PROSE_CLASSES}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
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
