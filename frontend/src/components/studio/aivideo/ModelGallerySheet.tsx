/**
 * ModelGallerySheet — the [Change] modal for picking the project's video model.
 * Video models come from useModelCatalog('video') (already filtered available),
 * grouped into tier ROWS. Each card shows origin, clip window, strength, cost,
 * and a live clip-math line for the current target length. Selecting closes the
 * sheet and hands the model back to the page, which clamps every scene's
 * duration to the new model's legal set before persisting.
 */

import { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useModelCatalog } from '@/components/video/ModelPicker';
import type { StudioModelInfo } from '@/lib/api';
import { useClipMath } from '@/components/studio/useClipMath';
import { TIER_ORDER, originLine, clipWindowLabel } from './shared';

interface ModelGallerySheetProps {
  open: boolean;
  currentId: string;
  targetSeconds: number;
  onClose: () => void;
  onPick: (model: StudioModelInfo) => void;
}

function ModelCard({
  model,
  selected,
  targetSeconds,
  onPick,
}: {
  model: StudioModelInfo;
  selected: boolean;
  targetSeconds: number;
  onPick: (m: StudioModelInfo) => void;
}) {
  const { maxClip, estClips } = useClipMath(model, targetSeconds);
  const origin = originLine(model);

  return (
    <button
      onClick={() => onPick(model)}
      className={cn(
        'flex flex-col gap-1.5 rounded-lg border bg-card p-3 text-left transition-colors',
        selected ? 'border-strong bg-accent-soft' : 'border-border hover:bg-surface-2',
      )}
    >
      <div className="flex items-center gap-2">
        <span className="min-w-0 truncate text-sm font-medium text-text">{model.label}</span>
        <span className="ml-auto h-2 w-2 shrink-0 rounded-full bg-success" title="available" />
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {model.tier}
        </span>
        {origin && <span className="text-[10px] text-subtle">{origin}</span>}
      </div>
      <p className="font-mono text-[11px] text-muted-foreground">{clipWindowLabel(model)}</p>
      {model.strengths && (
        <p className="text-[11px] text-subtle">Strength: {model.strengths}</p>
      )}
      <p className="font-mono text-[11px] text-muted-foreground">{model.cost_text}</p>
      {maxClip && (
        <p className="font-mono text-[11px] text-accent">
          {targetSeconds}s target - {estClips} clips of {maxClip}s
        </p>
      )}
    </button>
  );
}

export default function ModelGallerySheet({
  open,
  currentId,
  targetSeconds,
  onClose,
  onPick,
}: ModelGallerySheetProps) {
  const { models, error } = useModelCatalog('video');

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const tiers = [...new Set(models.map((m) => m.tier))].sort(
    (a, b) => (TIER_ORDER[a] ?? 9) - (TIER_ORDER[b] ?? 9),
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/20 p-6"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="mx-auto mt-10 w-full max-w-[880px] rounded-lg border border-border bg-card p-5"
        style={{ boxShadow: 'var(--shadow-elevated)' }}
      >
        <div className="mb-4 flex items-center gap-2">
          <h2 className="text-sm font-semibold text-text">Choose a video model</h2>
          <button
            onClick={onClose}
            title="Close"
            className="ml-auto rounded p-1 text-subtle transition-colors hover:bg-surface-2 hover:text-text"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error ? (
          <p className="py-8 text-center text-xs text-muted-foreground">{error}</p>
        ) : !models.length ? (
          <p className="py-8 text-center text-xs text-muted-foreground">Loading models...</p>
        ) : (
          <div className="space-y-5">
            {tiers.map((tier) => (
              <div key={tier}>
                <p className="label-section mb-2">{tier}</p>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                  {models
                    .filter((m) => m.tier === tier)
                    .sort((a, b) => a.label.localeCompare(b.label))
                    .map((m) => (
                      <ModelCard
                        key={m.id}
                        model={m}
                        selected={m.id === currentId}
                        targetSeconds={targetSeconds}
                        onPick={(picked) => {
                          onPick(picked);
                          onClose();
                        }}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
