/**
 * DemandGenCreative — the Studio's Demand Gen creative section.
 *
 * The reject-the-AI-creative → iterate-with-my-own-photos flow, in one place:
 *
 *   1. Reference & generate — attach the operator's OWN library images (real
 *      hotel / property photos) as references, draft a corporate-brand prompt
 *      with the Demand Gen preset (text-free, editorial, DG aspects), and
 *      generate anchored variants. New images land in the shared library.
 *   2. Build the ad's images — pick images from the gallery and assign each to
 *      a Demand Gen slot (landscape 1.91:1 / square 1:1 / logo 1:1).
 *   3. Push to campaign ad — replace or append those images on a live
 *      DemandGenMultiAssetAd IN PLACE (confirm-gated).
 *
 * Design: DESIGN.md tokens only (calm light). Uploaded/generated images share
 * the same ad_assets library the generators write to, so anything the operator
 * uploads via the Studio "Upload" button appears here immediately.
 */

import { useCallback, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ImagePlus, Loader2, Sparkles, Upload as UploadIcon, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  demandGenUpdateAdImages,
  studioExtractBrief,
  studioGenerateImage,
  type BriefVariant,
} from '@/lib/api';
import type { AdAsset } from './AssetLibrary';
import { ASSETS_QUERY_KEY } from './AssetLibrary';

// The launched Demand Gen ad this flow was built to iterate on (editable).
const DEFAULT_AD_GROUP_ID = '205525130784';
const DEFAULT_AD_ID = '818651372857';

// Demand Gen image slots → the fields the push endpoint accepts. Logo/square
// are 1:1, landscape is 1.91:1.
type Slot = 'landscape' | 'square' | 'logo';
const SLOTS: { key: Slot; label: string; hint: string }[] = [
  { key: 'landscape', label: 'Landscape', hint: '1.91:1' },
  { key: 'square', label: 'Square', hint: '1:1' },
  { key: 'logo', label: 'Logo', hint: '1:1' },
];

async function fetchImageAssets(accountId: string): Promise<AdAsset[]> {
  const qs = new URLSearchParams({
    account_id: accountId, asset_type: 'image', limit: '60', offset: '0',
  });
  const r = await fetch(`/api/assets?${qs}`);
  if (!r.ok) throw new Error(`assets list failed (${r.status})`);
  return r.json();
}

interface Props {
  accountId: string;
  /** Host opens its shared upload picker (StudioHome's hidden file input). */
  onUpload?: () => void;
}

export default function DemandGenCreative({ accountId, onUpload }: Props) {
  const queryClient = useQueryClient();

  const assetsQuery = useQuery({
    queryKey: [ASSETS_QUERY_KEY, 'dg-images', accountId],
    queryFn: () => fetchImageAssets(accountId),
    enabled: !!accountId,
    staleTime: 10_000,
  });
  const assets = useMemo(
    () => (assetsQuery.data ?? []).filter((a) => !!a.url && a.type === 'image'),
    [assetsQuery.data],
  );
  const refreshAssets = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [ASSETS_QUERY_KEY] });
  }, [queryClient]);

  // ── Card 1: references + generate ───────────────────────────────
  const [referenceIds, setReferenceIds] = useState<string[]>([]);
  const [prompt, setPrompt] = useState('');
  const [drafting, setDrafting] = useState(false);
  const [variants, setVariants] = useState<BriefVariant[]>([]);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);

  const toggleReference = useCallback((id: string) => {
    setReferenceIds((ids) =>
      ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]);
  }, []);

  const referenceNote = useMemo(() => {
    if (referenceIds.length === 0) return undefined;
    const names = referenceIds
      .map((id) => assets.find((a) => a.id === id)?.filename)
      .filter(Boolean);
    return names.length ? names.join(', ') : `${referenceIds.length} attached image(s)`;
  }, [referenceIds, assets]);

  const handleDraft = useCallback(async () => {
    setDrafting(true);
    setVariants([]);
    setGenMsg(null);
    try {
      const res = await studioExtractBrief({
        context: prompt.trim() || 'Corporate residency-by-investment brand image for a Demand Gen ad.',
        target: 'image',
        account_id: accountId || undefined,
        preset: 'demand_gen',
        reference_note: referenceNote,
      });
      setVariants(res.variants || []);
      if (res.variants?.[0]?.prompt) setPrompt(res.variants[0].prompt);
    } catch (e) {
      setGenMsg(`Draft failed: ${e instanceof Error ? e.message : 'unknown error'}`);
    } finally {
      setDrafting(false);
    }
  }, [prompt, accountId, referenceNote]);

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) { setGenMsg('Write or draft a prompt first.'); return; }
    setGenerating(true);
    setGenMsg(null);
    try {
      // Two DG aspects in one shot (1.91:1 landscape + 1:1 square), anchored to
      // the attached references. Nano Banana takes reference images.
      const res = await studioGenerateImage({
        prompt: prompt.trim(),
        model: 'nano_banana_2',
        aspect_ratios: ['1.91:1', '1:1'],
        variants_per_aspect: 1,
        account_id: accountId || undefined,
        reference_asset_ids: referenceIds.length ? referenceIds : undefined,
      });
      setGenMsg(`Generating ${res.asset_ids.length} image(s) — they will appear in the gallery below.`);
      // Give the workers a beat, then refresh so new tiles surface.
      window.setTimeout(refreshAssets, 4000);
      window.setTimeout(() => assetsQuery.refetch(), 4000);
    } catch (e) {
      setGenMsg(`Generation failed: ${e instanceof Error ? e.message : 'unknown error'}`);
    } finally {
      setGenerating(false);
    }
  }, [prompt, accountId, referenceIds, refreshAssets, assetsQuery]);

  // ── Card 2: slot assignment ─────────────────────────────────────
  const [slotAssign, setSlotAssign] = useState<Record<Slot, string[]>>({
    landscape: [], square: [], logo: [],
  });
  const toggleSlot = useCallback((slot: Slot, id: string) => {
    setSlotAssign((cur) => {
      const has = cur[slot].includes(id);
      return { ...cur, [slot]: has ? cur[slot].filter((x) => x !== id) : [...cur[slot], id] };
    });
  }, []);
  const totalAssigned = slotAssign.landscape.length + slotAssign.square.length + slotAssign.logo.length;

  // ── Card 3: push to ad ──────────────────────────────────────────
  const [adGroupId, setAdGroupId] = useState(DEFAULT_AD_GROUP_ID);
  const [adId, setAdId] = useState(DEFAULT_AD_ID);
  const [mode, setMode] = useState<'replace' | 'append'>('replace');
  const [confirming, setConfirming] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<string | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);

  const handlePush = useCallback(async () => {
    setPushing(true);
    setPushResult(null);
    setPushError(null);
    try {
      const res = await demandGenUpdateAdImages(accountId, {
        ad_group_id: adGroupId.trim() || undefined,
        ad_id: adId.trim() || undefined,
        mode,
        landscape_images: slotAssign.landscape,
        square_images: slotAssign.square,
        logos: slotAssign.logo,
      });
      const slots = Object.entries(res.updated_slots)
        .map(([s, ids]) => `${s}×${ids.length}`).join(', ');
      setPushResult(`Ad ${res.ad_id} updated (${res.mode}): ${slots || 'no slots'}.`);
    } catch (e) {
      setPushError(e instanceof Error ? e.message : 'push failed');
    } finally {
      setPushing(false);
      setConfirming(false);
    }
  }, [accountId, adGroupId, adId, mode, slotAssign]);

  const canPush = totalAssigned > 0 && !!(adGroupId.trim() && adId.trim());

  return (
    <div className="space-y-5 max-w-5xl">
      {/* ── Card 1: References + generate ── */}
      <section className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-accent" /> Generate with your references
            </h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Corporate brand preset — text-free, editorial, sized for Demand Gen slots. Attach your
              own hotel or property photos below so the images feature your real asset.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-border text-muted-foreground bg-surface-2">
            demand_gen preset
          </span>
        </div>

        {referenceIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">References:</span>
            {referenceIds.map((id) => {
              const a = assets.find((x) => x.id === id);
              return (
                <span key={id} className="inline-flex items-center gap-1 text-[11px] bg-accent-soft text-accent border border-accent/30 rounded px-1.5 py-0.5">
                  {a?.filename?.slice(0, 20) ?? id.slice(0, 8)}
                  <button onClick={() => toggleReference(id)} aria-label="Remove reference">
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              );
            })}
          </div>
        )}

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Describe the image, or click Draft to generate a corporate-brand prompt…"
          className="w-full text-xs bg-surface-2 border border-border rounded-md px-2.5 py-2 focus:outline-none focus:border-accent resize-y"
        />

        {variants.length > 0 && (
          <div className="space-y-1.5">
            <div className="label-section">Drafted angles — pick one</div>
            {variants.map((v) => (
              <button
                key={v.angle}
                onClick={() => setPrompt(v.prompt)}
                className={cn(
                  'block w-full text-left rounded border px-2 py-1.5 text-[11px] transition-colors',
                  prompt === v.prompt
                    ? 'border-accent bg-accent-soft'
                    : 'border-border hover:border-accent/40 bg-surface-2',
                )}
              >
                <span className="font-medium capitalize text-accent">{v.angle}</span>
                <span className="text-muted-foreground"> — {v.rationale}</span>
                <p className="mt-0.5 line-clamp-2">{v.prompt}</p>
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <Button size="sm" variant="outline" onClick={handleDraft} disabled={drafting} className="gap-1.5">
            {drafting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            Draft prompt
          </Button>
          <Button size="sm" onClick={handleGenerate} disabled={generating} className="gap-1.5">
            {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-3.5" />}
            Generate (1.91:1 + 1:1)
          </Button>
          {genMsg && <span className="text-[11px] text-muted-foreground">{genMsg}</span>}
        </div>
      </section>

      {/* ── Card 2: gallery + slot assignment ── */}
      <section className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold">Build the ad's images</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Click a tile to attach it as a reference (above), or assign it to a Demand Gen slot.
              Uploaded and generated images both appear here.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {onUpload && (
              <button
                onClick={onUpload}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-secondary hover:bg-secondary/80 text-xs border border-border"
              >
                <UploadIcon className="h-3.5 w-3.5" /> Upload
              </button>
            )}
            <button
              onClick={() => { refreshAssets(); assetsQuery.refetch(); }}
              className="px-2.5 py-1 text-[11px] bg-secondary/30 hover:bg-secondary/50 border border-border rounded-md"
            >
              ↻ Refresh
            </button>
          </div>
        </div>

        {assetsQuery.isLoading ? (
          <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-2">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-md bg-secondary/40 animate-pulse" />
            ))}
          </div>
        ) : assets.length === 0 ? (
          <div className="border border-dashed border-border rounded-lg py-12 text-center">
            <ImagePlus className="h-7 w-7 text-muted-foreground/50 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              No images yet. Upload your property photos or generate some above.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-6 gap-2">
            {assets.map((a) => {
              const isRef = referenceIds.includes(a.id);
              const inSlots = SLOTS.filter((s) => slotAssign[s.key].includes(a.id));
              return (
                <div
                  key={a.id}
                  className={cn(
                    'group relative rounded-md overflow-hidden border bg-card',
                    isRef || inSlots.length ? 'border-accent ring-1 ring-accent/40' : 'border-border',
                  )}
                >
                  <button
                    onClick={() => toggleReference(a.id)}
                    className="block w-full aspect-square bg-secondary/30"
                    title={isRef ? 'Remove as reference' : 'Attach as reference'}
                  >
                    <img src={a.url} alt={a.filename} loading="lazy" className="w-full h-full object-cover" />
                    {isRef && (
                      <span className="absolute top-1 left-1 bg-accent text-on-accent text-[9px] px-1 py-0.5 rounded">ref</span>
                    )}
                  </button>
                  {/* Slot assignment chips */}
                  <div className="flex items-stretch divide-x divide-border border-t border-border">
                    {SLOTS.map((s) => {
                      const on = slotAssign[s.key].includes(a.id);
                      return (
                        <button
                          key={s.key}
                          onClick={() => toggleSlot(s.key, a.id)}
                          title={`Assign to ${s.label} (${s.hint})`}
                          className={cn(
                            'flex-1 text-[9px] py-0.5 transition-colors',
                            on ? 'bg-accent-soft text-accent font-medium' : 'text-muted-foreground hover:bg-secondary/50',
                          )}
                        >
                          {s.label[0]}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {totalAssigned > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="text-muted-foreground">Assigned:</span>
            {SLOTS.map((s) => (
              <span key={s.key} className="inline-flex items-center gap-1 bg-surface-2 border border-border rounded px-1.5 py-0.5">
                {s.label} <span className="font-mono text-accent">{slotAssign[s.key].length}</span>
              </span>
            ))}
            <button
              onClick={() => setSlotAssign({ landscape: [], square: [], logo: [] })}
              className="text-muted-foreground hover:text-foreground underline"
            >
              Clear
            </button>
          </div>
        )}
      </section>

      {/* ── Card 3: push to ad ── */}
      <section className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Push to campaign ad</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Updates the live Demand Gen ad's images in place — same ad, same text and history.
            Only the slots you assigned are changed.
          </p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
          <label className="text-[11px] text-muted-foreground">
            Ad group ID
            <input
              value={adGroupId}
              onChange={(e) => setAdGroupId(e.target.value)}
              className="mt-0.5 w-full h-8 rounded border border-border bg-surface-2 px-2 text-xs font-mono focus:outline-none focus:border-accent"
            />
          </label>
          <label className="text-[11px] text-muted-foreground">
            Ad ID
            <input
              value={adId}
              onChange={(e) => setAdId(e.target.value)}
              className="mt-0.5 w-full h-8 rounded border border-border bg-surface-2 px-2 text-xs font-mono focus:outline-none focus:border-accent"
            />
          </label>
          <label className="text-[11px] text-muted-foreground">
            Mode
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as 'replace' | 'append')}
              className="mt-0.5 w-full h-8 rounded border border-border bg-surface-2 px-2 text-xs focus:outline-none focus:border-accent"
            >
              <option value="replace">Replace slot images</option>
              <option value="append">Append to slot</option>
            </select>
          </label>
          <Button size="sm" onClick={() => setConfirming(true)} disabled={!canPush || pushing} className="gap-1.5 h-8">
            {pushing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
            Push to ad
          </Button>
        </div>
        {!canPush && (
          <p className="text-[11px] text-muted-foreground">
            Assign at least one image to a slot and set the ad group + ad IDs to enable the push.
          </p>
        )}
        {pushResult && (
          <p className="text-[11px] text-success bg-success-soft border border-success/30 rounded px-2 py-1.5">{pushResult}</p>
        )}
        {pushError && (
          <p className="text-[11px] text-danger bg-danger-soft border border-danger/30 rounded px-2 py-1.5">{pushError}</p>
        )}
      </section>

      {/* ── Confirm dialog ── */}
      {confirming && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-6" onClick={() => setConfirming(false)}>
          <div className="bg-card border border-border rounded-lg max-w-md w-full p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold">Confirm push to live ad</h3>
            <p className="text-xs text-muted-foreground">
              This will <span className="font-medium text-foreground">{mode}</span> images on the live Demand Gen ad
              <span className="font-mono"> {adId}</span> (ad group <span className="font-mono">{adGroupId}</span>):
            </p>
            <ul className="text-[11px] space-y-0.5">
              {SLOTS.filter((s) => slotAssign[s.key].length).map((s) => (
                <li key={s.key} className="flex gap-2">
                  <span className="text-muted-foreground w-20">{s.label} ({s.hint})</span>
                  <span className="font-mono text-accent">{slotAssign[s.key].length} image(s)</span>
                </li>
              ))}
            </ul>
            <p className="text-[11px] text-warning bg-warning-soft border border-warning/30 rounded px-2 py-1.5">
              The images serve on the live campaign. Local images are cropped to each slot's exact aspect automatically.
            </p>
            <div className="flex items-center justify-end gap-2 pt-1">
              <button onClick={() => setConfirming(false)} className="text-xs px-3 py-1.5 rounded border border-border hover:bg-secondary">
                Cancel
              </button>
              <Button size="sm" onClick={handlePush} disabled={pushing} className="gap-1.5">
                {pushing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                Confirm push
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
