/**
 * ModelPicker — shared model selector fed by the server-side catalog
 * (GET /api/studio/models). Plain-language tiers up front ("Best
 * quality / Fast / Budget"); raw model ids only appear in the option
 * title attribute. One module-level cache per kind so multiple mounted
 * pickers don't refetch.
 */

import { useEffect, useState } from 'react';
import { studioListModels, type StudioModelInfo } from '@/lib/api';

const TIER_ORDER: Record<string, number> = { 'Best quality': 0, Fast: 1, Budget: 2 };

const catalogCache: Partial<Record<'image' | 'video', Promise<StudioModelInfo[]>>> = {};

export function fetchCatalog(kind: 'image' | 'video'): Promise<StudioModelInfo[]> {
  if (!catalogCache[kind]) {
    catalogCache[kind] = studioListModels(kind)
      .then((r) => r.models.filter((m) => m.available))
      .catch((e) => {
        delete catalogCache[kind]; // allow retry on next mount
        throw e;
      });
  }
  return catalogCache[kind]!;
}

export function useModelCatalog(kind: 'image' | 'video') {
  const [models, setModels] = useState<StudioModelInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetchCatalog(kind)
      .then((m) => { if (!cancelled) setModels(m); })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); });
    return () => { cancelled = true; };
  }, [kind]);
  return { models, error };
}

export default function ModelPicker({
  kind, value, onChange, disabled, className,
}: {
  kind: 'image' | 'video';
  value: string;
  onChange: (id: string, model: StudioModelInfo | undefined) => void;
  disabled?: boolean;
  className?: string;
}) {
  const { models, error } = useModelCatalog(kind);

  // Default selection once the catalog lands and nothing is picked yet
  // (or the picked id belongs to the other kind after a mode switch).
  useEffect(() => {
    if (!models.length) return;
    const current = models.find((m) => m.id === value);
    if (!current) {
      const def = models.find((m) => m.default) || models[0];
      onChange(def.id, def);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [models, value]);

  const sorted = [...models].sort(
    (a, b) => (TIER_ORDER[a.tier] ?? 9) - (TIER_ORDER[b.tier] ?? 9) || a.label.localeCompare(b.label),
  );

  if (error) {
    return (
      <span className="text-[10px] text-muted-foreground" title={error}>
        model list unavailable
      </span>
    );
  }

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value, models.find((m) => m.id === e.target.value))}
      disabled={disabled || !models.length}
      className={className ?? 'h-7 rounded border border-border bg-background px-2 text-xs disabled:opacity-40'}
    >
      {!models.length && <option value="">Loading models…</option>}
      {sorted.map((m) => (
        <option key={m.id} value={m.id} title={`${m.id} · ${m.cost_text}`}>
          {m.label} · {m.tier}
        </option>
      ))}
    </select>
  );
}
