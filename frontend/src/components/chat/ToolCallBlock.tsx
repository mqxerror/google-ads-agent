import { useState } from 'react';
import { ChevronRight, ChevronDown, Check, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolCall } from '@/types';

interface ToolCallBlockProps {
  toolCall: ToolCall;
}

export default function ToolCallBlock({ toolCall }: ToolCallBlockProps) {
  const [expanded, setExpanded] = useState(false);

  const sourceIcon = toolCall.source === 'google-ads' ? '🔧' : '🌐';
  const sourceColor = toolCall.source === 'google-ads' ? 'text-tool-api' : 'text-tool-browser';

  const statusIcon =
    toolCall.status === 'pending' ? (
      <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
    ) : toolCall.status === 'success' ? (
      <Check className="h-3 w-3 text-status-enabled" />
    ) : (
      <X className="h-3 w-3 text-destructive" />
    );

  return (
    <div className="border border-border rounded-md my-2 text-xs">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-secondary/40 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 text-muted-foreground" />
        )}
        <span>{sourceIcon}</span>
        <span className={cn('font-mono', sourceColor)}>{toolCall.name}</span>
        <span className="ml-auto">{statusIcon}</span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          <div>
            <div className="text-muted-foreground mb-1">Input</div>
            <pre className="bg-secondary/50 rounded-sm p-2 overflow-x-auto font-mono text-[11px]">
              {JSON.stringify(toolCall.input, null, 2)}
            </pre>
          </div>
          {toolCall.output && (
            <div>
              <div className="text-muted-foreground mb-1">Output</div>
              <pre className="bg-secondary/50 rounded-sm p-2 overflow-x-auto font-mono text-[11px]">
                {JSON.stringify(toolCall.output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
