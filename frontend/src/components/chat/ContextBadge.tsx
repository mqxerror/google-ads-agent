import { useState } from 'react';
import { Megaphone, FileText, Brain, ChevronDown, Archive } from 'lucide-react';
import { cn } from '@/lib/utils';

interface LayerInfo {
  name: string;
  tokens: number;
  priority: number;
  truncated: boolean;
  dropped: boolean;
}

interface CompactionInfo {
  should_warn: boolean;
  should_compact: boolean;
  usage_ratio: number;
  checkpoint_count: number;
  last_checkpoint_summary: string | null;
}

export interface ContextMetaData {
  total_tokens: number;
  budget: number;
  usage_percent: number;
  usage_ratio: number;
  layers: LayerInfo[];
  warnings: string[];
  dropped: string[];
  compaction?: CompactionInfo;
}

interface ContextBadgeProps {
  campaignName: string | null;
  guidelinesLoaded: boolean;
  contextMeta?: ContextMetaData | null;
}

export default function ContextBadge({ campaignName, guidelinesLoaded, contextMeta }: ContextBadgeProps) {
  const [showDetails, setShowDetails] = useState(false);

  const usagePercent = contextMeta?.usage_percent ?? 0;
  const hasCompacted = (contextMeta?.compaction?.checkpoint_count ?? 0) > 0;

  // Color based on usage
  const barColor = usagePercent >= 85
    ? 'bg-danger'
    : usagePercent >= 70
      ? 'bg-warning'
      : 'bg-success';

  const barBg = usagePercent >= 85
    ? 'bg-danger-soft'
    : usagePercent >= 70
      ? 'bg-warning-soft'
      : 'bg-surface-3';

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs flex-wrap">
      {campaignName && (
        <span className="inline-flex items-center gap-1 bg-surface-3 rounded-full px-2.5 py-0.5 text-text">
          <Megaphone className="h-3 w-3" />
          {campaignName}
        </span>
      )}
      {guidelinesLoaded && (
        <span className="inline-flex items-center gap-1 bg-surface-3 rounded-full px-2.5 py-0.5 text-text">
          <span className="w-1.5 h-1.5 rounded-full bg-success" />
          <FileText className="h-3 w-3" />
          Guidelines
        </span>
      )}

      {/* Token usage indicator */}
      {contextMeta && contextMeta.total_tokens > 0 && (
        <div className="relative">
          <button
            onClick={() => setShowDetails(!showDetails)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 transition-colors',
              barBg,
              usagePercent >= 85 ? 'text-danger' :
              usagePercent >= 70 ? 'text-warning' :
              'text-text'
            )}
          >
            <Brain className="h-3 w-3" />
            <div className="flex items-center gap-1">
              <div className="w-12 h-1.5 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all duration-500', barColor)}
                  style={{ width: `${Math.min(usagePercent, 100)}%` }}
                />
              </div>
              <span className="tabular-nums">{usagePercent}%</span>
            </div>
            {hasCompacted && (
              <Archive className="h-3 w-3 text-muted-foreground" />
            )}
            <ChevronDown className={cn('h-3 w-3 transition-transform', showDetails && 'rotate-180')} />
          </button>

          {/* Details dropdown */}
          {showDetails && (
            <div
              className="absolute top-full left-0 mt-1 z-[999] w-72 bg-surface border border-border rounded-lg p-3 space-y-2"
              style={{ boxShadow: 'var(--shadow-elevated)' }}
            >
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Context usage</span>
                <span className="font-medium">
                  {formatTokens(contextMeta.total_tokens)} / {formatTokens(contextMeta.budget)}
                </span>
              </div>

              {/* Per-layer breakdown */}
              <div className="space-y-1">
                {contextMeta.layers
                  .filter(l => l.tokens > 0 || l.dropped)
                  .sort((a, b) => b.tokens - a.tokens)
                  .map((layer) => (
                    <div key={layer.name} className="flex items-center gap-2 text-[10px]">
                      <div className="w-20 truncate text-muted-foreground">
                        {formatLayerName(layer.name)}
                      </div>
                      <div className="flex-1 h-1 bg-surface-3 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            layer.dropped ? 'bg-danger' :
                            layer.truncated ? 'bg-warning' :
                            priorityColor(layer.priority),
                          )}
                          style={{ width: `${(layer.tokens / contextMeta.total_tokens) * 100}%` }}
                        />
                      </div>
                      <div className="w-12 text-right tabular-nums text-muted-foreground">
                        {layer.dropped ? (
                          <span className="text-danger">dropped</span>
                        ) : (
                          formatTokens(layer.tokens)
                        )}
                      </div>
                    </div>
                  ))}
              </div>

              {/* Warnings */}
              {contextMeta.warnings.length > 0 && (
                <div className="pt-1 border-t border-border space-y-0.5">
                  {contextMeta.warnings.map((w, i) => (
                    <p key={i} className="text-[10px] text-warning">{w}</p>
                  ))}
                </div>
              )}

              {/* Compaction status */}
              {hasCompacted && (
                <div className="pt-1 border-t border-border">
                  <p className="text-[10px] text-muted-foreground">
                    <Archive className="inline h-3 w-3 mr-1" />
                    {contextMeta.compaction!.checkpoint_count} checkpoint{contextMeta.compaction!.checkpoint_count !== 1 ? 's' : ''} created
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

function formatLayerName(name: string): string {
  return name
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function priorityColor(priority: number): string {
  switch (priority) {
    case 0: return 'bg-accent';
    case 1: return 'bg-success';
    case 2: return 'bg-warning';
    case 3: return 'bg-border-strong';
    default: return 'bg-border-strong';
  }
}
