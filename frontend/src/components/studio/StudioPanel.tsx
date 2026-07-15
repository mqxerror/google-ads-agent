/**
 * StudioPanel — the shared creative engine panel (Epic 12, story 12.1).
 *
 * One slide-over (right, 480px, like the chat panel) that any flow can
 * open in context: PMax wizard image slots, video thumbnail, copy
 * drafting — later Search ads, Shopping, chat. Three modes:
 *
 *   image  — prompt → Higgsfield image variants → "Use in slot"
 *   video  — prompt → one Higgsfield clip → "Use in slot"
 *   copy   — intent → host-injected drafter → "Use in step"
 *
 * DECOUPLING (approved brief addendum): this component knows nothing
 * about Google Ads. The `context` prop is the ONLY coupling — hosts
 * pass {campaignId, brief, businessName, finalUrl, slot, aspect} and
 * receive the chosen asset back through `onUse`. Copy drafting is
 * host-injected (`onDraftCopy`) for the same reason: the panel never
 * calls a campaign-specific endpoint itself.
 *
 * Keep the host's instance MOUNTED and toggle `open` — jobs keep
 * streaming while the panel is off-screen and finished results are
 * waiting on reopen (brief §7: panel survives close/reopen).
 *
 * Design: restrained per DESIGN.md — tokens only, one accent, quiet
 * rows, no color sprawl. Advanced params live behind one "Tune"
 * disclosure (brief §5: progressive disclosure, never a wall of knobs).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle, Check, ChevronDown, ChevronRight, Loader2,
  Lock, Music, Sparkles, Wand2, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ModelPicker, { useModelCatalog } from '@/components/video/ModelPicker';
import { useStudioJobs, isTerminal, type JobVariant } from '@/components/studio/useStudioJobs';
import {
  studioCostEstimate,
  studioExtractBrief,
  studioGenerateImage,
  studioGenerateVideo,
  studioGetJob,
  studioListSouls,
  videoEngineEstimate,
  videoEngineRender,
  videoEngineRenderStatus,
  type BriefVariant,
  type SoulCharacter,
  type StudioJobStatus,
  type StudioModelInfo,
} from '@/lib/api';

export type StudioPanelMode = 'image' | 'video' | 'copy';

/** The ONLY coupling between the panel and its host flow. */
export interface StudioPanelContext {
  campaignId?: string;
  brief?: string;
  businessName?: string;
  finalUrl?: string;
  /** Plain-language slot label, e.g. "Square marketing image". */
  slot?: string;
  /** Locks the aspect selector, e.g. "1:1". */
  aspect?: string;
}

export interface CopyDraftResult {
  headlines?: string[];
  long_headlines?: string[];
  descriptions?: string[];
}

/** Host-pushed prefill: a preset prompt (Marketing Studio hooks), a
 * model to preselect, and/or a Soul to lock in (Soul test-generate).
 * Applied when the object reference changes, so hosts pass a fresh
 * object per pick. */
export interface StudioPanelPreset {
  prompt?: string;
  model?: string;
  soulId?: string;
}

interface StudioPanelProps {
  open: boolean;
  onClose: () => void;
  mode: StudioPanelMode;
  accountId: string;
  context?: StudioPanelContext;
  /** Hub hosts pass this to get image/video tabs in the panel header
   * (the hub has one "Create" button, not one per mode). */
  onModeChange?: (mode: 'image' | 'video') => void;
  /** Prefill from presets / Soul test-generate. */
  preset?: StudioPanelPreset;
  /** Called with the chosen asset when the operator clicks "Use in slot". */
  onUse?: (asset: StudioJobStatus) => void;
  /** Fires whenever a watched job reaches a terminal state — hub hosts
   * refresh the library from this. */
  onJobSettled?: (asset: StudioJobStatus) => void;
  /** copy mode — host-injected drafter (keeps the panel decoupled). */
  onDraftCopy?: (intent: string) => Promise<CopyDraftResult>;
  onUseCopy?: (result: CopyDraftResult) => void;
}

const FALLBACK_ASPECTS = ['1:1', '4:5', '9:16', '16:9'];
const CREDITS_RX = /credit|balance|insufficient|quota|top.?up/i;

export default function StudioPanel({
  open, onClose, mode, accountId, context, onModeChange, preset,
  onUse, onJobSettled, onDraftCopy, onUseCopy,
}: StudioPanelProps) {
  const [prompt, setPrompt] = useState('');
  const [model, setModel] = useState('');
  const [modelInfo, setModelInfo] = useState<StudioModelInfo | undefined>(undefined);
  const [aspect, setAspect] = useState(context?.aspect || '1:1');
  const [variantsCount, setVariantsCount] = useState(1);
  const [duration, setDuration] = useState(5);
  const [klingMode, setKlingMode] = useState('std');
  const [veoQuality, setVeoQuality] = useState('');
  const [soulId, setSoulId] = useState('');
  const [tuneOpen, setTuneOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [usePending, setUsePending] = useState(false);

  // ── Soul talking intro (Epic 11 P2) — video mode only ──────────
  // Presenter-style segment from a trained Soul, rendered ahead of
  // the clip via the video-engine timeline. Motion + voiceover, NO
  // lip-sync (§1a fallback — see backend services/video_engine.py).
  const [talkingIntro, setTalkingIntro] = useState(false);
  const [introSoulId, setIntroSoulId] = useState('');
  const [introScript, setIntroScript] = useState('');
  const [engineJobId, setEngineJobId] = useState<string | null>(null);
  const [engineMsg, setEngineMsg] = useState<string | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const engineBusy = engineJobId !== null;

  // ── Finished video (video-engine planner) — video mode only ────
  // Sub-mode toggle. "Single clip" keeps today's behavior verbatim;
  // "Finished video" hands a target length + model + prompt to the
  // backend planner, which builds N Higgsfield clips and stitches one
  // MP4 (music bed + VO optional). Default 'single' so nothing regresses.
  const [videoSubMode, setVideoSubMode] = useState<'single' | 'finished'>('single');
  const [targetSeconds, setTargetSeconds] = useState<15 | 30 | 60>(30);
  const [musicOn, setMusicOn] = useState(false);
  const [voOn, setVoOn] = useState(false);
  const [musicFilename, setMusicFilename] = useState<string | null>(null);
  const [voScript, setVoScript] = useState('');
  const [showMusicPicker, setShowMusicPicker] = useState(false);

  const genKind: 'image' | 'video' = mode === 'video' ? 'video' : 'image';
  const finishedActive = genKind === 'video' && videoSubMode === 'finished';
  const { models } = useModelCatalog(genKind);
  const jobs = useStudioJobs(onJobSettled);

  // ── context-driven state ────────────────────────────────────────
  useEffect(() => {
    if (context?.aspect) setAspect(context.aspect);
  }, [context?.aspect]);

  // ── preset prefill (Marketing Studio hooks / Soul test-generate) ─
  // The model pick waits for the catalog: until then it parks in
  // pendingModel; ModelPicker's own default-select runs first and is
  // then overridden, which is fine — both settle on the preset.
  const [pendingModel, setPendingModel] = useState<string | null>(null);
  useEffect(() => {
    if (!preset) return;
    if (preset.prompt) setPrompt(preset.prompt);
    if (preset.soulId) setSoulId(preset.soulId);
    if (preset.model) setPendingModel(preset.model);
  }, [preset]);
  useEffect(() => {
    if (!pendingModel || !models.length) return;
    const found = models.find((m) => m.id === pendingModel);
    if (found) {
      setModel(found.id);
      setModelInfo(found);
    }
    setPendingModel(null); // unknown id → keep whatever is selected
  }, [pendingModel, models]);

  // Effective aspect: locked from context, else clamped to what the
  // selected model accepts (catalog constraint).
  const modelAspects = modelInfo?.constraints?.aspect_ratios?.length
    ? modelInfo.constraints.aspect_ratios
    : FALLBACK_ASPECTS;
  const lockedAspect = context?.aspect;
  const effectiveAspect = lockedAspect ?? (modelAspects.includes(aspect) ? aspect : modelAspects[0]);

  // Finished-video helpers. maxClip mirrors the backend planner: enum →
  // longest legal duration, int → max_duration, null-duration → 1 clip.
  // estClips = ceil(target / maxClip) so the "≈ N clips" hint matches
  // what the planner will build.
  const maxClip = useMemo(() => {
    const c = modelInfo?.constraints;
    if (c?.duration_type === 'enum' && c.durations?.length) return Math.max(...c.durations);
    if (c?.duration_type === 'int' && c.max_duration) return c.max_duration;
    return null; // null-duration model → one clip covers the whole target
  }, [modelInfo]);
  const estClips = maxClip ? Math.max(1, Math.ceil(targetSeconds / maxClip)) : 1;
  const modelOrigin = model
    ? (/^(kling|seedance|minimax|hailuo|wan)/.test(model) ? 'Chinese'
      : /^(veo|grok)/.test(model) ? 'American'
      : model === 'soul_cast' || /soul/.test(model) ? 'Soul' : null)
    : null;

  const handleModelChange = useCallback((id: string, info: StudioModelInfo | undefined) => {
    setModel(id);
    setModelInfo(info);
    // Snap duration into the model's legal values so the CLI never
    // rejects at render time (Veo enum vs Kling int — server catalog).
    const c = info?.constraints;
    if (c?.duration_type === 'enum' && c.durations?.length) {
      setDuration((d) => c.durations!.reduce((best, cur) =>
        Math.abs(cur - d) < Math.abs(best - d) ? cur : best, c.durations![0]));
    } else if (c?.duration_type === 'int' && c.max_duration) {
      setDuration((d) => Math.min(d, c.max_duration!));
    }
  }, []);

  // ── soul library (soul-aware model OR the talking-intro toggle) ─
  const supportsSoul = !!modelInfo?.constraints?.supports_soul;
  const wantsSouls = supportsSoul || (genKind === 'video' && talkingIntro);
  const [souls, setSouls] = useState<SoulCharacter[]>([]);
  useEffect(() => {
    if (!wantsSouls) return;
    studioListSouls(accountId).then(setSouls).catch(() => setSouls([]));
  }, [wantsSouls, accountId]);
  const readySouls = souls.filter((s) => s.status === 'ready' && s.soul_id);
  const introActive = genKind === 'video' && talkingIntro && !!introSoulId;

  // ── finished-video audio pickers (mirror VideoCreator's sources) ─
  // Music from the account's audio asset library; voices from the TTS
  // voice list. Both are direct fetches (same endpoints VideoCreator
  // uses); loaded lazily when the finished-video audio controls appear.
  const [libraryAudio, setLibraryAudio] = useState<Array<{ id: string; filename: string; url: string }>>([]);
  const [audioLoading, setAudioLoading] = useState(false);
  useEffect(() => {
    if (!showMusicPicker || !accountId) return;
    let cancelled = false;
    setAudioLoading(true);
    const qs = new URLSearchParams({ account_id: accountId, asset_type: 'audio', limit: '60' });
    fetch(`/api/assets?${qs}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((rows) => { if (!cancelled) setLibraryAudio(rows); })
      .catch(() => { if (!cancelled) setLibraryAudio([]); })
      .finally(() => { if (!cancelled) setAudioLoading(false); });
    return () => { cancelled = true; };
  }, [showMusicPicker, accountId]);

  const [voices, setVoices] = useState<Array<{ voice_id: string; name: string }>>([]);
  const [voiceId, setVoiceId] = useState('');
  useEffect(() => {
    if (!finishedActive || !voOn || voices.length) return;
    let cancelled = false;
    fetch('/api/video/voices')
      .then((r) => (r.ok ? r.json() : []))
      .then((vo: Array<{ voice_id: string; name: string }>) => {
        if (cancelled) return;
        setVoices(vo);
        const sarah = vo.find((v) => v.name === 'Sarah');
        if (sarah) setVoiceId((id) => id || sarah.voice_id);
        else if (vo[0]) setVoiceId((id) => id || vo[0].voice_id);
      })
      .catch(() => { if (!cancelled) setVoices([]); });
    return () => { cancelled = true; };
  }, [finishedActive, voOn, voices.length]);

  // ── live cost (debounced; soft errors surfaced inline) ─────────
  const [costCredits, setCostCredits] = useState<number | null>(null);
  // Timeline estimates can be partial (a stage the CLI couldn't
  // price) — shown as "N+" instead of pretending N is the total.
  const [costPartial, setCostPartial] = useState(false);
  const [costLoading, setCostLoading] = useState(false);
  const [costError, setCostError] = useState<string | null>(null);
  const costAbortRef = useRef<AbortController | null>(null);
  const isKling = genKind === 'video' && /^kling/.test(model);

  useEffect(() => {
    if (mode === 'copy') return;
    const trimmed = prompt.trim();
    if (!trimmed || !model) {
      setCostCredits(null);
      setCostError(null);
      return;
    }
    const handle = window.setTimeout(() => {
      costAbortRef.current?.abort();
      const ac = new AbortController();
      costAbortRef.current = ac;
      setCostLoading(true);
      // Finished video → the planner prices N clips from the target
      // length; talking intro → summed soul+motion+clip timeline; both
      // replace the single-clip lookup so the number by Generate covers
      // everything about to burn.
      const lookup = finishedActive
        ? videoEngineEstimate({
            target_seconds: targetSeconds,
            model_id: model,
            prompt: trimmed,
            aspect: effectiveAspect,
          }).then((r) => {
            if (ac.signal.aborted) return;
            setCostCredits(r.total_credits);
            setCostPartial(r.unknown_count > 0);
            setCostError(null);
          })
        : introActive
        ? videoEngineEstimate({
            segments: [
              { engine: 'soul', soul_id: introSoulId, script: introScript.trim() || 'Intro' },
              { engine: 'higgsfield', prompt: trimmed, model, duration },
            ],
            aspect: effectiveAspect,
          }).then((r) => {
            if (ac.signal.aborted) return;
            setCostCredits(r.total_credits);
            setCostPartial(r.unknown_count > 0);
            setCostError(null);
          })
        : studioCostEstimate({
            prompt: trimmed,
            model,
            aspect_ratio: effectiveAspect,
            duration_seconds: genKind === 'video' ? duration : undefined,
            mode: isKling ? klingMode : undefined,
          }).then((r) => {
            if (ac.signal.aborted) return;
            setCostCredits(r.credits);
            setCostPartial(false);
            setCostError(r.credits === null && r.error_message
              ? r.error_message.split('\n').filter(Boolean).slice(0, 2).join(' · ').slice(0, 200)
              : null);
          });
      lookup
        .catch((e) => {
          if (ac.signal.aborted) return;
          setCostCredits(null);
          setCostError(e instanceof Error ? e.message : 'cost lookup failed');
        })
        .finally(() => { if (!ac.signal.aborted) setCostLoading(false); });
    }, 400);
    return () => window.clearTimeout(handle);
  }, [prompt, model, effectiveAspect, duration, klingMode, isKling, genKind, mode, introActive, introSoulId, introScript, finishedActive, targetSeconds]);

  // ── Enhance (Visual Director) — same 2-stage drafter as Studio ──
  const [enhancing, setEnhancing] = useState(false);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);
  const [angleVariants, setAngleVariants] = useState<BriefVariant[]>([]);
  const canEnhance = !!(prompt.trim() || context?.brief?.trim() || context?.businessName?.trim());

  const handleEnhance = async () => {
    if (enhancing || busy || !canEnhance) return;
    const parts: string[] = [];
    const idea = prompt.trim();
    if (idea) parts.push(`Operator's rough idea for the creative: ${idea}`);
    if (context?.brief?.trim()) parts.push(`Campaign brief: ${context.brief.trim()}`);
    if (context?.businessName?.trim()) parts.push(`Business name: ${context.businessName.trim()}`);
    if (context?.finalUrl?.trim()) parts.push(`Landing page URL: ${context.finalUrl.trim()}`);
    if (context?.slot) {
      parts.push(`Asset slot: ${context.slot}${context.aspect ? ` (${context.aspect} aspect)` : ''}.`);
    }
    setEnhancing(true);
    setEnhanceError(null);
    setAngleVariants([]);
    try {
      const res = await studioExtractBrief({
        context: parts.join('\n'),
        target: genKind,
        account_id: accountId,
        campaign_id: context?.campaignId,
      });
      if (res.variants?.length) setAngleVariants(res.variants.filter((v) => v.prompt));
      else if (res.drafted_prompt) setPrompt(res.drafted_prompt);
    } catch (e) {
      setEnhanceError(e instanceof Error ? e.message : String(e));
    } finally {
      setEnhancing(false);
    }
  };

  // ── Generate ────────────────────────────────────────────────────
  const submit = async () => {
    const trimmed = prompt.trim();
    if (!trimmed || busy || engineBusy || !model) return;
    setBusy(true);
    setSelectedId(null);
    try {
      if (finishedActive) {
        // Planner-built finished video: backend derives N clips from the
        // target length + model + prompt, stitches one MP4, and layers
        // the chosen audio. Same job+poll path as the talking-intro render
        // (the finished asset joins the tiles below on completion).
        setEngineError(null);
        const res = await videoEngineRender({
          account_id: accountId,
          campaign_id: context?.campaignId,
          target_seconds: targetSeconds,
          model_id: model,
          prompt: trimmed,
          aspect: effectiveAspect,
          quality: 'draft',
          music_filename: musicOn && musicFilename ? musicFilename : undefined,
          voiceover_script: voOn && voScript.trim() ? voScript.trim() : undefined,
          voice_id: voOn && voiceId ? voiceId : undefined,
          brief: `Finished video — ${targetSeconds}s ${model}`,
        });
        setEngineJobId(res.job_id);
        setEngineMsg(`Planning ${estClips} clip${estClips > 1 ? 's' : ''} + stitching… can take several minutes.`);
        return;
      }
      if (genKind === 'video' && introActive) {
        // Segment-timeline render: Soul intro + this clip in one MP4
        // (job+poll — the finished asset joins the tiles below).
        setEngineError(null);
        const res = await videoEngineRender({
          account_id: accountId,
          campaign_id: context?.campaignId,
          segments: [
            { engine: 'soul', soul_id: introSoulId, script: introScript.trim() },
            { engine: 'higgsfield', prompt: trimmed, model, duration, speak: '' },
          ],
          aspect: effectiveAspect,
          quality: 'draft',
          brief: `Soul intro + AI clip${context?.businessName ? ` — ${context.businessName}` : ''}`,
        });
        setEngineJobId(res.job_id);
        setEngineMsg('Rendering intro + clip… can take several minutes.');
        return;
      }
      if (genKind === 'video') {
        const res = await studioGenerateVideo({
          prompt: trimmed,
          model,
          aspect_ratio: effectiveAspect,
          duration_seconds: duration,
          mode: isKling ? klingMode : undefined,
          quality: veoQuality || undefined,
          soul_id: supportsSoul && soulId ? soulId : undefined,
          account_id: accountId,
          campaign_id: context?.campaignId,
        });
        jobs.watch([res.asset_id]);
      } else {
        const res = await studioGenerateImage({
          prompt: trimmed,
          model,
          aspect_ratios: [effectiveAspect],
          variants_per_aspect: Math.min(6, Math.max(1, variantsCount)),
          soul_id: supportsSoul && soulId ? soulId : undefined,
          account_id: accountId,
          campaign_id: context?.campaignId,
        });
        jobs.watch(res.asset_ids);
      }
    } catch (e) {
      jobs.failSubmit(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  /** Per-item retry: resubmit a single job with the same params and
   * swap the failed tile for the fresh one. */
  const retryOne = async (failedId: string) => {
    const trimmed = prompt.trim();
    if (!trimmed || !model) return;
    try {
      if (genKind === 'video') {
        const res = await studioGenerateVideo({
          prompt: trimmed, model, aspect_ratio: effectiveAspect,
          duration_seconds: duration,
          mode: isKling ? klingMode : undefined,
          soul_id: supportsSoul && soulId ? soulId : undefined,
          account_id: accountId, campaign_id: context?.campaignId,
        });
        jobs.watchMore([res.asset_id], [failedId]);
      } else {
        const res = await studioGenerateImage({
          prompt: trimmed, model, aspect_ratios: [effectiveAspect],
          variants_per_aspect: 1,
          soul_id: supportsSoul && soulId ? soulId : undefined,
          account_id: accountId, campaign_id: context?.campaignId,
        });
        jobs.watchMore(res.asset_ids, [failedId]);
      }
    } catch { /* tile keeps its error state */ }
  };

  // Poll the engine render job; on done, hand the finished asset to
  // the normal job watcher so it appears as a completed result tile
  // (the row is written by record_generated_video, so studioGetJob
  // reconciles it instantly). Panel stays mounted while closed, so
  // renders survive close/reopen like every other job here.
  useEffect(() => {
    if (!engineJobId) return;
    const startedAt = Date.now();
    let cancelled = false;
    const handle = window.setInterval(async () => {
      if (cancelled) return;
      if (Date.now() - startedAt > 20 * 60_000) {
        setEngineJobId(null);
        setEngineMsg(null);
        setEngineError('Render timed out after 20 minutes — check the Studio library; it may still finish.');
        return;
      }
      try {
        const job = await videoEngineRenderStatus(engineJobId);
        if (cancelled) return;
        if (job.status === 'done' && job.asset_id) {
          setEngineJobId(null);
          setEngineMsg(null);
          jobs.watch([job.asset_id]);
        } else if (job.status === 'error') {
          setEngineJobId(null);
          setEngineMsg(null);
          setEngineError(job.message || 'render failed');
        } else if (job.message) {
          setEngineMsg(job.message);
        }
      } catch { /* transient — next tick retries */ }
    }, 3000);
    return () => { cancelled = true; window.clearInterval(handle); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [engineJobId]);

  const handleUse = async () => {
    if (!selectedId || !onUse) return;
    setUsePending(true);
    try {
      const asset = await studioGetJob(selectedId);
      onUse(asset);
      onClose();
    } catch { /* keep the panel open; operator can retry */ }
    finally { setUsePending(false); }
  };

  // ── copy mode ───────────────────────────────────────────────────
  const [copyBusy, setCopyBusy] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copyResult, setCopyResult] = useState<CopyDraftResult | null>(null);

  const draftCopy = async () => {
    if (!onDraftCopy || copyBusy) return;
    setCopyBusy(true);
    setCopyError(null);
    try {
      const result = await onDraftCopy(prompt.trim());
      setCopyResult(result);
    } catch (e) {
      setCopyError(e instanceof Error ? e.message : String(e));
    } finally {
      setCopyBusy(false);
    }
  };

  // ── chrome ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const readyCount = jobs.variants.filter((v) => v.status === 'completed').length;
  const emptyCredits = useMemo(
    () => jobs.variants.some((v) => v.error_message && CREDITS_RX.test(v.error_message))
      || (costError !== null && CREDITS_RX.test(costError)),
    [jobs.variants, costError],
  );

  const title = mode === 'copy' ? 'Draft copy' : mode === 'video' ? 'Create video' : 'Generate image';
  const placeholder = mode === 'copy'
    ? 'Anything specific the copy should emphasize? (optional — the brief and landing page already feed the draft)'
    : `Describe the ${context?.slot ? context.slot.toLowerCase() : genKind} you need${context?.businessName ? ` for ${context.businessName}` : ''}, or leave a rough idea and press Enhance.`;

  return (
    <>
      {/* Backdrop — click closes; panel state survives (stays mounted). */}
      <div
        className={cn(
          'fixed inset-0 z-40 bg-black/20 transition-opacity duration-200',
          open ? 'opacity-100' : 'opacity-0 pointer-events-none',
        )}
        onClick={onClose}
        aria-hidden
      />
      <aside
        className={cn(
          'fixed top-0 right-0 z-50 h-full w-[480px] max-w-[95vw] bg-card border-l border-border',
          'flex flex-col shadow-xl transition-transform duration-200',
          open ? 'translate-x-0' : 'translate-x-full pointer-events-none',
        )}
        role="dialog"
        aria-label={title}
      >
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
          <Sparkles className="h-4 w-4 text-primary" />
          {onModeChange && mode !== 'copy' ? (
            // Hub host: one Create button outside, image/video tabs here.
            <div className="inline-flex rounded-md border border-border p-0.5 gap-0.5">
              {(['image', 'video'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => onModeChange(m)}
                  className={cn(
                    'px-2 py-0.5 rounded text-xs capitalize transition-colors',
                    mode === m ? 'bg-accent-soft text-accent font-medium' : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {m}
                </button>
              ))}
            </div>
          ) : (
            <span className="text-sm font-semibold">{title}</span>
          )}
          {context?.slot && (
            <span className="text-[10px] text-muted-foreground bg-secondary rounded-full px-2 py-0.5">
              {context.slot}
            </span>
          )}
          {readyCount > 0 && (
            <span className="text-[10px] text-success">{readyCount} ready</span>
          )}
          <button onClick={onClose} className="ml-auto p-1 hover:bg-secondary rounded" aria-label="Close panel">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {/* Intent input */}
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={placeholder}
            rows={3}
            disabled={busy || copyBusy}
            className="w-full rounded-md bg-secondary/40 border border-border px-2.5 py-2 text-sm resize-none disabled:opacity-50 placeholder:text-muted-foreground/60"
          />

          {mode !== 'copy' && (
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-muted-foreground leading-snug">
                Enhance drafts 3 prompt angles from your idea and the campaign brief.
              </span>
              <Button
                size="sm" variant="outline" onClick={handleEnhance}
                disabled={enhancing || busy || !canEnhance}
                className="h-7 gap-1.5 shrink-0"
              >
                {enhancing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                {enhancing ? 'Enhancing…' : 'Enhance (Visual Director)'}
              </Button>
            </div>
          )}
          {enhanceError && (
            <p className="text-[10px] text-danger flex items-center gap-1">
              <AlertCircle className="h-3 w-3 shrink-0" /> {enhanceError}
            </p>
          )}

          {/* Video sub-mode: Single clip (today's behavior) vs Finished
              video (planner stitches N clips into one MP4). */}
          {mode === 'video' && (
            <div className="inline-flex rounded-md border border-border p-0.5 gap-0.5">
              {([['single', 'Single clip'], ['finished', 'Finished video']] as const).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setVideoSubMode(m)}
                  disabled={busy || engineBusy}
                  className={cn(
                    'px-2.5 py-0.5 rounded text-xs transition-colors disabled:opacity-50',
                    videoSubMode === m ? 'bg-accent-soft text-accent font-medium' : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          )}

          {/* Finished video — target length + flexible audio. Model +
              aspect live in the bottom row (shared with single-clip). */}
          {finishedActive && (
            <div className="border border-border rounded-md px-3 py-2.5 space-y-3">
              {/* Target length */}
              <div className="space-y-1.5">
                <span className="text-[10px] uppercase font-mono text-muted-foreground">Length</span>
                <div className="flex items-center gap-2">
                  <div className="inline-flex rounded-md border border-border p-0.5 gap-0.5">
                    {([15, 30, 60] as const).map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setTargetSeconds(s)}
                        disabled={busy || engineBusy}
                        className={cn(
                          'px-2.5 py-0.5 rounded text-xs font-mono transition-colors disabled:opacity-50',
                          targetSeconds === s ? 'bg-accent-soft text-accent font-medium' : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        {s}s
                      </button>
                    ))}
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    ≈ {estClips} clip{estClips > 1 ? 's' : ''}
                  </span>
                </div>
              </div>

              {/* Flexible audio: music bed and/or voiceover (either/both/none) */}
              <div className="space-y-2">
                <span className="text-[10px] uppercase font-mono text-muted-foreground">Audio</span>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
                    <input type="checkbox" checked={musicOn} disabled={busy || engineBusy}
                      onChange={(e) => setMusicOn(e.target.checked)} />
                    Music bed
                  </label>
                  <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
                    <input type="checkbox" checked={voOn} disabled={busy || engineBusy}
                      onChange={(e) => setVoOn(e.target.checked)} />
                    Voiceover
                  </label>
                </div>

                {musicOn && (
                  <div className="flex items-center gap-2">
                    {musicFilename ? (
                      <span className="inline-flex items-center gap-1 h-7 rounded border border-border bg-secondary/40 px-2 text-[11px]">
                        <Music className="h-3 w-3" />
                        <span className="truncate max-w-[160px]">{musicFilename}</span>
                        <button type="button" onClick={() => setMusicFilename(null)} disabled={busy || engineBusy}
                          className="ml-0.5 text-muted-foreground hover:text-foreground" aria-label="Remove music">
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ) : (
                      <Button size="sm" variant="outline" className="h-7 gap-1.5"
                        onClick={() => setShowMusicPicker(true)} disabled={busy || engineBusy}>
                        <Music className="h-3 w-3" /> Pick music
                      </Button>
                    )}
                  </div>
                )}

                {voOn && (
                  <div className="space-y-1.5">
                    <textarea
                      value={voScript}
                      onChange={(e) => setVoScript(e.target.value)}
                      rows={2}
                      disabled={busy || engineBusy}
                      placeholder="Voiceover script — the narration read over the finished video."
                      className="w-full rounded-md bg-secondary/40 border border-border px-2.5 py-1.5 text-xs resize-none disabled:opacity-50 placeholder:text-muted-foreground/60"
                    />
                    {voices.length > 0 && (
                      <select
                        value={voiceId}
                        onChange={(e) => setVoiceId(e.target.value)}
                        disabled={busy || engineBusy}
                        className="h-7 rounded border border-border bg-background px-2 text-xs disabled:opacity-50"
                      >
                        {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
                      </select>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Soul talking intro (Epic 11 P2). Honest copy — the §1a
              fallback is motion + voiceover, NOT lip-sync. Single-clip
              only — the finished-video planner owns its own audio. */}
          {mode === 'video' && videoSubMode === 'single' && (
            <div className="border border-border rounded-md px-3 py-2 space-y-2">
              <label className="flex items-center gap-2 text-xs cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={talkingIntro}
                  onChange={(e) => setTalkingIntro(e.target.checked)}
                  disabled={busy || engineBusy}
                />
                <span className="font-medium">Add talking intro (Soul presenter)</span>
              </label>
              {talkingIntro && (
                <>
                  <select
                    value={introSoulId}
                    onChange={(e) => setIntroSoulId(e.target.value)}
                    disabled={busy || engineBusy || !readySouls.length}
                    className="h-7 w-full rounded border border-border bg-background px-2 text-xs disabled:opacity-50"
                  >
                    <option value="">{readySouls.length ? 'Pick a ready Soul…' : 'No ready Soul yet'}</option>
                    {readySouls.map((s) => (
                      <option key={s.id} value={s.soul_id ?? ''}>{s.name}</option>
                    ))}
                  </select>
                  {!readySouls.length && (
                    <p className="text-[10px] text-muted-foreground">
                      Train one in Studio → Souls first (5-15 min), then it appears here.
                    </p>
                  )}
                  <textarea
                    value={introScript}
                    onChange={(e) => setIntroScript(e.target.value)}
                    rows={2}
                    disabled={busy || engineBusy}
                    placeholder="Intro line the presenter speaks (8-20 words)"
                    className="w-full rounded-md bg-secondary/40 border border-border px-2.5 py-1.5 text-xs resize-none disabled:opacity-50 placeholder:text-muted-foreground/60"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Presenter-style: your Soul on camera with motion and a voiceover of
                    this line — no lip-sync. Renders as intro + clip in one video; the
                    intro clip is cached, so re-renders are free.
                  </p>
                </>
              )}
            </div>
          )}

          {/* 3-angle picker */}
          {angleVariants.length > 0 && (
            <div className="border border-border rounded-md divide-y divide-border">
              {angleVariants.map((v) => (
                <button
                  key={v.angle}
                  type="button"
                  onClick={() => { setPrompt(v.prompt); setAngleVariants([]); }}
                  className="w-full text-left px-3 py-2 hover:bg-secondary/50 transition-colors block"
                  title={v.prompt}
                >
                  <span className="text-[10px] uppercase font-mono font-semibold">{v.angle}</span>
                  {v.rationale && (
                    <span className="text-[10px] text-muted-foreground italic ml-2">{v.rationale}</span>
                  )}
                  <p className="text-[11px] leading-snug line-clamp-3 mt-0.5">{v.prompt}</p>
                </button>
              ))}
            </div>
          )}

          {/* Results */}
          {mode !== 'copy' && jobs.variants.length > 0 && (
            <div className={cn('grid gap-2', genKind === 'video' ? 'grid-cols-1' : 'grid-cols-3')}>
              {jobs.variants.map((v, i) => (
                <ResultTile
                  key={v.asset_id}
                  variant={v}
                  index={i}
                  video={genKind === 'video'}
                  selected={selectedId === v.asset_id}
                  onSelect={() => setSelectedId(v.asset_id === selectedId ? null : v.asset_id)}
                  onRetry={() => retryOne(v.asset_id)}
                />
              ))}
            </div>
          )}
          {mode !== 'copy' && engineBusy && engineMsg && (
            <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin shrink-0" /> {engineMsg}
            </p>
          )}
          {mode !== 'copy' && engineError && (
            <p className="text-[11px] text-danger flex items-center gap-1">
              <AlertCircle className="h-3 w-3 shrink-0" /> {engineError}
            </p>
          )}
          {mode !== 'copy' && emptyCredits && (
            <p className="text-[11px] text-warning flex items-center gap-1.5">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              Looks like the Higgsfield balance is low.&nbsp;
              <a href="https://higgsfield.ai/" target="_blank" rel="noreferrer" className="underline hover:text-foreground">
                Top up credits
              </a>
            </p>
          )}
          {mode !== 'copy' && jobs.variants.length === 0 && (
            <p className="text-[11px] text-muted-foreground">
              {context?.slot
                ? `Results land here, then "Use in slot" fills ${context.slot.toLowerCase()} directly.`
                : 'Results stream in here as they finish.'}
            </p>
          )}

          {/* Copy mode body */}
          {mode === 'copy' && (
            <div className="space-y-3">
              <Button size="sm" onClick={draftCopy} disabled={copyBusy || !onDraftCopy} className="gap-1.5">
                {copyBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                {copyBusy ? 'Drafting… 1-3 min (reads your landing page)' : 'Draft with Creative Director'}
              </Button>
              {copyError && (
                <p className="text-[11px] text-danger flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" /> {copyError}
                </p>
              )}
              {copyResult && (
                <div className="space-y-2.5">
                  <CopyList label="Headlines" items={copyResult.headlines} />
                  <CopyList label="Long headlines" items={copyResult.long_headlines} />
                  <CopyList label="Descriptions" items={copyResult.descriptions} />
                </div>
              )}
              {!copyResult && !copyBusy && (
                <p className="text-[11px] text-muted-foreground">
                  The draft fills headlines, long headlines, and descriptions. Everything stays editable in the step.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Bottom controls — quiet row + Tune disclosure */}
        <div className="border-t border-border px-4 py-3 space-y-2 shrink-0 bg-card">
          {mode !== 'copy' && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <ModelPicker kind={genKind} value={model} onChange={handleModelChange} disabled={busy} />
                {finishedActive && modelOrigin && (
                  <span className="text-[10px] text-muted-foreground" title="Model origin">{modelOrigin}</span>
                )}
                {/* Aspect — locked from context, else model-constrained */}
                {lockedAspect ? (
                  <span
                    className="inline-flex items-center gap-1 h-7 rounded border border-border bg-secondary/40 px-2 text-[11px] font-mono text-muted-foreground"
                    title="Aspect locked to the slot you are filling"
                  >
                    <Lock className="h-3 w-3" /> {lockedAspect}
                  </span>
                ) : (
                  <select
                    value={effectiveAspect}
                    onChange={(e) => setAspect(e.target.value)}
                    disabled={busy}
                    className="h-7 rounded border border-border bg-background px-2 text-xs font-mono"
                  >
                    {modelAspects.map((a) => <option key={a} value={a}>{a}</option>)}
                  </select>
                )}
                {/* Live cost — always visible before Generate (brief §8) */}
                <span
                  className={cn(
                    'text-[10px] font-mono px-2 py-1 rounded border',
                    costError
                      ? 'border-danger/40 text-danger'
                      : 'border-border text-muted-foreground',
                  )}
                  title={costError ? `Model rejected the params: ${costError}` : costPartial ? 'Some stages could not be priced — total is partial' : (modelInfo?.cost_text || '')}
                >
                  {costError ? 'incompatible' : `≈ ${costLoading ? '…' : costCredits !== null ? `${costCredits}${costPartial ? '+' : ''}` : '—'} credits`}
                </span>
                <Button
                  onClick={submit}
                  disabled={busy || engineBusy || !prompt.trim() || !model || jobs.runningCount > 0
                    || (genKind === 'video' && videoSubMode === 'single' && talkingIntro && (!introSoulId || !introScript.trim()))
                    || (finishedActive && ((musicOn && !musicFilename) || (voOn && !voScript.trim())))}
                  size="sm"
                  className="ml-auto gap-1.5"
                  title={finishedActive
                    ? (musicOn && !musicFilename ? 'Pick a music file first'
                      : voOn && !voScript.trim() ? 'Add a voiceover script first'
                      : `Confirms the render — burns ≈ ${costCredits ?? '…'} credits`)
                    : undefined}
                >
                  {busy || engineBusy || jobs.runningCount > 0
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <Sparkles className="h-3.5 w-3.5" />}
                  {engineBusy
                    ? 'Rendering…'
                    : jobs.runningCount > 0
                      ? `${jobs.settledCount}/${jobs.variants.length}`
                      : finishedActive
                        ? `Generate finished video (≈ ${costLoading ? '…' : costCredits !== null ? `${costCredits}${costPartial ? '+' : ''}` : '—'} cr)`
                        : genKind === 'video'
                          ? (introActive ? `Render intro + ${duration}s clip` : `Generate ${duration}s clip`)
                          : variantsCount > 1 ? `Generate ${variantsCount}` : 'Generate'}
                </Button>
              </div>

              {/* Tune — the one advanced-params disclosure */}
              <div>
                <button
                  type="button"
                  onClick={() => setTuneOpen((v) => !v)}
                  className="flex items-center gap-1 text-[10px] uppercase font-mono text-muted-foreground hover:text-foreground transition-colors"
                >
                  {tuneOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  Tune
                  <span className="normal-case font-sans">· model {model || '…'}{modelInfo ? ` · ${modelInfo.cost_text}` : ''}</span>
                </button>
                {tuneOpen && (
                  <div className="flex flex-wrap items-center gap-3 mt-2 text-xs">
                    {genKind === 'image' && (
                      <label className="flex items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground">Variants</span>
                        <select
                          value={variantsCount}
                          onChange={(e) => setVariantsCount(Number(e.target.value))}
                          disabled={busy}
                          className="h-7 rounded border border-border bg-background px-2 text-xs font-mono"
                        >
                          {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
                        </select>
                      </label>
                    )}
                    {genKind === 'video' && videoSubMode === 'single' && modelInfo?.constraints?.duration_type === 'enum' && (
                      <label className="flex items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground">Duration</span>
                        <select
                          value={duration}
                          onChange={(e) => setDuration(Number(e.target.value))}
                          disabled={busy}
                          className="h-7 rounded border border-border bg-background px-2 text-xs font-mono"
                        >
                          {(modelInfo.constraints.durations || [4, 6, 8]).map((d) => (
                            <option key={d} value={d}>{d}s</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {genKind === 'video' && videoSubMode === 'single' && modelInfo?.constraints?.duration_type === 'int' && (
                      <label className="flex items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground">Duration</span>
                        <Input
                          type="number" min={1}
                          max={modelInfo.constraints.max_duration || 15}
                          value={duration}
                          onChange={(e) => setDuration(Math.max(1, Math.min(modelInfo.constraints.max_duration || 15, Number(e.target.value) || 1)))}
                          disabled={busy}
                          className="h-7 w-16 text-xs font-mono"
                        />
                        <span className="text-[10px] text-muted-foreground">s</span>
                      </label>
                    )}
                    {genKind === 'video' && !!modelInfo?.constraints?.modes?.length && (
                      <label className="flex items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground">Mode</span>
                        <select
                          value={klingMode}
                          onChange={(e) => setKlingMode(e.target.value)}
                          disabled={busy}
                          className="h-7 rounded border border-border bg-background px-2 text-xs font-mono"
                        >
                          {modelInfo.constraints.modes!.map((m) => <option key={m} value={m}>{m}</option>)}
                        </select>
                      </label>
                    )}
                    {genKind === 'video' && !!modelInfo?.constraints?.qualities?.length && (
                      <label className="flex items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground">Quality</span>
                        <select
                          value={veoQuality}
                          onChange={(e) => setVeoQuality(e.target.value)}
                          disabled={busy}
                          className="h-7 rounded border border-border bg-background px-2 text-xs font-mono"
                        >
                          <option value="">default</option>
                          {modelInfo.constraints.qualities!.map((q) => <option key={q} value={q}>{q}</option>)}
                        </select>
                      </label>
                    )}
                    {supportsSoul && (
                      <label className="flex items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-muted-foreground">Soul</span>
                        <select
                          value={soulId}
                          onChange={(e) => setSoulId(e.target.value)}
                          disabled={busy}
                          className="h-7 rounded border border-border bg-background px-2 text-xs max-w-[180px]"
                        >
                          <option value="">No Soul (random face)</option>
                          {souls.filter((s) => s.status === 'ready' && s.soul_id).map((s) => (
                            <option key={s.id} value={s.soul_id ?? ''}>{s.name}</option>
                          ))}
                        </select>
                      </label>
                    )}
                  </div>
                )}
              </div>

              {onUse && (
                <Button
                  onClick={handleUse}
                  disabled={!selectedId || usePending}
                  size="sm"
                  variant={selectedId ? 'default' : 'outline'}
                  className="w-full gap-1.5"
                >
                  {usePending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                  {selectedId ? 'Use in slot' : 'Pick a result to use'}
                </Button>
              )}
            </>
          )}

          {mode === 'copy' && onUseCopy && (
            <Button
              onClick={() => { if (copyResult) { onUseCopy(copyResult); onClose(); } }}
              disabled={!copyResult}
              size="sm"
              className="w-full gap-1.5"
            >
              <Check className="h-3.5 w-3.5" />
              Use in step
            </Button>
          )}
        </div>

        {/* Music-bed picker (finished video). Pulls the account's audio
            library — same source VideoCreator uses. */}
        {showMusicPicker && (
          <div
            className="absolute inset-0 z-10 bg-black/20 flex items-center justify-center p-4"
            onClick={() => setShowMusicPicker(false)}
          >
            <div
              className="w-full max-w-sm max-h-[80%] flex flex-col rounded-md border border-border bg-card shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
                <Music className="h-4 w-4 text-primary" />
                <span className="text-sm font-medium">Pick a music bed</span>
                <button onClick={() => setShowMusicPicker(false)} className="ml-auto p-1 hover:bg-secondary rounded" aria-label="Close">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-2">
                {audioLoading ? (
                  <p className="text-[11px] text-muted-foreground flex items-center gap-1.5 px-1 py-2">
                    <Loader2 className="h-3 w-3 animate-spin" /> loading audio…
                  </p>
                ) : libraryAudio.length === 0 ? (
                  <p className="text-[11px] text-muted-foreground px-1 py-2">
                    No audio in your library yet. Upload royalty-free tracks in the asset library first.
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {libraryAudio.map((a) => (
                      <li key={a.id}>
                        <button
                          type="button"
                          onClick={() => { setMusicFilename(a.filename); setShowMusicPicker(false); }}
                          className="w-full text-left px-2 py-1.5 text-xs hover:bg-secondary/50 rounded flex items-center gap-1.5"
                          title={a.filename}
                        >
                          <Music className="h-3 w-3 shrink-0 text-muted-foreground" />
                          <span className="truncate">{a.filename}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  );
}

// ── tiles ─────────────────────────────────────────────────────────

function ResultTile({
  variant, index, video, selected, onSelect, onRetry,
}: {
  variant: JobVariant;
  index: number;
  video: boolean;
  selected: boolean;
  onSelect: () => void;
  onRetry: () => void;
}) {
  const running = !isTerminal(variant.status);
  const ok = variant.status === 'completed' && variant.url;
  const frame = video ? 'aspect-video' : 'aspect-square';

  if (running) {
    return (
      <div className={cn(frame, 'rounded border border-border bg-secondary/30 flex items-center justify-center text-[10px] font-mono text-muted-foreground')}>
        <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> #{index + 1}
      </div>
    );
  }
  if (ok) {
    const url = variant.url || '';
    return (
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          frame, 'rounded border overflow-hidden bg-secondary/30 relative group transition-colors',
          selected ? 'border-primary ring-2 ring-primary' : 'border-border hover:border-primary/50',
        )}
        title={selected ? 'Selected — click "Use in slot" below' : 'Click to select'}
      >
        {video ? (
          <video src={url} className="w-full h-full object-cover" preload="metadata" muted playsInline controls />
        ) : (
          <img src={url} alt="" className="w-full h-full object-cover" loading="lazy" />
        )}
        {selected && (
          <span className="absolute top-1 right-1 bg-primary text-primary-foreground rounded-full p-0.5">
            <Check className="h-3 w-3" />
          </span>
        )}
      </button>
    );
  }
  // failed | nsfw — per-item retry (brief §6)
  return (
    <div
      className={cn(frame, 'rounded border border-danger/40 bg-danger-soft flex flex-col items-center justify-center gap-1 p-1 text-center')}
      title={variant.error_message || variant.status}
    >
      <AlertCircle className="h-3.5 w-3.5 text-danger" />
      <span className="text-[9px] font-mono text-danger leading-tight line-clamp-2 break-all">
        {variant.status === 'nsfw' ? 'Content filter' : (variant.error_message || 'failed').slice(0, 60)}
      </span>
      <button
        type="button"
        onClick={onRetry}
        className="text-[10px] underline text-muted-foreground hover:text-foreground"
      >
        Retry
      </button>
    </div>
  );
}

function CopyList({ label, items }: { label: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="text-[10px] uppercase font-mono text-muted-foreground mb-1">{label}</p>
      <ul className="space-y-1">
        {items.map((t, i) => (
          <li key={i} className="text-xs border border-border rounded px-2 py-1 bg-secondary/30">{t}</li>
        ))}
      </ul>
    </div>
  );
}
