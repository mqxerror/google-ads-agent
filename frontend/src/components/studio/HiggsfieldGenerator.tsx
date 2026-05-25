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
import { Sparkles, Loader2, AlertCircle, Check, ImageIcon, Video as VideoIcon, Image as ImageGlyph, LinkIcon, Wand2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  studioGenerateImage,
  studioGenerateVideo,
  studioGetJob,
  studioCostEstimate,
  studioListSouls,
  studioExtractBrief,
  type StudioJobStatus,
  type HiggsfieldGenerateImageRequest,
  type HiggsfieldGenerateVideoRequest,
  type SoulCharacter,
  type BriefVariant,
} from '@/lib/api';

// Models that accept --soul-id. When one of these is selected, the
// generator surfaces a Soul picker pulling from the account's library.
const SOUL_AWARE_MODELS = new Set([
  'text2image_soul_v2',
  'soul_cinematic',
  'soul_location',
  'soul_cast',
]);

// job_set_type identifiers from the official @higgsfield/cli npm
// package — the value of the positional after `generate create`.
// Refresh from `higgsfield --json model list --image` if Higgsfield
// adds new models.
// Image models from `higgsfield --json model list --image` (May 2026).
// Refresh that command after Higgsfield ships new models.
const IMAGE_MODELS: { id: string; label: string }[] = [
  { id: 'nano_banana_2',          label: 'Nano Banana Pro (premium)' },
  { id: 'nano_banana_flash',      label: 'Nano Banana 2 (mid-tier)' },
  { id: 'nano_banana',            label: 'Nano Banana (budget)' },
  { id: 'flux_2',                 label: 'FLUX.2' },
  { id: 'flux_kontext',           label: 'FLUX Kontext' },
  { id: 'text2image_soul_v2',     label: 'Soul V2 (face-consistent)' },
  { id: 'soul_cinematic',         label: 'Soul Cinematic' },
  { id: 'soul_location',          label: 'Soul Location' },
  { id: 'gpt_image_2',            label: 'GPT Image 2' },
  { id: 'imagegen_2_0',           label: 'GPT Image 2 (alt)' },
  { id: 'openai_hazel',           label: 'OpenAI Hazel' },
  { id: 'grok_image',             label: 'Grok Image' },
  { id: 'kling_omni_image',       label: 'Kling O1 Image' },
  { id: 'seedream_v4_5',          label: 'Seedream 4.5' },
  { id: 'seedream_v5_lite',       label: 'Seedream V5 Lite (budget)' },
  { id: 'marketing_studio_image', label: 'Marketing Studio (text-in-image)' },
  { id: 'ms_image',               label: 'MS Image' },
  { id: 'cinematic_studio_2_5',   label: 'Cinematic Studio 2.5' },
  { id: 'z_image',                label: 'Z Image' },
  { id: 'image_auto',             label: 'Auto (Higgsfield picks)' },
];

// Video models from `higgsfield --json model list --video` (May 2026).
// maxSeconds is the per-model upstream cap surfaced in the picker so
// the operator doesn't burn a 20s render that returns 8s. Veo's cap is
// strict enum (4/6/8); Kling caps at 15; the rest vary.
const VIDEO_MODELS: { id: string; label: string; maxSeconds?: number; budgetTier?: 'budget' | 'premium' }[] = [
  { id: 'veo3_1',                   label: 'Veo 3.1 (Google, premium)',    maxSeconds: 8, budgetTier: 'premium' },
  { id: 'veo3_1_lite',              label: 'Veo 3.1 Lite (cheap)',         maxSeconds: 8, budgetTier: 'budget' },
  { id: 'veo3',                     label: 'Veo 3 (Google, older)',        maxSeconds: 8 },
  { id: 'kling3_0',                 label: 'Kling 3.0',                    maxSeconds: 15 },
  { id: 'kling2_6',                 label: 'Kling 2.6 (cheap)',            maxSeconds: 10, budgetTier: 'budget' },
  { id: 'seedance_2_0',             label: 'Seedance 2.0' },
  { id: 'seedance1_5',              label: 'Seedance 1.5 Pro' },
  { id: 'minimax_hailuo',           label: 'Minimax Hailuo' },
  { id: 'grok_video',               label: 'Grok Video' },
  { id: 'wan2_7',                   label: 'Wan 2.7' },
  { id: 'wan2_6',                   label: 'Wan 2.6' },
  { id: 'soul_cast',                label: 'Soul Cast (face-consistent)' },
  { id: 'cinematic_studio_3_0',     label: 'Cinematic Studio 3.0' },
  { id: 'cinematic_studio_video',   label: 'Cinematic Studio Video' },
  { id: 'cinematic_studio_video_v2', label: 'Cinematic Studio Video V2' },
  { id: 'marketing_studio_video',   label: 'Marketing Studio Video' },
  { id: 'reframe',                  label: 'Reframe' },
];

// Kling-only sub-quality modes (std/pro/4k). The user's "kling 720
// cheap vs 4k default" question maps here.
const KLING_MODES = ['std', 'pro', '4k'] as const;

const ASPECT_RATIOS = ['1:1', '4:5', '9:16', '16:9'] as const;
type AspectRatio = (typeof ASPECT_RATIOS)[number];

// Higgsfield's per-account image-gen cap.
const MAX_VARIANTS = 6;

type Mode = 'image' | 'video';

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
  const [mode, setMode] = useState<Mode>('image');
  const [prompt, setPrompt] = useState(initialPrompt);
  const [model, setModel] = useState(IMAGE_MODELS[0].id);
  const [videoModel, setVideoModel] = useState(VIDEO_MODELS[0].id);
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>(lockAspect ?? initialAspect);
  const [variantsCount, setVariantsCount] = useState<number>(1);
  // Video duration in seconds. Some models cap (veo3_1=8s); the
  // upstream rejection surfaces cleanly. Default 5s matches typical
  // ad-creative length.
  const [duration, setDuration] = useState<number>(5);
  // Kling-specific mode (std / pro / 4k) — the cheap-vs-premium
  // selector. Default `std` because that's the cheapest; 4k is
  // multiples more expensive.
  const [klingMode, setKlingMode] = useState<string>('std');
  // Multi-aspect mode: render the same prompt across all 4 aspects in
  // one Generate click. Disabled when a parent lockAspect is set
  // (PMaxWizard inline forces one aspect per slot). Image-only.
  const [multiAspect, setMultiAspect] = useState(false);
  const [busy, setBusy] = useState(false);
  const [variants, setVariants] = useState<VariantState[]>([]);
  const eventSourcesRef = useRef<EventSource[]>([]);

  // Live cost estimate. Refreshed on model/prompt/duration/mode change
  // (debounced 400ms so each keystroke doesn't shell out). costError
  // carries the upstream "model needs different params" message so
  // the UI can show WHY a cost is missing (e.g. Veo 3 requires an
  // input image — silently displaying "—" was confusing).
  const [costCredits, setCostCredits] = useState<number | null>(null);
  const [costLoading, setCostLoading] = useState(false);
  const [costError, setCostError] = useState<string | null>(null);
  const costAbortRef = useRef<AbortController | null>(null);
  const isKling = mode === 'video' && /^kling/.test(videoModel);

  // Landing-page brief extraction. Operator pastes a campaign's
  // landing page URL → backend runs the 2-stage drafter (decompose +
  // 3 angle variants per visual_director role) → operator picks
  // which angle fits the campaign rotation, that prompt becomes
  // `prompt`.
  const [briefUrl, setBriefUrl] = useState('');
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState<string | null>(null);
  const [briefVariants, setBriefVariants] = useState<BriefVariant[]>([]);

  // Soul library + selection. Fetched lazily when a Soul-aware model
  // is picked. Only `ready` Souls are pickable; pending/training/failed
  // are shown but disabled.
  const activeModelId = mode === 'video' ? videoModel : model;
  const isSoulAware = SOUL_AWARE_MODELS.has(activeModelId);
  const [souls, setSouls] = useState<SoulCharacter[]>([]);
  const [selectedSoulId, setSelectedSoulId] = useState<string>('');

  useEffect(() => {
    if (!isSoulAware) return;
    studioListSouls(accountId)
      .then(setSouls)
      .catch(() => setSouls([]));
  }, [isSoulAware, accountId]);

  useEffect(() => {
    const trimmed = prompt.trim();
    if (!trimmed) {
      setCostCredits(null);
      setCostError(null);
      return;
    }
    const handle = window.setTimeout(() => {
      costAbortRef.current?.abort();
      const ac = new AbortController();
      costAbortRef.current = ac;
      setCostLoading(true);
      setCostError(null);
      const activeModel = mode === 'video' ? videoModel : model;
      studioCostEstimate({
        prompt: trimmed,
        model: activeModel,
        aspect_ratio: lockAspect ?? aspectRatio,
        duration_seconds: mode === 'video' ? duration : undefined,
        mode: isKling ? klingMode : undefined,
      })
        .then((r) => {
          if (ac.signal.aborted) return;
          setCostCredits(r.credits);
          // Soft-failure path: backend returned 200 with credits=null
          // + structured error. Surface the upstream "needs input
          // image / aspect not supported / etc." so the operator
          // knows what's wrong instead of staring at "—".
          if (r.credits === null && r.error_message) {
            setCostError(_summarizeCostError(r.error_message));
          } else {
            setCostError(null);
          }
        })
        .catch((e) => {
          if (ac.signal.aborted) return;
          setCostCredits(null);
          setCostError(e instanceof Error ? e.message : 'cost lookup failed');
        })
        .finally(() => {
          if (!ac.signal.aborted) setCostLoading(false);
        });
    }, 400);
    return () => window.clearTimeout(handle);
  }, [prompt, model, videoModel, mode, aspectRatio, duration, klingMode, lockAspect, isKling]);

  // Pull the operator-actionable line out of higgsfield's multi-line
  // CLI error so the badge tooltip isn't a wall of text.
  function _summarizeCostError(msg: string): string {
    // CLI errors look like:
    //   "Error: Missing required params: input_image
    //    Invalid values: aspect_ratio=1:1 (allowed: 16:9,9:16)
    //    Unknown params: duration"
    const lines = msg.split('\n').filter(Boolean);
    return lines.slice(0, 3).join(' · ').slice(0, 240);
  }

  const handleExtractBrief = async () => {
    const u = briefUrl.trim();
    if (!u || briefLoading) return;
    setBriefLoading(true);
    setBriefError(null);
    setBriefVariants([]);
    try {
      const res = await studioExtractBrief({
        url: u,
        target: mode === 'video' ? 'video' : 'image',
        account_id: accountId,
        campaign_id: campaignId,
      });
      // Surface all 3 variants; operator picks. Fallback to single-
      // prompt swap only if the backend returned the legacy shape
      // (variants empty but drafted_prompt populated — older deploys
      // or a future stage-2 failure).
      if (res.variants && res.variants.length > 0) {
        setBriefVariants(res.variants.filter((v) => v.prompt));
      } else if (res.drafted_prompt) {
        setPrompt(res.drafted_prompt);
      }
    } catch (e) {
      setBriefError(e instanceof Error ? e.message : String(e));
    } finally {
      setBriefLoading(false);
    }
  };

  const pickVariant = (v: BriefVariant) => {
    setPrompt(v.prompt);
    setBriefVariants([]);  // collapse the picker once the operator chooses
  };

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

    setBusy(true);
    setVariants([]);
    eventSourcesRef.current.forEach((es) => es.close());
    eventSourcesRef.current = [];

    let assetIdsToWatch: string[] = [];
    try {
      if (mode === 'video') {
        // Video: single submission per call (no multi-aspect / variants
        // for video — too slow + expensive). Server validates duration
        // against the model's max upstream.
        const body: HiggsfieldGenerateVideoRequest = {
          prompt: trimmed,
          model: videoModel,
          aspect_ratio: lockAspect ?? aspectRatio,
          duration_seconds: duration,
          mode: isKling ? klingMode : undefined,
          soul_id: isSoulAware && selectedSoulId ? selectedSoulId : undefined,
          account_id: accountId,
          campaign_id: campaignId,
        };
        const res = await studioGenerateVideo(body);
        assetIdsToWatch = [res.asset_id];
      } else {
        // Image: same multi-aspect + variants behaviour as before.
        const aspectsToRun: AspectRatio[] = lockAspect
          ? [lockAspect]
          : multiAspect
            ? Array.from(ASPECT_RATIOS)
            : [aspectRatio];
        const variantsPerAspect = multiAspect ? 1 : Math.max(1, variantsCount);
        const total = aspectsToRun.length * variantsPerAspect;
        if (total > MAX_VARIANTS) {
          setBusy(false);
          return;
        }
        const body: HiggsfieldGenerateImageRequest = {
          prompt: trimmed,
          model,
          aspect_ratios: aspectsToRun.slice(),
          variants_per_aspect: variantsPerAspect,
          soul_id: isSoulAware && selectedSoulId ? selectedSoulId : undefined,
          account_id: accountId,
          campaign_id: campaignId,
        };
        const res = await studioGenerateImage(body);
        assetIdsToWatch = res.asset_ids;
      }
      setVariants(
        assetIdsToWatch.map((id) => ({
          asset_id: id,
          status: 'pending',
          url: null,
          error_message: null,
        })),
      );
      assetIdsToWatch.forEach((assetId) => {
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
        <span className="text-xs font-medium">
          {mode === 'video' ? 'Video generation' : 'Image generation'}
        </span>
        {caption && (
          <span className="text-[10px] text-muted-foreground italic">{caption}</span>
        )}
        {/* Image / Video mode toggle — segmented control. PMaxWizard
            slot mode always wants images (videos go in the YouTube ID
            step), so when lockAspect is set we hide the toggle. */}
        {!lockAspect && (
          <div className="ml-auto inline-flex rounded border border-border text-[10px] font-mono">
            <button
              type="button"
              onClick={() => setMode('image')}
              disabled={busy}
              className={cn(
                'px-2 py-0.5 rounded-l transition-colors flex items-center gap-1',
                mode === 'image'
                  ? 'bg-violet-500/20 text-violet-600 dark:text-violet-300'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <ImageGlyph className="h-3 w-3" /> Image
            </button>
            <button
              type="button"
              onClick={() => setMode('video')}
              disabled={busy}
              className={cn(
                'px-2 py-0.5 rounded-r transition-colors flex items-center gap-1',
                mode === 'video'
                  ? 'bg-pink-500/20 text-pink-600 dark:text-pink-300'
                  : 'text-muted-foreground hover:text-foreground',
              )}
              title="Video generation can take 5-10 minutes per clip"
            >
              <VideoIcon className="h-3 w-3" /> Video
            </button>
          </div>
        )}
      </div>

      {/* Landing-page brief extraction. Operator pastes a campaign's
          landing URL, hits Extract, the backend fetches the page and
          asks Claude to draft an on-brand prompt grounded in the
          page's real content. Much faster than writing from scratch
          and the visuals stay aligned with what the page promises. */}
      {!lockAspect && (
        <div className="flex items-center gap-2 text-xs">
          <LinkIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <Input
            value={briefUrl}
            onChange={(e) => setBriefUrl(e.target.value)}
            placeholder="Paste a campaign's landing page URL — Claude will draft a prompt from it"
            disabled={briefLoading || busy}
            className="h-7 text-xs flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleExtractBrief();
              }
            }}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={handleExtractBrief}
            disabled={!briefUrl.trim() || briefLoading || busy}
            className="h-7 gap-1.5 shrink-0"
          >
            {briefLoading ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Wand2 className="h-3 w-3" />
            )}
            {briefLoading ? 'Drafting…' : 'Extract brief'}
          </Button>
        </div>
      )}
      {briefError && (
        <div className="text-[10px] text-red-600 dark:text-red-400 flex items-center gap-1">
          <AlertCircle className="h-3 w-3" /> {briefError}
        </div>
      )}

      {/* Variant picker — appears after Extract returns three angle
          variants. Each card shows the angle name + one-line
          rationale + the prompt preview. Clicking "Use" swaps the
          prompt into the textarea and collapses the picker. Mirrors
          the meta-ads-agent practice of showing 3 angles instead of
          one generic draft. */}
      {briefVariants.length > 0 && (
        <div className="border border-violet-500/30 bg-violet-500/5 rounded-md p-2 flex flex-col gap-1.5">
          <div className="text-[10px] uppercase font-mono text-violet-700 dark:text-violet-300 flex items-center gap-1">
            <Wand2 className="h-3 w-3" />
            Pick an angle — each one is grounded in the page's claim hints + your firm's visual rules
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-1.5">
            {briefVariants.map((v) => (
              <VariantCard key={v.angle} variant={v} onPick={() => pickVariant(v)} />
            ))}
          </div>
        </div>
      )}

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
          {mode === 'video' ? (
            <select
              value={videoModel}
              onChange={(e) => setVideoModel(e.target.value)}
              disabled={busy}
              className="h-7 rounded border border-border bg-background px-2 text-xs"
            >
              {VIDEO_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}{m.maxSeconds ? ` · max ${m.maxSeconds}s` : ''}
                </option>
              ))}
            </select>
          ) : (
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
          )}
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
        {/* Soul picker — only shown when a Soul-aware model is
            selected. Without a ready Soul the model will produce
            random faces; with one it produces the same person
            across every render. Falls back to "no Soul (random face)"
            if the operator hasn't trained any yet. */}
        {isSoulAware && (
          <label className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-mono text-muted-foreground">Soul</span>
            <select
              value={selectedSoulId}
              onChange={(e) => setSelectedSoulId(e.target.value)}
              disabled={busy}
              className="h-7 rounded border border-border bg-background px-2 text-xs max-w-[200px]"
              title="The trained character to render. Train new Souls in the Souls panel."
            >
              <option value="">No Soul (random face)</option>
              {souls
                .filter((s) => s.status === 'ready' && s.soul_id)
                .map((s) => (
                  <option key={s.id} value={s.soul_id ?? ''}>
                    {s.name} · {s.training_model}
                  </option>
                ))}
              {souls.filter((s) => s.status === 'ready').length === 0 && (
                <option disabled value="">(no trained Souls yet)</option>
              )}
            </select>
          </label>
        )}
        {mode === 'image' && !lockAspect && (
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
        {mode === 'image' && (
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
        )}
        {mode === 'video' && isKling && (
          <label className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-mono text-muted-foreground">Quality</span>
            <select
              value={klingMode}
              onChange={(e) => setKlingMode(e.target.value)}
              disabled={busy}
              className="h-7 rounded border border-border bg-background px-2 text-xs font-mono"
              title="Kling render quality. std = cheapest (~720p-equivalent), pro = 1080p, 4k = highest. Cost scales accordingly."
            >
              {KLING_MODES.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>
        )}
        {mode === 'video' && (
          <label className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-mono text-muted-foreground">Duration</span>
            <Input
              type="number"
              min={1}
              max={60}
              value={duration}
              onChange={(e) => setDuration(Math.max(1, Math.min(60, Number(e.target.value) || 1)))}
              disabled={busy}
              className="h-7 w-16 text-xs font-mono"
              title="Seconds. Veo accepts only 4/6/8; Kling caps at 15. Upstream rejects out-of-range values."
            />
            <span className="text-[10px] text-muted-foreground">s</span>
          </label>
        )}
        {/* Live cost badge. When the model rejects our params (Veo 3
            needs --input_image; Wan accepts duration enum strings only)
            the badge turns red and the tooltip surfaces the actual
            upstream error so the operator can switch model or fix
            params instead of staring at "—". */}
        <div
          className={cn(
            'flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded border',
            costError
              ? 'border-red-500/40 text-red-600 dark:text-red-400 bg-red-500/5'
              : costCredits !== null && costCredits > 50
                ? 'border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/5'
                : costCredits !== null
                  ? 'border-green-500/30 text-green-600 dark:text-green-400 bg-green-500/5'
                  : 'border-border text-muted-foreground'
          )}
          title={
            costError
              ? `Model rejected the params: ${costError}`
              : costCredits !== null
                ? `Estimated cost: ${costCredits} Higgsfield credits per generation. Pick a budget model (Veo Lite, Kling std) to lower this.`
                : 'Cost will appear once you have a prompt + model selected.'
          }
        >
          {costError ? (
            <><AlertCircle className="h-3 w-3" /> incompatible</>
          ) : (
            <>≈ {costLoading ? '…' : costCredits ?? '—'} credits</>
          )}
        </div>
        <Button
          onClick={submit}
          disabled={busy || !prompt.trim()}
          className="ml-auto gap-1.5"
          size="sm"
        >
          {busy ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {mode === 'video' ? 'Rendering…' : `${settledCount}/${variants.length || '…'}`}
            </>
          ) : (
            <>
              <Sparkles className="h-3.5 w-3.5" />
              {mode === 'video'
                ? `Generate ${duration}s video`
                : multiAspect ? 'Generate all 4' : variantsCount > 1 ? `Generate ${variantsCount}` : 'Generate'}
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
    const url = variant.url || '';
    const isVideo = /\.(mp4|mov|webm)(\?|$)/i.test(url);
    return (
      <a
        href={url || '#'}
        target="_blank"
        rel="noreferrer"
        className="aspect-square rounded border border-green-500/40 overflow-hidden bg-secondary/30 block group relative"
        title={`#${index + 1} ${isVideo ? 'video' : 'image'} saved to library`}
      >
        {isVideo ? (
          // Embed as a poster preview so the operator can scrub /
          // confirm without leaving the page. `metadata` preload keeps
          // bandwidth low until they hover.
          <video
            src={url}
            className="w-full h-full object-cover"
            preload="metadata"
            muted
            playsInline
          />
        ) : (
          <img src={url} alt="" className="w-full h-full object-cover" loading="lazy" />
        )}
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

function VariantCard({ variant, onPick }: { variant: BriefVariant; onPick: () => void }) {
  // Color-code each angle so the operator can tell them apart at a
  // glance after a few sessions. Colors echo the underlying frame:
  // problem-led = amber (decision/tension), aspirational = green
  // (settled outcome), social-proof = blue (institutional trust).
  const angleColors: Record<string, string> = {
    'problem-led':   'border-amber-500/40 bg-amber-500/5',
    'aspirational':  'border-green-500/40 bg-green-500/5',
    'social-proof':  'border-blue-500/40 bg-blue-500/5',
  };
  const accent = angleColors[variant.angle] || 'border-border bg-secondary/30';
  return (
    <div className={cn('border rounded p-2 flex flex-col gap-1.5 text-xs', accent)}>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase font-semibold">{variant.angle}</span>
        <Button
          size="sm"
          variant="outline"
          onClick={onPick}
          className="h-5 text-[10px] px-2"
        >
          Use
        </Button>
      </div>
      {variant.rationale && (
        <p className="text-[10px] text-muted-foreground italic line-clamp-2" title={variant.rationale}>
          {variant.rationale}
        </p>
      )}
      <p className="text-[11px] leading-snug line-clamp-6" title={variant.prompt}>
        {variant.prompt}
      </p>
    </div>
  );
}
