/**
 * MarketingPresetsPanel — browse Higgsfield's Marketing Studio hooks.
 *
 * Hooks are pre-engineered ad concepts (Product Hit, Spicy, Interview,
 * Random Object Mic, etc.) shipped by Higgsfield with prompt + preview
 * video. The operator browses the grid, picks one, and the prompt
 * flows into the shared StudioPanel as a preset — much faster than
 * writing prompts from scratch.
 */

import { useState, useEffect } from 'react';
import { Megaphone, Loader2, Play, Pin } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  studioListMarketingHooks,
  type MarketingHook,
} from '@/lib/api';

interface MarketingPresetsPanelProps {
  /** Called when the operator picks a hook. Caller (StudioPage) opens
   * the StudioPanel with the prompt + suggested model preset. */
  onUseHook?: (hook: MarketingHook) => void;
}

export default function MarketingPresetsPanel({ onUseHook }: MarketingPresetsPanelProps) {
  const [hooks, setHooks] = useState<MarketingHook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'stunt' | 'subtle'>('all');

  useEffect(() => {
    setLoading(true);
    studioListMarketingHooks()
      .then((items) => {
        setHooks(items);
        setError(null);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setHooks([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const visible = filter === 'all' ? hooks : hooks.filter((h) => h.type === filter);
  const types = Array.from(new Set(hooks.map((h) => h.type).filter(Boolean))) as string[];

  return (
    <section className="border border-border rounded-md p-3 flex flex-col gap-2 bg-card">
      <div className="flex items-center gap-2 flex-wrap">
        <Megaphone className="h-3.5 w-3.5 text-primary" />
        <span className="text-[10px] uppercase font-mono text-muted-foreground">Higgsfield</span>
        <span className="text-xs font-medium">Marketing Studio presets</span>
        <span className="text-[10px] text-muted-foreground italic">
          Pre-engineered ad concepts · pick one to skip the prompt-writing
        </span>
        <div className="ml-auto inline-flex rounded border border-border text-[10px] font-mono">
          {(['all', ...types] as const).map((t) => (
            <button
              key={t}
              onClick={() => setFilter(t as typeof filter)}
              className={cn(
                'px-2 py-0.5 capitalize transition-colors',
                filter === t
                  ? 'bg-accent-soft text-accent'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {t} {t !== 'all' && `(${hooks.filter((h) => h.type === t).length})`}
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="text-xs text-muted-foreground py-2 flex items-center gap-2">
          <Loader2 className="h-3 w-3 animate-spin" /> Loading presets…
        </div>
      )}

      {error && (
        <div className="text-[11px] text-danger py-2">
          {error}
        </div>
      )}

      {!loading && !error && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          {visible.map((h) => (
            <HookTile key={h.id} hook={h} onUse={onUseHook} />
          ))}
          {visible.length === 0 && (
            <div className="col-span-full text-xs text-muted-foreground py-2">
              No presets in this category yet.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function HookTile({ hook, onUse }: { hook: MarketingHook; onUse?: (hook: MarketingHook) => void }) {
  const [hovering, setHovering] = useState(false);

  return (
    <div
      className="border border-border rounded-md overflow-hidden bg-secondary/20 hover:border-primary/40 hover:shadow-sm transition-all flex flex-col group"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <div className="aspect-video bg-secondary/40 relative overflow-hidden">
        {hovering && hook.video_url ? (
          <video
            src={hook.video_url}
            className="w-full h-full object-cover"
            autoPlay
            muted
            loop
            playsInline
          />
        ) : hook.thumbnail_url ? (
          <img
            src={hook.thumbnail_url}
            alt={hook.name}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <Play className="h-6 w-6 opacity-30" />
          </div>
        )}
        {hook.is_pinned && (
          <div className="absolute top-1 right-1 bg-warning-soft text-warning rounded-full p-0.5" title="Pinned by Higgsfield">
            <Pin className="h-3 w-3" />
          </div>
        )}
      </div>
      <div className="p-2 flex flex-col gap-1 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-semibold truncate" title={hook.name}>{hook.name}</span>
          {hook.type && (
            <span className="text-[9px] font-mono uppercase text-muted-foreground bg-secondary/50 rounded px-1">
              {hook.type}
            </span>
          )}
        </div>
        <p
          className="text-[10px] text-muted-foreground line-clamp-2"
          title={hook.prompt}
        >
          {hook.prompt}
        </p>
        <Button
          size="sm"
          variant="outline"
          className="mt-1 h-6 text-[10px]"
          onClick={() => onUse?.(hook)}
        >
          Use this prompt →
        </Button>
      </div>
    </div>
  );
}
