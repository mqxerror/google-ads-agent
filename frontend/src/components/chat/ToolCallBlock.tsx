import { useState } from 'react';
import { ChevronRight, ChevronDown, Check, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolCall } from '@/types';

interface ToolCallBlockProps {
  toolCall: ToolCall;
  compact?: boolean;
}

const SOURCE_CONFIG = {
  'google-ads-mcp': { icon: '🔌', label: 'MCP', color: 'text-green-400' },
  'google-ads': { icon: '🔧', label: 'API', color: 'text-tool-api' },
  chrome: { icon: '🌐', label: 'Browser', color: 'text-tool-browser' },
  gtm: { icon: '🏷️', label: 'GTM', color: 'text-orange-400' },
} as const;

export default function ToolCallBlock({ toolCall, compact }: ToolCallBlockProps) {
  const [expanded, setExpanded] = useState(false);

  const config = SOURCE_CONFIG[toolCall.source] || SOURCE_CONFIG['google-ads'];

  const statusIcon =
    toolCall.status === 'pending' ? (
      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
    ) : toolCall.status === 'success' ? (
      <Check className="h-3 w-3 text-status-enabled" />
    ) : (
      <X className="h-3 w-3 text-destructive" />
    );

  if (compact) {
    return (
      <div className="flex items-center gap-2 px-2 py-0.5 text-[10px] text-muted-foreground">
        <span className="opacity-60">{config.icon}</span>
        <span className="font-mono truncate">{toolCall.name}</span>
        <span className="ml-auto shrink-0">{statusIcon}</span>
      </div>
    );
  }

  return (
    <div className="rounded text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-secondary/40 rounded transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
        )}
        <span>{config.icon}</span>
        <span className={cn('font-mono truncate', config.color)}>{toolCall.name}</span>
        <span className="ml-auto shrink-0">{statusIcon}</span>
      </button>

      {expanded && (
        <div className="px-2 pb-2 space-y-2 ml-5">
          <div>
            <div className="text-muted-foreground mb-1">Input</div>
            <pre className="bg-secondary/50 rounded-sm p-2 overflow-x-auto font-mono text-[11px]">
              {JSON.stringify(toolCall.input, null, 2)}
            </pre>
          </div>
          {toolCall.output && (
            <div>
              <div className="text-muted-foreground mb-1">Output</div>
              <pre className="bg-secondary/50 rounded-sm p-2 overflow-x-auto font-mono text-[11px] max-h-40 overflow-y-auto">
                {JSON.stringify(toolCall.output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
