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
  Lock, Sparkles, Wand2, X,
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

  const genKind: 'image' | 'video' = mode === 'video' ? 'video' : 'image';
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

  // ── soul library (only when the model supports it) ─────────────
  const supportsSoul = !!modelInfo?.constraints?.supports_soul;
  const [souls, setSouls] = useState<SoulCharacter[]>([]);
  useEffect(() => {
    if (!supportsSoul) return;
    studioListSouls(accountId).then(setSouls).catch(() => setSouls([]));
  }, [supportsSoul, accountId]);

  // ── live cost (debounced; soft errors surfaced inline) ─────────
  const [costCredits, setCostCredits] = useState<number | null>(null);
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
      studioCostEstimate({
        prompt: trimmed,
        model,
        aspect_ratio: effectiveAspect,
        duration_seconds: genKind === 'video' ? duration : undefined,
        mode: isKling ? klingMode : undefined,
      })
        .then((r) => {
          if (ac.signal.aborted) return;
          setCostCredits(r.credits);
          setCostError(r.credits === null && r.error_message
            ? r.error_message.split('\n').filter(Boolean).slice(0, 2).join(' · ').slice(0, 200)
            : null);
        })
        .catch((e) => {
          if (ac.signal.aborted) return;
          setCostCredits(null);
          setCostError(e instanceof Error ? e.message : 'cost lookup failed');
        })
        .finally(() => { if (!ac.signal.aborted) setCostLoading(false); });
    }, 400);
    return () => window.clearTimeout(handle);
  }, [prompt, model, effectiveAspect, duration, klingMode, isKling, genKind, mode]);

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
    if (!trimmed || busy || !model) return;
    setBusy(true);
    setSelectedId(null);
    try {
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
                  title={costError ? `Model rejected the params: ${costError}` : (modelInfo?.cost_text || '')}
                >
                  {costError ? 'incompatible' : `≈ ${costLoading ? '…' : costCredits ?? '—'} credits`}
                </span>
                <Button
                  onClick={submit}
                  disabled={busy || !prompt.trim() || !model || jobs.runningCount > 0}
                  size="sm"
                  className="ml-auto gap-1.5"
                >
                  {busy || jobs.runningCount > 0
                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    : <Sparkles className="h-3.5 w-3.5" />}
                  {jobs.runningCount > 0
                    ? `${jobs.settledCount}/${jobs.variants.length}`
                    : genKind === 'video' ? `Generate ${duration}s clip` : variantsCount > 1 ? `Generate ${variantsCount}` : 'Generate'}
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
                    {genKind === 'video' && modelInfo?.constraints?.duration_type === 'enum' && (
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
                    {genKind === 'video' && modelInfo?.constraints?.duration_type === 'int' && (
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
