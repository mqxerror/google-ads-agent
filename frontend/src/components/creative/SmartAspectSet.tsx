// SmartAspectSet (Epic 17 · FR2.3/2.4/2.6) — "Generate the full set".
//
// One approved art direction → the whole slot set, rendered server-side in waves
// under the SAME 6-job semaphore as ad-hoc Studio generations, surviving a
// backend restart. Layered on the StudioPanel Enhance flow: the art direction is
// prefilled from the wizard brief and editable here.
//
// Two phases: CONFIGURE (model · mode · per-slot variants · honest credit
// preflight) then RUNNING (a live tile grid from the batch SSE stream, per-tile
// retry, advisory safe-zone chips). Finished tiles auto-assign to their slot via
// `onAssign` — the composite image when a logo was overlaid, else the base.
//
// The tile cap and retry cap come from the registry (ENGINE) — zero baked
// limits (guard-scanned).

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, Loader2, RefreshCw, Sparkles, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCreativeSpecs } from '@/lib/creativeSpecs';
import {
  studioBatchRender, studioGetBatch, studioListModels, studioBalance,
  studioRetryBatchTile,
  type BatchView, type BatchTileView, type StudioModelInfo,
} from '@/lib/api';

export interface SmartAspectSlot {
  slot: string;     // key into IMAGE_SLOT_SPECS (registry)
  label: string;    // human label, e.g. "Landscape (1.91:1)"
  aspect: number;   // w/h for the preview frame
}

export type SmartAspectMode = 'with_logo' | 'without_logo' | 'asset_anchored';

export interface SmartAspectSetProps {
  open: boolean;
  onClose: () => void;
  accountId: string;
  campaignType: 'pmax' | 'demand_gen';
  campaignId?: string;
  /** Prefilled from the wizard brief / an Enhance prompt; editable here. */
  artDirection: string;
  /** The wizard's slot set (what "the full set" means for this campaign type). */
  slots: SmartAspectSlot[];
  /** Reference photos to anchor generation on (asset_anchored mode). */
  referenceAssetIds?: string[];
  /** A logo library asset id, enabling with_logo mode. */
  logoAssetId?: string;
  /** Push a finished tile's asset id (+ preview url) into the wizard's slot. */
  onAssign: (slot: string, assetId: string, url?: string | null) => void;
}

const DEFAULT_VARIANTS = 2;

export default function SmartAspectSet(props: SmartAspectSetProps) {
  const { open, onClose, accountId, campaignType, campaignId, artDirection,
    slots, referenceAssetIds, logoAssetId, onAssign } = props;
  const { specs } = useCreativeSpecs();
  const tileCap = specs?.engine?.batch_tile_cap ?? null;

  const [prompt, setPrompt] = useState(artDirection);
  const [model, setModel] = useState<string>('');
  const [models, setModels] = useState<StudioModelInfo[]>([]);
  const [mode, setMode] = useState<SmartAspectMode>('without_logo');
  const [variants, setVariants] = useState<Record<string, number>>(() =>
    Object.fromEntries(slots.map(s => [s.slot, DEFAULT_VARIANTS])));
  const [balance, setBalance] = useState<number | null>(null);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [view, setView] = useState<BatchView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const assignedRef = useRef<Set<string>>(new Set());
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => { setPrompt(artDirection); }, [artDirection]);

  // Load image models + balance when the panel opens.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    studioListModels('image').then(r => {
      if (cancelled) return;
      setModels(r.models);
      const def = r.models.find(m => m.default) ?? r.models[0];
      setModel(prev => prev || (def?.id ?? ''));
    }).catch(() => { /* model list degrades to the id we have */ });
    studioBalance().then(b => { if (!cancelled) setBalance(b.credits); })
      .catch(() => { /* balance is advisory */ });
    return () => { cancelled = true; };
  }, [open]);

  const chosenModel = useMemo(
    () => models.find(m => m.id === model), [models, model]);
  const perImage = chosenModel?.est_credits ?? 0;

  const tileCount = useMemo(
    () => slots.reduce((n, s) => n + (variants[s.slot] ?? 0), 0),
    [slots, variants]);
  const estCredits = tileCount * perImage;
  const overCap = tileCap != null && tileCount > tileCap;

  // ── streaming ────────────────────────────────────────────────
  const closeStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  const applyView = useCallback((v: BatchView) => {
    setView(v);
    // Auto-assign every newly-finished tile to its slot (once).
    for (const t of v.tiles) {
      if (t.status !== 'completed') continue;
      const id = t.composite_asset_id ?? t.asset_id;
      const key = t.asset_id;
      if (assignedRef.current.has(key)) continue;
      assignedRef.current.add(key);
      onAssign(t.slot, id, t.composite_url ?? t.url);
    }
  }, [onAssign]);

  const watch = useCallback((id: string) => {
    closeStream();
    const es = new EventSource(`/api/studio/batch-render/${id}/stream`);
    esRef.current = es;
    es.onmessage = (ev) => {
      try {
        const v = JSON.parse(ev.data) as BatchView;
        if ((v as unknown as { error?: string }).error) return;
        applyView(v);
        if (['done', 'done_with_failures', 'cancelled'].includes(v.status)) es.close();
      } catch { /* poll fallback below */ }
    };
    es.onerror = () => {
      es.close();
      studioGetBatch(id).then(applyView).catch(() => {});
    };
  }, [applyView, closeStream]);

  useEffect(() => closeStream, [closeStream]);

  const handleGenerate = useCallback(async () => {
    if (submitting || overCap || tileCount === 0 || !prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    assignedRef.current = new Set();
    try {
      const res = await studioBatchRender({
        account_id: accountId,
        art_direction: prompt.trim(),
        model,
        mode,
        campaign_type: campaignType,
        campaign_id: campaignId,
        logo_asset_id: mode === 'with_logo' ? logoAssetId : undefined,
        reference_asset_ids: mode === 'asset_anchored' ? referenceAssetIds : undefined,
        slots: slots
          .map(s => ({ slot: s.slot, variants: variants[s.slot] ?? 0 }))
          .filter(s => s.variants > 0),
      });
      setBatchId(res.batch_id);
      watch(res.batch_id);
      studioGetBatch(res.batch_id).then(applyView).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }, [submitting, overCap, tileCount, prompt, accountId, model, mode, campaignType,
      campaignId, logoAssetId, referenceAssetIds, slots, variants, watch, applyView]);

  const handleRetry = useCallback(async (assetId: string) => {
    if (!batchId) return;
    try {
      await studioRetryBatchTile(batchId, assetId);
      watch(batchId);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [batchId, watch]);

  if (!open) return null;

  const running = batchId !== null;
  const slotLabel = (slot: string) => slots.find(s => s.slot === slot)?.label ?? slot;
  const slotAspect = (slot: string) => slots.find(s => s.slot === slot)?.aspect ?? 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog" aria-modal="true" aria-label="Generate the full set"
    >
      <div className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-lg border border-border bg-card shadow-xl">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">Generate the full set</h2>
          </div>
          <button onClick={() => { closeStream(); onClose(); }} className="rounded p-1 hover:bg-secondary" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        {!running ? (
          <div className="space-y-4 p-4">
            <div>
              <label className="mb-1 block text-xs font-medium">Art direction</label>
              <textarea
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                rows={3}
                className="w-full resize-y rounded-md border border-border bg-background p-2 text-xs"
                placeholder="One approved art direction for every slot…"
              />
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium">Model</label>
                <select
                  value={model}
                  onChange={e => setModel(e.target.value)}
                  className="w-full rounded-md border border-border bg-background p-2 text-xs"
                >
                  {models.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.label} · {m.tier}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium">Logo &amp; references</label>
                <select
                  value={mode}
                  onChange={e => setMode(e.target.value as SmartAspectMode)}
                  className="w-full rounded-md border border-border bg-background p-2 text-xs"
                >
                  <option value="without_logo">No logo (default)</option>
                  <option value="with_logo" disabled={!logoAssetId}>
                    Composite my logo{logoAssetId ? '' : ' (add a logo first)'}
                  </option>
                  <option value="asset_anchored" disabled={!referenceAssetIds?.length}>
                    Anchor to my reference photos
                  </option>
                </select>
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-medium">Variants per slot</p>
              <div className="space-y-1.5">
                {slots.map(s => (
                  <div key={s.slot} className="flex items-center justify-between rounded-md border border-border bg-secondary/20 px-3 py-1.5">
                    <span className="text-xs">{s.label}</span>
                    <Stepper
                      value={variants[s.slot] ?? 0}
                      min={0}
                      max={tileCap ?? undefined}
                      onChange={v => setVariants(prev => ({ ...prev, [s.slot]: v }))}
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Credit preflight — honest, estimate-labeled (FR2.6). */}
            <div className={cn(
              'rounded-md border p-3 text-xs',
              overCap ? 'border-warning bg-warning/10' : 'border-border bg-secondary/20',
            )}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{tileCount} tiles</span>
                <span className="tabular-nums text-muted-foreground">
                  ≈ {estCredits} credits <span className="opacity-70">(est.)</span>
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
                <span>
                  {perImage ? `~${perImage} est. credits/image` : 'estimate unavailable'}
                  {balance != null && ` · balance ${balance}`}
                </span>
                {tileCap != null && (
                  <span className={overCap ? 'text-warning' : ''}>
                    cap {tileCap} tiles
                  </span>
                )}
              </div>
              {overCap && tileCap != null && (
                <p className="mt-1.5 flex items-center gap-1 text-warning">
                  <AlertTriangle className="h-3 w-3 shrink-0" />
                  Over the {tileCap}-tile cap — reduce variants to continue.
                </p>
              )}
            </div>

            {error && <p className="text-xs text-red-500">{error}</p>}

            <button
              type="button"
              onClick={handleGenerate}
              disabled={submitting || overCap || tileCount === 0 || !prompt.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Generate the full set
            </button>
          </div>
        ) : (
          <div className="space-y-3 p-4">
            <BatchProgress view={view} />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {(view?.tiles ?? []).map(t => (
                <TileCard
                  key={t.asset_id}
                  tile={t}
                  label={slotLabel(t.slot)}
                  aspect={slotAspect(t.slot)}
                  onRetry={() => handleRetry(t.asset_id)}
                />
              ))}
            </div>
            {error && <p className="text-xs text-red-500">{error}</p>}
            {view && ['done', 'done_with_failures'].includes(view.status) && (
              <button
                type="button"
                onClick={() => { closeStream(); onClose(); }}
                className="w-full rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-secondary"
              >
                Done — finished tiles are in their slots
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Stepper({ value, min, max, onChange }: {
  value: number; min: number; max?: number; onChange: (v: number) => void;
}) {
  const dec = () => onChange(Math.max(min, value - 1));
  const inc = () => onChange(max != null ? Math.min(max, value + 1) : value + 1);
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={dec} className="h-6 w-6 rounded border border-border hover:bg-secondary" aria-label="Fewer">−</button>
      <span className="w-5 text-center text-xs tabular-nums">{value}</span>
      <button type="button" onClick={inc} className="h-6 w-6 rounded border border-border hover:bg-secondary" aria-label="More">+</button>
    </div>
  );
}

function BatchProgress({ view }: { view: BatchView | null }) {
  const p = view?.progress ?? { done: 0, failed: 0, total: 0 };
  const settled = p.done + p.failed;
  const pct = p.total ? Math.round((settled / p.total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium">
          {p.done} done{p.failed ? ` · ${p.failed} failed` : ''} / {p.total}
        </span>
        <span className="text-muted-foreground tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function TileCard({ tile, label, aspect, onRetry }: {
  tile: BatchTileView; label: string; aspect: number; onRetry: () => void;
}) {
  const flagged = !!tile.safe_zone?.slots?.[tile.slot]?.flagged;
  const previewUrl = tile.composite_url ?? tile.url;
  return (
    <div className="text-xs">
      <div
        className={cn(
          'relative overflow-hidden rounded-md border bg-secondary/30',
          flagged ? 'border-warning' : 'border-border',
        )}
        style={{ aspectRatio: String(aspect) }}
        title={`${label} · variant ${tile.variant_index + 1}`}
      >
        {previewUrl ? (
          <img src={previewUrl} alt={label} className="h-full w-full object-cover" loading="lazy" />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            {tile.status === 'failed' || tile.status === 'nsfw' ? (
              <AlertTriangle className="h-4 w-4 text-warning" />
            ) : (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
          </div>
        )}
        {tile.status === 'completed' && (
          <CheckCircle2 className="absolute right-1 top-1 h-4 w-4 text-emerald-500 drop-shadow" />
        )}
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="truncate text-[10px] text-muted-foreground">{label}</span>
        {(tile.status === 'failed' || tile.status === 'nsfw') && (
          <button
            type="button"
            onClick={onRetry}
            className="flex items-center gap-0.5 text-[10px] text-primary hover:underline"
          >
            <RefreshCw className="h-2.5 w-2.5" /> Retry
          </button>
        )}
      </div>
      {flagged && (
        <p className="mt-0.5 flex items-center gap-0.5 text-[9px] leading-tight text-warning">
          <AlertTriangle className="h-2.5 w-2.5 shrink-0" /> subject may be cut in this ratio
        </p>
      )}
    </div>
  );
}
