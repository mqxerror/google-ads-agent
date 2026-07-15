/**
 * SceneCard — one storyboard scene on the canvas. Editable visual-prompt +
 * VO line, a per-scene model override, a duration chip, a thumbnail slot with
 * three states (empty / rendering skeleton / poster), and a ⋮ menu for
 * move/override/delete. All edits bubble to the canvas via onChange (the
 * canvas debounces the persist). Motion is transform/opacity only.
 */

import { useEffect, useRef, useState } from 'react';
import { MoreVertical, ArrowUp, ArrowDown, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StoryboardScene, StudioModelInfo } from '@/lib/api';

interface SceneCardProps {
  scene: StoryboardScene;
  index: number;
  total: number;
  projectModelId: string;
  catalog: StudioModelInfo[];
  /** true while this scene's clip is rendering — shows the skeleton slot. */
  rendering?: boolean;
  /** finished clip poster/url for this scene, if any. */
  posterUrl?: string | null;
  onChange: (patch: Partial<StoryboardScene>) => void;
  onDelete: () => void;
  onMove: (dir: -1 | 1) => void;
}

export default function SceneCard({
  scene,
  index,
  total,
  projectModelId,
  catalog,
  rendering,
  posterUrl,
  onChange,
  onDelete,
  onMove,
}: SceneCardProps) {
  // Entrance: 6px translate-y + fade, staggered by index (transform/opacity only).
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setMounted(true), 10);
    return () => window.clearTimeout(id);
  }, []);

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menuOpen]);

  const effectiveModel = scene.model ?? projectModelId;

  return (
    <div
      className="rounded-lg border border-border bg-card p-3"
      style={{
        opacity: mounted ? 1 : 0,
        transform: mounted ? 'translateY(0)' : 'translateY(6px)',
        transition: 'opacity 180ms var(--ease-out-quint), transform 180ms var(--ease-out-quint)',
        transitionDelay: `${Math.min(index, 8) * 40}ms`,
        boxShadow: 'var(--shadow-resting)',
      }}
    >
      {/* header */}
      <div className="mb-2 flex items-center gap-2">
        <span className="label-section">Scene {scene.n}</span>
        <span className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[12.5px] text-muted-foreground">
          {scene.duration}s
        </span>
        <span className="truncate rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-subtle">
          {catalog.find((m) => m.id === effectiveModel)?.label ?? effectiveModel}
        </span>
        <div className="relative ml-auto" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((o) => !o)}
            title="Scene options"
            className="rounded p-1 text-subtle transition-colors hover:bg-surface-2 hover:text-text"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
          {menuOpen && (
            <div
              className="absolute right-0 top-8 z-20 w-56 rounded-lg border border-border bg-card p-2"
              style={{ boxShadow: 'var(--shadow-elevated)' }}
            >
              <p className="label-section mb-1 px-1">Model for this scene</p>
              <select
                value={scene.model ?? ''}
                onChange={(e) => {
                  onChange({ model: e.target.value || undefined });
                  setMenuOpen(false);
                }}
                className="mb-2 h-7 w-full rounded border border-border bg-surface px-2 text-xs"
              >
                <option value="">Use project model</option>
                {catalog.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-1">
                <button
                  disabled={index === 0}
                  onClick={() => {
                    onMove(-1);
                    setMenuOpen(false);
                  }}
                  className="flex flex-1 items-center justify-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-surface-2 disabled:opacity-40"
                >
                  <ArrowUp className="h-3 w-3" /> Up
                </button>
                <button
                  disabled={index === total - 1}
                  onClick={() => {
                    onMove(1);
                    setMenuOpen(false);
                  }}
                  className="flex flex-1 items-center justify-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-surface-2 disabled:opacity-40"
                >
                  <ArrowDown className="h-3 w-3" /> Down
                </button>
              </div>
              <button
                onClick={() => {
                  onDelete();
                  setMenuOpen(false);
                }}
                className="mt-2 flex w-full items-center justify-center gap-1 rounded border border-border px-2 py-1 text-[11px] text-danger transition-colors hover:bg-danger-soft"
              >
                <Trash2 className="h-3 w-3" /> Delete scene
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        {/* thumbnail slot */}
        <div className="aspect-video w-32 shrink-0 overflow-hidden rounded border border-border bg-surface-2">
          {posterUrl ? (
            <video
              src={posterUrl}
              className="h-full w-full object-cover"
              controls
              preload="metadata"
            />
          ) : rendering ? (
            <div className="studio-pulse h-full w-full bg-surface-3" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-[10px] text-subtle">
              no clip yet
            </div>
          )}
        </div>

        {/* body */}
        <div className="min-w-0 flex-1 space-y-2">
          <textarea
            value={scene.visual_prompt}
            onChange={(e) => onChange({ visual_prompt: e.target.value })}
            rows={2}
            placeholder="Visual prompt for this scene"
            className="w-full resize-y rounded border border-border bg-surface-2 px-2 py-1.5 text-[12.5px] leading-snug text-text outline-none focus:border-strong"
          />
          <input
            value={scene.vo_line}
            onChange={(e) => onChange({ vo_line: e.target.value })}
            placeholder="Voiceover line"
            className={cn(
              'w-full rounded border border-border bg-surface px-2 py-1.5 text-[12.5px] text-text outline-none focus:border-strong',
            )}
          />
          {scene.on_screen_text && (
            <p className="text-[11px] text-subtle">
              On-screen: <span className="text-muted-foreground">{scene.on_screen_text}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
