/**
 * HiggsfieldGenerator — Studio's higgsfield image generation panel.
 *
 * Adapted from meta-ads-agent's reference component, restructured for
 * this codebase's async flow: POST /api/studio/generate-image returns
 * asset_ids immediately, then we subscribe to each via SSE (with
 * polling fallback) to surface running → completed | failed | nsfw.
 *
 * Single source of truth = the `ad_assets` row. The UI is a view of
 * the row's `status` column; closing the tab and refreshing
 * reconciles correctly because the worker keeps writing to the row.
 */

import { useState, useEffect, useRef } from 'react';
import { Sparkles, Loader2, AlertCircle, Check, ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  studioGenerateImage,
  studioGetJob,
  type StudioJobStatus,
  type HiggsfieldGenerateImageRequest,
} from '@/lib/api';

// job_set_type identifiers from the official @higgsfield/cli npm
// package — the value of the positional after `generate create`.
// Refresh from `higgsfield --json model list --image` if Higgsfield
// adds new models.
const IMAGE_MODELS: { id: string; label: string }[] = [
  { id: 'nano_banana_2', label: 'Nano Banana Pro' },
  { id: 'flux_2', label: 'FLUX.2' },
  { id: 'text2image_soul_v2', label: 'Soul V2 (character-faithful)' },
  { id: 'gpt_image_2', label: 'GPT Image 2' },
  { id: 'grok_image', label: 'Grok Image' },
  { id: 'kling_omni_image', label: 'Kling O1 Image' },
  { id: 'marketing_studio_image', label: 'Marketing Studio (text-in-image)' },
  { id: 'image_auto', label: 'Auto (Higgsfield picks)' },
];

const ASPECT_RATIOS = ['1:1', '4:5', '9:16', '16:9'] as const;
type AspectRatio = (typeof ASPECT_RATIOS)[number];

// Higgsfield's per-account image-gen cap.
const MAX_VARIANTS = 6;

interface HiggsfieldGeneratorProps {
  accountId: string;
  campaignId?: string;
  /** Called per asset as it transitions to a terminal state (completed
   * or failed). Slot-mode callers (PMaxWizard inline modal) use the
   * FIRST successful asset to pin the slot; Studio-mode callers
   * refresh their library on every settled. */
  onSettled?: (asset: StudioJobStatus) => void;
  /** Pre-fill prompt. Caller can still edit before submitting. */
  initialPrompt?: string;
  /** Pre-select an aspect ratio. Defaults to "1:1". */
  initialAspect?: AspectRatio;
  /** Disable the multi-aspect toggle and force a single aspect.
   * PMaxWizard inline uses this — each slot wants exactly one aspect. */
  lockAspect?: AspectRatio;
  /** Caption / hint shown next to the title. */
  caption?: string;
}

interface VariantState {
  asset_id: string;
  status: StudioJobStatus['status'];
  url: string | null;
  error_message: string | null;
}

export default function HiggsfieldGenerator({
  accountId, campaignId, onSettled,
  initialPrompt = '',
  initialAspect = '1:1',
  lockAspect,
  caption,
}: HiggsfieldGeneratorProps) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [model, setModel] = useState(IMAGE_MODELS[0].id);
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>(lockAspect ?? initialAspect);
  const [variantsCount, setVariantsCount] = useState<number>(1);
  // Multi-aspect mode: render the same prompt across all 4 aspects in
  // one Generate click. Disabled when a parent lockAspect is set
  // (PMaxWizard inline forces one aspect per slot).
  const [multiAspect, setMultiAspect] = useState(false);
  const [busy, setBusy] = useState(false);
  const [variants, setVariants] = useState<VariantState[]>([]);
  const eventSourcesRef = useRef<EventSource[]>([]);

  // Keep aspect in sync if the parent changes lockAspect mid-mount
  // (PMaxWizard opens different slot modals with different aspects).
  useEffect(() => {
    if (lockAspect) setAspectRatio(lockAspect);
  }, [lockAspect]);

  // Close any in-flight SSE connections on unmount so we don't leak
  // sockets when the user navigates away.
  useEffect(() => {
    return () => {
      eventSourcesRef.current.forEach((es) => es.close());
      eventSourcesRef.current = [];
    };
  }, []);

  const submit = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || busy) return;

    // Resolve which aspects + variant count.
    const aspectsToRun: AspectRatio[] = lockAspect
      ? [lockAspect]
      : multiAspect
        ? Array.from(ASPECT_RATIOS)
        : [aspectRatio];
    const variantsPerAspect = multiAspect ? 1 : Math.max(1, variantsCount);
    const total = aspectsToRun.length * variantsPerAspect;
    if (total > MAX_VARIANTS) {
      // Shouldn't happen via the UI controls but guard anyway.
      return;
    }

    setBusy(true);
    setVariants([]);
    // Close any leftover SSE from a previous run.
    eventSourcesRef.current.forEach((es) => es.close());
    eventSourcesRef.current = [];

    try {
      const body: HiggsfieldGenerateImageRequest = {
        prompt: trimmed,
        model,
        aspect_ratios: aspectsToRun.slice(),
        variants_per_aspect: variantsPerAspect,
        account_id: accountId,
        campaign_id: campaignId,
      };
      const res = await studioGenerateImage(body);
      // Initialize variants with pending state.
      setVariants(
        res.asset_ids.map((id) => ({
          asset_id: id,
          status: 'pending',
          url: null,
          error_message: null,
        })),
      );
      // Subscribe to each asset's stream.
      res.asset_ids.forEach((assetId) => {
        const es = new EventSource(`/api/studio/jobs/${assetId}/stream`);
        eventSourcesRef.current.push(es);
        es.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data) as StudioJobStatus;
            setVariants((prev) =>
              prev.map((v) =>
                v.asset_id === assetId
                  ? { ...v, status: data.status, url: data.url, error_message: data.error_message }
                  : v,
              ),
            );
            // Notify parent on terminal state.
            if (['completed', 'failed', 'nsfw'].includes(data.status)) {
              onSettled?.(data);
              es.close();
            }
          } catch {
            // Ignore malformed events; the polling fallback covers us.
          }
        };
        es.onerror = () => {
          // SSE failed — fall back to one-shot poll. Could re-poll on
          // a timer but for V1 a single fallback fetch is enough; if
          // the asset is genuinely stuck the row will reflect that.
          es.close();
          studioGetJob(assetId)
            .then((data) => {
              setVariants((prev) =>
                prev.map((v) =>
                  v.asset_id === assetId
                    ? { ...v, status: data.status, url: data.url, error_message: data.error_message }
                    : v,
                ),
              );
              if (['completed', 'failed', 'nsfw'].includes(data.status)) {
                onSettled?.(data);
              }
            })
            .catch(() => {});
        };
      });
    } catch (e) {
      // Network or 4xx — surface as a single failed variant.
      const msg = e instanceof Error ? e.message : String(e);
      setVariants([{ asset_id: 'err', status: 'failed', url: null, error_message: msg }]);
    } finally {
      setBusy(false);
    }
  };

  const settledCount = variants.filter((v) =>
    ['completed', 'failed', 'nsfw'].includes(v.status),
  ).length;
  const errCount = variants.filter((v) => v.status === 'failed' || v.status === 'nsfw').length;
  const runningCount = variants.filter((v) =>
    ['pending', 'running'].includes(v.status),
  ).length;

  return (
    <section className="border border-border rounded-md p-3 flex flex-col gap-2 bg-card">
      <div className="flex items-center gap-2 flex-wrap">
        <Sparkles className="h-3.5 w-3.5 text-primary" />
        <span className="text-[10px] uppercase font-mono text-muted-foreground">Higgsfield</span>
        <span className="text-xs font-medium">Image generation</span>
        {caption && (
          <span className="text-[10px] text-muted-foreground italic">{caption}</span>
        )}
      </div>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="A confident investor reviewing immigration documents in a sunlit home office, editorial photography, soft warm light."
        rows={3}
        disabled={busy}
        className="w-full rounded bg-secondary/40 border border-border px-2 py-1.5 text-sm disabled:opacity-50 resize-none"
      />

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <label className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase font-mono text-muted-foreground">Model</span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={busy}
            className="h-7 rounded border border-border bg-background px-2 text-xs"
          >
            {IMAGE_MODELS.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase font-mono text-muted-foreground">Aspect</span>
          <select
            value={aspectRatio}
            onChange={(e) => setAspectRatio(e.target.value as AspectRatio)}
            disabled={busy || multiAspect || !!lockAspect}
            title={
              lockAspect
                ? `Locked to ${lockAspect} (slot-mode generator)`
                : multiAspect
                  ? 'Disabled — multi-aspect mode renders all 4 ratios'
                  : ''
            }
            className="h-7 rounded border border-border bg-background px-2 text-xs font-mono disabled:opacity-40"
          >
            {ASPECT_RATIOS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </label>
        {!lockAspect && (
          <label
            className="flex items-center gap-1 cursor-pointer select-none"
            title="Render the same prompt across all 4 ad aspects (1:1, 4:5, 9:16, 16:9) in one click."
          >
            <input
              type="checkbox"
              checked={multiAspect}
              onChange={(e) => setMultiAspect(e.target.checked)}
              disabled={busy}
            />
            <span className="text-[10px] uppercase font-mono text-muted-foreground">All 4 aspects</span>
          </label>
        )}
        <label className="flex items-center gap-1.5">
          <span className="text-[10px] uppercase font-mono text-muted-foreground">Variants</span>
          <select
            value={variantsCount}
            onChange={(e) => setVariantsCount(Number(e.target.value))}
            disabled={busy || multiAspect}
            title={
              multiAspect
                ? 'Disabled — multi-aspect already uses 4 of the 6 parallel slots'
                : 'Higgsfield per-account cap = 6 parallel jobs'
            }
            className="h-7 rounded border border-border bg-background px-2 text-xs font-mono disabled:opacity-40"
          >
            {Array.from({ length: MAX_VARIANTS }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <Button
          onClick={submit}
          disabled={busy || !prompt.trim()}
          className="ml-auto gap-1.5"
          size="sm"
        >
          {busy ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {settledCount}/{variants.length || '…'}
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              {multiAspect ? 'Generate all 4' : variantsCount > 1 ? `Generate ${variantsCount}` : 'Generate'}
            </>
          )}
        </Button>
      </div>

      {variants.length > 0 && (
        <div className="flex flex-col gap-1.5 mt-1">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-1.5">
            {variants.map((v, i) => (
              <VariantTile key={v.asset_id} variant={v} index={i} />
            ))}
          </div>
          {!busy && variants.length > 1 && (
            <div className="text-[10px] uppercase font-mono text-muted-foreground">
              {settledCount - errCount} ok · {errCount} failed{runningCount > 0 ? ` · ${runningCount} running` : ''}
            </div>
          )}
          {errCount > 0 && !busy && (
            <div className="rounded border border-red-500/30 bg-red-500/5 p-2 text-[11px] flex flex-col gap-1">
              {variants
                .filter((v) => v.status === 'failed' || v.status === 'nsfw')
                .map((v, i) => (
                  <div key={v.asset_id} className="font-mono text-red-600 dark:text-red-400 break-words">
                    <span className="font-semibold mr-1">#{i + 1}</span>
                    {v.error_message || v.status}
                  </div>
                ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function VariantTile({ variant, index }: { variant: VariantState; index: number }) {
  const isRunning = variant.status === 'pending' || variant.status === 'running';
  const isOk = variant.status === 'completed' && variant.url;
  const isErr = variant.status === 'failed' || variant.status === 'nsfw';

  if (isRunning) {
    return (
      <div className="aspect-square rounded border border-border flex items-center justify-center text-[10px] font-mono text-muted-foreground bg-secondary/30">
        <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
        #{index + 1}
      </div>
    );
  }
  if (isOk) {
    return (
      <a
        href={variant.url || '#'}
        target="_blank"
        rel="noreferrer"
        className="aspect-square rounded border border-green-500/40 overflow-hidden bg-secondary/30 block group relative"
        title={`#${index + 1} saved to library`}
      >
        <img src={variant.url || ''} alt="" className="w-full h-full object-cover" loading="lazy" />
        <div className="absolute top-1 right-1 bg-green-500/80 text-white rounded-full p-0.5">
          <Check className="h-3 w-3" />
        </div>
      </a>
    );
  }
  if (isErr) {
    return (
      <div
        className="aspect-square rounded border border-red-500/40 bg-red-500/5 flex flex-col items-center justify-center text-[10px] font-mono text-red-600 dark:text-red-400 p-1 text-center break-all"
        title={variant.error_message || variant.status}
      >
        <AlertCircle className="h-3.5 w-3.5 mb-0.5" />
        #{index + 1}
        <span className="block leading-tight">
          {variant.status === 'nsfw' ? 'NSFW' : 'failed'}
        </span>
      </div>
    );
  }
  return (
    <div className="aspect-square rounded border border-border flex items-center justify-center text-[10px] font-mono text-muted-foreground">
      <ImageIcon className="h-3.5 w-3.5 opacity-30" />
    </div>
  );
}
