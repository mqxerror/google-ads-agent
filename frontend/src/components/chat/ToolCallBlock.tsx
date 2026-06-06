// ToolCallBlock — calm light redesign (DESIGN.md).
//
// A QUIET inline row, not a card: a state dot + source glyph + mono tool name,
// right-aligned status text, expandable to input/output panes on --surface-2.
// Pending = pulsing subtle dot; success = success dot; error = danger dot +
// the name in danger color. Never a green check on a failed result.

import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { ToolCall } from '@/types';

interface ToolCallBlockProps {
  toolCall: ToolCall;
  compact?: boolean;
}

const SOURCE_ICON: Record<string, string> = {
  'google-ads-mcp': '🔌',
  'google-ads': '🔧',
  chrome: '🌐',
  gtm: '🏷️',
};

function iconFor(source: string): string {
  return SOURCE_ICON[source] || '🔧';
}

function StateDot({ status }: { status: ToolCall['status'] }) {
  if (status === 'pending') {
    return (
      <span
        className="studio-pulse h-2 w-2 shrink-0 rounded-full bg-subtle"
        aria-label="pending"
      />
    );
  }
  if (status === 'error') {
    return <span className="h-2 w-2 shrink-0 rounded-full bg-danger" aria-label="error" />;
  }
  return <span className="h-2 w-2 shrink-0 rounded-full bg-success" aria-label="done" />;
}

export default function ToolCallBlock({ toolCall, compact }: ToolCallBlockProps) {
  const [expanded, setExpanded] = useState(false);
  const icon = iconFor(toolCall.source);
  const isError = toolCall.status === 'error';

  if (compact) {
    return (
      <div className="flex items-center gap-2 px-2 py-0.5 text-[10px] text-muted-foreground">
        <StateDot status={toolCall.status} />
        <span className="opacity-60">{icon}</span>
        <span className="font-mono truncate">{toolCall.name}</span>
      </div>
    );
  }

  return (
    <div className="text-[13px]">
      <button
        onClick={() => setExpanded(!expanded)}
        className="group -mx-2 flex w-[calc(100%+1rem)] items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-surface-2 transition-colors duration-150"
      >
        <StateDot status={toolCall.status} />
        <span className="shrink-0 text-[12px] opacity-80">{icon}</span>
        <span
          className={cn(
            'min-w-0 truncate font-mono text-[12.5px]',
            isError ? 'text-danger' : 'text-text',
          )}
        >
          {toolCall.name}
        </span>
        <span className="ml-auto shrink-0 text-[10px] text-subtle transition-transform duration-150 group-hover:text-muted">
          {expanded ? '▾' : '▸'}
        </span>
      </button>

      {expanded && (
        <div className="ml-3 mt-1.5 mb-1 space-y-2.5 border-l border-border pl-3">
          <div>
            <div className="label-section mb-1 text-[10px]">Input</div>
            <pre className="max-h-60 overflow-auto rounded-md border border-border bg-surface-2 p-2 font-mono text-[11.5px] leading-[1.55] text-text">
              {JSON.stringify(toolCall.input, null, 2)}
            </pre>
          </div>
          {toolCall.output && (
            <div>
              <div className="label-section mb-1 text-[10px]">Output</div>
              <pre className="max-h-60 overflow-auto rounded-md border border-border bg-surface-2 p-2 font-mono text-[11.5px] leading-[1.55] text-text">
                {JSON.stringify(toolCall.output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
