/**
 * PMaxWizard — Performance Max campaign creation flow.
 *
 * Six steps in sequence, each gating the next against Google's hard
 * minimums so the user can't reach Submit with an invalid bundle:
 *   1. Brief & budget (name, $/day, final URL, business name)
 *   2. Text assets — headlines (≥3, ≤30c), long headlines (≥1, ≤90c),
 *      descriptions (≥2, ≤90c).
 *   3. Image assets — logos (≥1), landscape 1.91:1 (≥1), square 1:1
 *      (≥1), portrait 4:5 (optional).
 *   4. Video assets — YouTube IDs (≥1).
 *   5. Audience signals (optional).
 *   6. Review + submit → POST /api/accounts/{id}/campaigns/pmax.
 *
 * Inline AI generation hooks (creative_director for copy, higgsfield
 * for images) are wired as buttons but deliberately deferred to a
 * follow-up commit — the manual-entry path is what ships first and
 * makes the wizard end-to-end usable today.
 *
 * Backed server-side by `pmax_orchestrator.py`, which does its own
 * pre-flight validation; this client UI surfaces the same errors
 * inline so the user fixes them before round-tripping.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  ArrowLeft, ArrowRight, Layers, CheckCircle2, Circle, Plus, X,
  Upload, Image as ImageIcon, Video, Sparkles, Loader2, AlertCircle,
  FolderOpen, Search, Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import HiggsfieldGenerator from '@/components/studio/HiggsfieldGenerator';
import type { PromptContext } from '@/components/studio/HiggsfieldGenerator';
import type { StudioJobStatus } from '@/lib/api';

// Map a wizard slot to the higgsfield aspect that fits best.
// Google's "landscape" PMax image is 1.91:1 — higgsfield's closest
// supported aspect is 16:9; the slight crop is negligible for ads.
type SlotAspect = '1:1' | '4:5' | '9:16' | '16:9';

const STEPS = [
  { id: 'brief',    label: 'Brief & budget'    },
  { id: 'text',     label: 'Text assets'       },
  { id: 'images',   label: 'Image assets'      },
  { id: 'videos',   label: 'Video assets'      },
  { id: 'signals',  label: 'Audience signals'  },
  { id: 'review',   label: 'Review & submit'   },
] as const;

type StepId = typeof STEPS[number]['id'];

// Google's PMax hard minimums — server validates these too; this is the
// client-side mirror so Next/Submit can stay disabled until satisfied.
const RULES = {
  headlines:      { min: 3, max: 15, maxChars: 30 },
  longHeadlines:  { min: 1, max: 5,  maxChars: 90 },
  descriptions:   { min: 2, max: 5,  maxChars: 90 },
  logos:          { min: 1 },
  landscape:      { min: 1 },
  square:         { min: 1 },
  videos:         { min: 1 },
};

interface PMaxBundle {
  name: string;
  dailyBudget: string;   // user types in dollars; convert to micros on submit
  finalUrl: string;
  businessName: string;
  brief: string;          // optional — fuel for the Creative Director draft
  headlines: string[];
  longHeadlines: string[];
  descriptions: string[];
  logos: string[];        // asset resource_names
  landscape: string[];
  square: string[];
  portrait: string[];
  videoIds: string[];     // YouTube video IDs
  audienceSignals: string[];
}

const EMPTY_BUNDLE: PMaxBundle = {
  name: '', dailyBudget: '', finalUrl: '', businessName: '', brief: '',
  headlines: [''], longHeadlines: [''], descriptions: ['', ''],
  logos: [], landscape: [], square: [], portrait: [],
  videoIds: [''], audienceSignals: [],
};

interface PMaxWizardProps {
  onClose: () => void;
  onBackToTypePicker: () => void;
}

export default function PMaxWizard({ onClose, onBackToTypePicker }: PMaxWizardProps) {
  const accountId = useClientAccountId();
  const [stepIdx, setStepIdx] = useState(0);
  const [bundle, setBundle] = useState<PMaxBundle>(() => {
    try {
      const saved = sessionStorage.getItem('pmax-wizard-bundle');
      // Merge over defaults so bundles saved before new fields (e.g. `brief`)
      // were added don't come back with undefined keys.
      return saved ? { ...EMPTY_BUNDLE, ...JSON.parse(saved) } : EMPTY_BUNDLE;
    } catch { return EMPTY_BUNDLE; }
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string; campaignId?: string } | null>(null);

  const setField = useCallback(<K extends keyof PMaxBundle>(key: K, value: PMaxBundle[K]) => {
    setBundle(prev => {
      const next = { ...prev, [key]: value };
      try { sessionStorage.setItem('pmax-wizard-bundle', JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const stepId = STEPS[stepIdx].id;

  // Human-readable "why is Next disabled" — the validation itself lives in
  // stepValid below; this just narrates the unmet minimums so a disabled
  // button never reads as a bug.
  const stepHint = useMemo(() => {
    const missing: string[] = [];
    if (stepId === 'brief') {
      if (!bundle.name.trim()) missing.push('campaign name');
      if (!(parseFloat(bundle.dailyBudget) > 0)) missing.push('daily budget');
      if (!bundle.finalUrl.trim()) missing.push('final URL');
      if (!bundle.businessName.trim()) missing.push('business name');
    } else if (stepId === 'text') {
      const h = bundle.headlines.filter(Boolean);
      const lh = bundle.longHeadlines.filter(Boolean);
      const d = bundle.descriptions.filter(Boolean);
      if (h.length < RULES.headlines.min) missing.push(`${RULES.headlines.min - h.length} more headline${RULES.headlines.min - h.length > 1 ? 's' : ''}`);
      if (lh.length < RULES.longHeadlines.min) missing.push(`${RULES.longHeadlines.min - lh.length} long headline`);
      if (d.length < RULES.descriptions.min) missing.push(`${RULES.descriptions.min - d.length} more description${RULES.descriptions.min - d.length > 1 ? 's' : ''}`);
      if (h.some(s => s.length > RULES.headlines.maxChars)) missing.push('a headline is over 30 chars');
      if (lh.some(s => s.length > RULES.longHeadlines.maxChars)) missing.push('a long headline is over 90 chars');
      if (d.some(s => s.length > RULES.descriptions.maxChars)) missing.push('a description is over 90 chars');
    } else if (stepId === 'images') {
      if (bundle.logos.length < RULES.logos.min) missing.push('a logo');
      if (bundle.landscape.length < RULES.landscape.min) missing.push('a landscape image');
      if (bundle.square.length < RULES.square.min) missing.push('a square image');
    } else if (stepId === 'videos') {
      if (bundle.videoIds.filter(Boolean).length < RULES.videos.min) missing.push('a YouTube video ID');
    }
    return missing.length ? `To continue: ${missing.join(' · ')}` : null;
  }, [stepId, bundle]);

  // ── Per-step validation: gates Next/Submit so a user never reaches the
  // server with an invalid bundle. Same rules as the orchestrator's
  // pre-flight; ad-hoc validation is intentional (no shared schema yet).
  const stepValid = useMemo(() => {
    switch (stepId) {
      case 'brief': {
        const b = parseFloat(bundle.dailyBudget);
        return !!bundle.name.trim()
          && !!bundle.finalUrl.trim()
          && !!bundle.businessName.trim()
          && Number.isFinite(b) && b > 0;
      }
      case 'text': {
        const h = bundle.headlines.filter(Boolean);
        const lh = bundle.longHeadlines.filter(Boolean);
        const d = bundle.descriptions.filter(Boolean);
        return h.length >= RULES.headlines.min
          && lh.length >= RULES.longHeadlines.min
          && d.length >= RULES.descriptions.min
          && h.every(s => s.length <= RULES.headlines.maxChars)
          && lh.every(s => s.length <= RULES.longHeadlines.maxChars)
          && d.every(s => s.length <= RULES.descriptions.maxChars);
      }
      case 'images':
        return bundle.logos.length >= RULES.logos.min
          && bundle.landscape.length >= RULES.landscape.min
          && bundle.square.length >= RULES.square.min;
      case 'videos':
        return bundle.videoIds.filter(Boolean).length >= RULES.videos.min;
      case 'signals':
        return true; // optional
      case 'review':
        return true; // submit handler does its own gate
    }
  }, [stepId, bundle]);

  const handleSubmit = useCallback(async () => {
    if (!accountId) return;
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const dailyDollars = parseFloat(bundle.dailyBudget);
      const budget_micros = Math.round(dailyDollars * 1_000_000);
      const res = await fetch(`/api/accounts/${accountId}/campaigns/pmax`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: bundle.name,
          budget_micros,
          final_urls: [bundle.finalUrl],
          business_name: bundle.businessName,
          headlines: bundle.headlines.filter(Boolean),
          long_headlines: bundle.longHeadlines.filter(Boolean),
          descriptions: bundle.descriptions.filter(Boolean),
          logos: bundle.logos,
          marketing_images: {
            landscape: bundle.landscape,
            square: bundle.square,
            portrait: bundle.portrait,
          },
          video_youtube_ids: bundle.videoIds.filter(Boolean),
          // Free-text hints become search-theme signals on the asset
          // group (attached server-side after asset linking succeeds).
          audience_signals: bundle.audienceSignals.length
            ? bundle.audienceSignals.map(s => ({ search_theme: s }))
            : null,
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        const errors: string[] = json?.detail?.errors || [json?.detail?.message || 'Unknown error'];
        setSubmitResult({ ok: false, message: errors.join('; ') });
        return;
      }
      setSubmitResult({
        ok: true,
        campaignId: json.campaign_id,
        message: `Campaign ${json.campaign_id} created (PAUSED). Asset group ${json.asset_group_id}. ${(json.warnings || []).length} warning(s).`,
      });
      try { sessionStorage.removeItem('pmax-wizard-bundle'); } catch {}
    } catch (e) {
      setSubmitResult({ ok: false, message: e instanceof Error ? e.message : String(e) });
    } finally {
      setSubmitting(false);
    }
  }, [accountId, bundle]);

  return (
    <div className="max-w-3xl mx-auto py-8 px-6">
      <div className="flex items-center gap-3 mb-8">
        <button onClick={onBackToTypePicker} className="p-1.5 hover:bg-secondary rounded-md">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Layers className="h-6 w-6 text-primary" />
            Performance Max
          </h1>
          <p className="text-sm text-muted-foreground">Build a complete PMax campaign — assets included.</p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-6 text-[10px]">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center flex-1">
            <div className={cn(
              'flex items-center gap-1.5 px-2 py-1 rounded-md',
              i === stepIdx && 'bg-primary text-primary-foreground font-medium',
              i < stepIdx && 'text-muted-foreground',
              i > stepIdx && 'text-muted-foreground/60',
            )}>
              {i < stepIdx
                ? <CheckCircle2 className="h-3 w-3" />
                : <Circle className="h-3 w-3" />
              }
              <span className="whitespace-nowrap">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="h-px flex-1 bg-border mx-1" />}
          </div>
        ))}
      </div>

      <div className="border border-border rounded-lg p-6 bg-card mb-4">
        {stepId === 'brief'    && <StepBrief    bundle={bundle} setField={setField} />}
        {stepId === 'text'     && <StepText     bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'images'   && <StepImages   bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'videos'   && <StepVideos   bundle={bundle} setField={setField} />}
        {stepId === 'signals'  && <StepSignals  bundle={bundle} setField={setField} />}
        {stepId === 'review'   && <StepReview   bundle={bundle} submitResult={submitResult} submitting={submitting} />}
      </div>

      {/* Footer nav */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => stepIdx === 0 ? onBackToTypePicker() : setStepIdx(stepIdx - 1)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground px-3 py-2"
          disabled={submitting}
        >
          <ArrowLeft className="h-4 w-4" />
          {stepIdx === 0 ? 'Type' : 'Back'}
        </button>
        {stepId !== 'review' ? (
          <div className="flex items-center gap-3">
            {!stepValid && stepHint && (
              <p className="text-[11px] text-warning max-w-[360px] text-right">{stepHint}</p>
            )}
            <Button
              onClick={() => setStepIdx(stepIdx + 1)}
              disabled={!stepValid}
              className="gap-1.5"
            >
              Next <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        ) : submitResult?.ok ? (
          <Button onClick={onClose} className="gap-1.5">
            <CheckCircle2 className="h-4 w-4" /> Done
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="gap-1.5"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {submitting ? 'Creating...' : 'Create campaign'}
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Step components ─────────────────────────────────────────────────

function StepBrief({ bundle, setField }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void }) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium mb-1.5 block">Campaign name *</label>
        <Input value={bundle.name} onChange={e => setField('name', e.target.value)} placeholder="e.g. Panama QIV — PMax — May 2026" />
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 block">Daily budget (USD) *</label>
        <Input type="number" step="0.01" min="0.01" value={bundle.dailyBudget} onChange={e => setField('dailyBudget', e.target.value)} placeholder="50.00" />
        <p className="text-[10px] text-muted-foreground mt-1">Google will spend up to ~2× this on high-traffic days, but average daily ≈ this number.</p>
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 block">Final URL *</label>
        <Input value={bundle.finalUrl} onChange={e => setField('finalUrl', e.target.value)} placeholder="https://goldenvisas.mercan.com/panama" />
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 block">Business name *</label>
        <Input value={bundle.businessName} onChange={e => setField('businessName', e.target.value)} placeholder="Mercan" />
        <p className="text-[10px] text-muted-foreground mt-1">Shown in auto-generated layouts; keep it short and brand-faithful.</p>
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 block">Campaign brief (optional)</label>
        <textarea
          value={bundle.brief}
          onChange={e => setField('brief', e.target.value)}
          rows={3}
          placeholder="Who is this for, what's the offer, what makes it different? The Creative Director uses this (plus your landing page) to draft headlines and descriptions in the next step."
          className="w-full text-sm rounded-md border border-border bg-background p-2.5 resize-none placeholder:text-muted-foreground/60"
        />
      </div>
    </div>
  );
}

function StepText({ bundle, setField, accountId }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void; accountId: string }) {
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  // Poll-based: the draft takes 1-3 min and a single long request died
  // whenever the dev proxy or a server blipped. Start a job, poll every 3s;
  // the job id is kept in sessionStorage so even a page refresh resumes it.
  const applyDraft = useCallback((result: { headlines?: string[]; long_headlines?: string[]; descriptions?: string[] }) => {
    if (result.headlines?.length) setField('headlines', result.headlines);
    if (result.long_headlines?.length) setField('longHeadlines', result.long_headlines);
    if (result.descriptions?.length) setField('descriptions', result.descriptions);
  }, [setField]);

  const pollDraft = useCallback(async (draftId: string) => {
    const started = Date.now();
    while (Date.now() - started < 6 * 60_000) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/pmax/draft-copy/${draftId}`);
        const job = await res.json();
        if (job.status === 'done') {
          applyDraft(job.result || {});
          sessionStorage.removeItem('pmax-draft-id');
          return;
        }
        if (job.status === 'error') {
          sessionStorage.removeItem('pmax-draft-id');
          throw new Error(job.message || 'draft failed');
        }
        // still running — keep polling (transient fetch errors just retry)
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
      }
    }
    throw new Error('Draft timed out after 6 minutes — try again.');
  }, [applyDraft]);

  const draftWithAI = async () => {
    setDrafting(true);
    setDraftError(null);
    try {
      const res = await fetch(`/api/accounts/${accountId}/pmax/draft-copy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief: bundle.brief,
          final_url: bundle.finalUrl,
          business_name: bundle.businessName,
          campaign_name: bundle.name,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.draft_id) throw new Error(data.detail?.message || data.error || `HTTP ${res.status}`);
      sessionStorage.setItem('pmax-draft-id', data.draft_id);
      await pollDraft(data.draft_id);
    } catch (e) {
      setDraftError(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
    }
  };

  // Resume polling a draft that was in flight when the page was refreshed.
  useEffect(() => {
    const pending = sessionStorage.getItem('pmax-draft-id');
    if (!pending) return;
    setDrafting(true);
    pollDraft(pending)
      .catch(e => setDraftError(e instanceof Error ? e.message : String(e)))
      .finally(() => setDrafting(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-5">
      {/* Creative Director draft — fills all three lists from the brief +
          landing page; everything stays editable below. */}
      <div className="border border-blue-500/20 bg-blue-500/5 rounded-md p-3 text-xs">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
            <p className="text-muted-foreground leading-relaxed">
              Let the <b>Creative Director</b> draft headlines and descriptions from your
              brief and landing page ({bundle.finalUrl || 'set the Final URL in step 1'}).
              Replaces what's typed below — everything stays editable.
            </p>
          </div>
          <Button size="sm" onClick={draftWithAI} disabled={drafting || !bundle.finalUrl} className="gap-1.5 shrink-0">
            {drafting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {drafting ? 'Drafting… 1–3 min (reads your landing page)' : 'Draft with Creative Director'}
          </Button>
        </div>
        {draftError && (
          <p className="mt-2 flex items-center gap-1.5 text-red-500">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {draftError}
          </p>
        )}
      </div>
      <TextList
        label="Headlines"
        hint={`≥${RULES.headlines.min}, each ≤${RULES.headlines.maxChars} chars · up to ${RULES.headlines.max}`}
        items={bundle.headlines}
        onChange={v => setField('headlines', v)}
        maxChars={RULES.headlines.maxChars}
        minItems={RULES.headlines.min}
        maxItems={RULES.headlines.max}
      />
      <TextList
        label="Long headlines"
        hint={`≥${RULES.longHeadlines.min}, each ≤${RULES.longHeadlines.maxChars} chars · up to ${RULES.longHeadlines.max}`}
        items={bundle.longHeadlines}
        onChange={v => setField('longHeadlines', v)}
        maxChars={RULES.longHeadlines.maxChars}
        minItems={RULES.longHeadlines.min}
        maxItems={RULES.longHeadlines.max}
      />
      <TextList
        label="Descriptions"
        hint={`≥${RULES.descriptions.min}, each ≤${RULES.descriptions.maxChars} chars · up to ${RULES.descriptions.max}`}
        items={bundle.descriptions}
        onChange={v => setField('descriptions', v)}
        maxChars={RULES.descriptions.maxChars}
        minItems={RULES.descriptions.min}
        maxItems={RULES.descriptions.max}
      />
    </div>
  );
}

function StepImages({ bundle, setField, accountId }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void; accountId: string }) {
  // Shared campaign context for the Visual Director enhance affordance
  // inside each slot's generator. Slot label/aspect get appended per
  // slot in ImageGroup.
  const baseContext: Omit<PromptContext, 'slotLabel' | 'slotAspect'> = {
    brief: bundle.brief,
    businessName: bundle.businessName,
    finalUrl: bundle.finalUrl,
  };
  return (
    <div className="space-y-5">
      <AiHint
        body="Upload your assets, pick from the Studio library, OR click ‘Generate (Higgsfield)’ to create them inline — the generator opens with the correct aspect locked to the slot, and any successful image lands here automatically."
      />
      <ImageGroup
        label="Logos"
        spec="Any aspect, transparent background preferred"
        slotAspect="1:1"
        items={bundle.logos}
        onChange={v => setField('logos', v)}
        accountId={accountId}
        minItems={RULES.logos.min}
        maxItems={5}
        promptContext={baseContext}
      />
      <ImageGroup
        label="Landscape marketing image (1.91:1)"
        spec="1200×628 recommended"
        slotAspect="16:9"
        items={bundle.landscape}
        onChange={v => setField('landscape', v)}
        accountId={accountId}
        minItems={RULES.landscape.min}
        maxItems={20}
        promptContext={baseContext}
      />
      <ImageGroup
        label="Square marketing image (1:1)"
        spec="1200×1200 recommended"
        slotAspect="1:1"
        items={bundle.square}
        onChange={v => setField('square', v)}
        accountId={accountId}
        minItems={RULES.square.min}
        maxItems={20}
        promptContext={baseContext}
      />
      <ImageGroup
        label="Portrait marketing image (4:5)"
        spec="Optional · 960×1200 recommended"
        slotAspect="4:5"
        items={bundle.portrait}
        onChange={v => setField('portrait', v)}
        accountId={accountId}
        minItems={0}
        maxItems={20}
        promptContext={baseContext}
      />
    </div>
  );
}

function StepVideos({ bundle, setField }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void }) {
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        PMax requires at least one YouTube video. Paste the video ID (the
        bit after <code>?v=</code> in the YouTube URL) — the video must
        already be uploaded to a YouTube channel.
      </p>
      <TextList
        label="YouTube video IDs"
        hint={`≥${RULES.videos.min} required`}
        items={bundle.videoIds}
        onChange={v => setField('videoIds', v)}
        maxChars={32}
        minItems={RULES.videos.min}
        maxItems={5}
        placeholder="dQw4w9WgXcQ"
      />
      {bundle.videoIds.filter(Boolean).map(id => (
        <div key={id} className="flex items-center gap-2 text-xs text-muted-foreground">
          <Video className="h-4 w-4 text-red-500" />
          <a href={`https://youtube.com/watch?v=${id}`} target="_blank" rel="noreferrer" className="hover:underline">
            youtube.com/watch?v={id}
          </a>
        </div>
      ))}
    </div>
  );
}

function StepSignals({ bundle, setField }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void }) {
  return (
    <div className="space-y-3">
      <AiHint
        body="Audience signals tell Google's algorithm who to target initially. Optional — skip to let PMax explore from scratch. Custom-segment wiring layered in the next phase."
      />
      <p className="text-xs text-muted-foreground">Skip this step or add free-text signal hints. Each hint is attached to the asset group as a search-theme signal; structured custom-segment wiring is a follow-up.</p>
      <TextList
        label="Signal hints (optional)"
        hint="One per row — e.g. 'high-net-worth investors', 'second-passport seekers'"
        items={bundle.audienceSignals.length ? bundle.audienceSignals : ['']}
        onChange={v => setField('audienceSignals', v.filter(Boolean))}
        maxChars={120}
        minItems={0}
        maxItems={10}
      />
    </div>
  );
}

function StepReview({ bundle, submitResult, submitting }: { bundle: PMaxBundle; submitResult: { ok: boolean; message: string; campaignId?: string } | null; submitting: boolean }) {
  return (
    <div className="space-y-4 text-sm">
      <ReviewRow label="Campaign name" value={bundle.name} />
      <ReviewRow label="Daily budget" value={`$${parseFloat(bundle.dailyBudget || '0').toFixed(2)}/d`} />
      <ReviewRow label="Final URL" value={bundle.finalUrl} />
      <ReviewRow label="Business name" value={bundle.businessName} />
      <ReviewRow label="Text assets" value={`${bundle.headlines.filter(Boolean).length} headlines · ${bundle.longHeadlines.filter(Boolean).length} long · ${bundle.descriptions.filter(Boolean).length} descriptions`} />
      <ReviewRow label="Image assets" value={`${bundle.logos.length} logo · ${bundle.landscape.length} landscape · ${bundle.square.length} square · ${bundle.portrait.length} portrait`} />
      <ReviewRow label="Videos" value={`${bundle.videoIds.filter(Boolean).length} YouTube video(s)`} />
      <ReviewRow label="Audience signals" value={bundle.audienceSignals.length ? bundle.audienceSignals.join(', ') : '— (Google explores from scratch)'} />
      <div className="mt-4 border border-amber-500/30 bg-amber-500/5 rounded-md p-3 text-xs">
        <strong>Campaign will be created PAUSED.</strong> Review the asset group in Google Ads UI before enabling — once enabled, it starts spending immediately.
      </div>
      {submitResult && (
        <div className={cn(
          'mt-3 rounded-md p-3 text-xs flex items-start gap-2',
          submitResult.ok ? 'border border-green-500/30 bg-green-500/5 text-green-700 dark:text-green-300' : 'border border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300'
        )}>
          {submitResult.ok ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" /> : <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />}
          <span>{submitResult.message}</span>
        </div>
      )}
      {submitting && (
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Creating budget, campaign, assets, and asset group...
        </div>
      )}
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-3 border-b border-border/50 pb-2 last:border-0 last:pb-0">
      <div className="text-xs text-muted-foreground w-32 shrink-0">{label}</div>
      <div className="text-sm flex-1 break-words">{value || <span className="text-muted-foreground italic">empty</span>}</div>
    </div>
  );
}

// ── Reusable building blocks ────────────────────────────────────────

function TextList({
  label, hint, items, onChange, maxChars, minItems, maxItems, placeholder,
}: {
  label: string; hint: string; items: string[]; onChange: (v: string[]) => void;
  maxChars: number; minItems: number; maxItems: number; placeholder?: string;
}) {
  const setAt = (i: number, val: string) => {
    const next = [...items];
    next[i] = val;
    onChange(next);
  };
  const addRow = () => onChange([...items, '']);
  const removeRow = (i: number) => {
    const next = [...items];
    next.splice(i, 1);
    onChange(next.length ? next : ['']);
  };
  const filled = items.filter(Boolean).length;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs font-medium">{label}</label>
        <span className={cn(
          'text-[10px]',
          filled < minItems ? 'text-amber-500' : 'text-muted-foreground'
        )}>
          {filled}/{minItems} min · {hint}
        </span>
      </div>
      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <Input
              value={item}
              onChange={e => setAt(i, e.target.value.slice(0, maxChars))}
              placeholder={placeholder || `${label} ${i + 1}`}
              className={cn('flex-1 text-sm', item.length > maxChars && 'border-red-500')}
            />
            <span className={cn(
              'text-[10px] tabular-nums w-12 text-right',
              item.length > maxChars * 0.9 ? 'text-amber-500' : 'text-muted-foreground'
            )}>
              {item.length}/{maxChars}
            </span>
            <button
              onClick={() => removeRow(i)}
              className="p-1 hover:bg-secondary rounded text-muted-foreground"
              aria-label="Remove"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        {items.length < maxItems && (
          <button
            onClick={addRow}
            className="text-xs text-primary hover:underline flex items-center gap-1"
          >
            <Plus className="h-3 w-3" /> Add another
          </button>
        )}
      </div>
    </div>
  );
}

function ImageGroup({
  label, spec, slotAspect, items, onChange, accountId, minItems, maxItems = 20, promptContext,
}: {
  label: string; spec: string; slotAspect: SlotAspect; items: string[]; onChange: (v: string[]) => void;
  accountId: string; minItems: number; maxItems?: number;
  promptContext?: Omit<PromptContext, 'slotLabel' | 'slotAspect'>;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showGen, setShowGen] = useState(false);
  const [showLib, setShowLib] = useState(false);

  const handleGenerated = (asset: StudioJobStatus) => {
    // Only completed assets count toward the slot; failed/nsfw stay
    // surfaced inside the generator's own per-tile error display.
    if (asset.status !== 'completed' || !asset.asset_id) return;
    // Avoid duplicates if onSettled fires for the same id twice.
    if (items.includes(asset.asset_id)) return;
    if (items.length >= maxItems) return;
    onChange([...items, asset.asset_id]);
  };

  // Library toggle: clicking a selected thumbnail removes it from the
  // slot; clicking an unselected one adds it (up to the slot max).
  const toggleLibraryAsset = (assetId: string) => {
    if (items.includes(assetId)) {
      onChange(items.filter((id) => id !== assetId));
    } else if (items.length < maxItems) {
      onChange([...items, assetId]);
    }
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('account_id', accountId);
      const res = await fetch('/api/assets/upload', { method: 'POST', body: fd });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.detail || `Upload failed (${res.status})`);
      // Existing endpoint returns an Asset with at least an id we can
      // hand to the orchestrator. If the response shape is different in
      // your codebase, this is the single point to adapt.
      const ref = json?.resource_name || json?.id || json?.asset_id;
      if (!ref) throw new Error('Upload response missing asset reference');
      onChange([...items, String(ref)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs font-medium">{label}</label>
        <span className={cn(
          'text-[10px]',
          items.length < minItems ? 'text-amber-500' : 'text-muted-foreground'
        )}>
          {items.length}{minItems ? `/${minItems} min` : ' (optional)'} · {spec}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((ref, i) => (
          <div key={ref + i} className="flex items-center gap-1 border border-border rounded-md px-2 py-1 text-xs bg-secondary/30">
            <ImageIcon className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono text-[10px] truncate max-w-[200px]">{ref}</span>
            <button
              onClick={() => onChange(items.filter((_, j) => j !== i))}
              className="ml-1 hover:bg-secondary rounded p-0.5"
              aria-label="Remove"
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={() => setShowGen(true)}
          className="cursor-pointer border border-dashed border-violet-500/50 rounded-md px-3 py-1.5 text-xs flex items-center gap-1.5 hover:bg-violet-500/10 transition-colors text-violet-600 dark:text-violet-300"
          title={`Generate ${slotAspect} images via Higgsfield`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Generate (Higgsfield)
        </button>
        <button
          type="button"
          onClick={() => setShowLib(v => !v)}
          className={cn(
            'cursor-pointer border border-dashed border-border rounded-md px-3 py-1.5 text-xs flex items-center gap-1.5 hover:bg-secondary/50 transition-colors',
            showLib && 'bg-secondary/50 border-solid',
          )}
          title="Pick already-generated or uploaded images from the Studio asset library"
        >
          <FolderOpen className="h-3.5 w-3.5" />
          From library
        </button>
        <label className={cn(
          'cursor-pointer border border-dashed border-border rounded-md px-3 py-1.5 text-xs flex items-center gap-1.5 hover:bg-secondary/50 transition-colors',
          uploading && 'opacity-60 pointer-events-none'
        )}>
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {uploading ? 'Uploading...' : 'Upload'}
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={e => {
              const f = e.target.files?.[0];
              if (f) handleUpload(f);
              e.target.value = '';
            }}
          />
        </label>
      </div>
      {error && (
        <p className="text-[10px] text-red-500 mt-1 flex items-center gap-1">
          <AlertCircle className="h-3 w-3" /> {error}
        </p>
      )}
      {/* Inline library picker — expands below the slot row (no modal).
          Lists the account's existing ad_assets images newest-first;
          a click toggles the asset in/out of this slot. The selected
          ids are the SAME shape upload/generate produce, so the
          orchestrator's local-UUID bridge resolves them unchanged. */}
      {showLib && (
        <LibraryPicker
          accountId={accountId}
          items={items}
          onToggle={toggleLibraryAsset}
          slotAspect={slotAspect}
          maxItems={maxItems}
          onClose={() => setShowLib(false)}
        />
      )}
      {/* Higgsfield generation modal — pre-locks the aspect ratio per
          slot so the operator can't accidentally generate a 16:9 for
          the square logo group. onSettled hands completed asset_ids
          straight into the slot's items array (same shape Upload
          produces, so no PMax-orchestrator-side adapter needed). */}
      {showGen && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center pt-20 px-4"
          onClick={() => setShowGen(false)}
        >
          <div
            className="w-full max-w-2xl bg-background border border-border rounded-lg shadow-xl overflow-hidden max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <div>
                <div className="text-sm font-semibold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-violet-500" />
                  Generate {label.toLowerCase()}
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Aspect locked to {slotAspect} for this slot. {spec}.
                </p>
              </div>
              <button
                onClick={() => setShowGen(false)}
                className="p-1 hover:bg-secondary rounded"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4">
              <HiggsfieldGenerator
                accountId={accountId}
                lockAspect={slotAspect}
                onSettled={handleGenerated}
                caption={`Slot: ${label.toLowerCase()}`}
                promptContext={{
                  ...promptContext,
                  slotLabel: label,
                  slotAspect,
                }}
              />
            </div>
            <div className="px-4 py-3 border-t border-border flex items-center justify-between bg-secondary/30">
              <p className="text-[10px] text-muted-foreground">
                {items.length} added · close when done
              </p>
              <Button size="sm" onClick={() => setShowGen(false)}>Done</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Minimal slice of the assets API response the picker needs — full
// shape lives in StudioPage's AdAsset; duplicating 5 fields here beats
// exporting a cross-page type for a read-only grid.
interface LibraryAsset {
  id: string;
  filename: string;
  url: string;
  thumbnail_url?: string | null;
  created_at: string;
}

/** Inline expanding panel listing the account's existing image assets
 * (Higgsfield generations + uploads), newest first. Clicking a tile
 * toggles its ad_asset id in/out of the slot. Aspect mismatches are
 * allowed — Google crops marketing images to fit — so the target
 * aspect is shown as guidance, not a filter. */
function LibraryPicker({
  accountId, items, onToggle, slotAspect, maxItems, onClose,
}: {
  accountId: string; items: string[]; onToggle: (assetId: string) => void;
  slotAspect: SlotAspect; maxItems: number; onClose: () => void;
}) {
  const [assets, setAssets] = useState<LibraryAsset[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    const qs = new URLSearchParams({ asset_type: 'image', limit: '200' });
    if (accountId) qs.set('account_id', accountId);
    fetch(`/api/assets?${qs}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: LibraryAsset[]) => { if (!cancelled) setAssets(d); })
      .catch(e => { if (!cancelled) setLoadError(e instanceof Error ? e.message : String(e)); });
    return () => { cancelled = true; };
  }, [accountId]);

  const q = search.trim().toLowerCase();
  const visible = (assets || []).filter(a => !q || a.filename.toLowerCase().includes(q));
  const atMax = items.length >= maxItems;

  return (
    <div className="mt-2 border border-border rounded-md bg-secondary/20 p-3">
      <div className="flex items-center gap-2 mb-2">
        <p className="text-[10px] text-muted-foreground flex-1">
          Target aspect <span className="font-mono">{slotAspect}</span> — other aspects still work; Google crops to fit.
          {' '}{items.length}/{maxItems} selected{atMax ? ' (slot full)' : ''}.
        </p>
        <div className="relative">
          <Search className="h-3 w-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Filter by filename"
            className="h-7 w-44 pl-6 text-xs"
          />
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-secondary rounded text-muted-foreground"
          aria-label="Close library"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      {loadError ? (
        <p className="text-[10px] text-red-500 flex items-center gap-1">
          <AlertCircle className="h-3 w-3" /> Library failed to load: {loadError}
        </p>
      ) : assets === null ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-3">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading library…
        </div>
      ) : visible.length === 0 ? (
        <p className="text-xs text-muted-foreground py-3">
          {q ? 'No images match that filename.' : 'No images in the library yet — generate or upload some first.'}
        </p>
      ) : (
        <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-1.5 max-h-56 overflow-y-auto">
          {visible.map(a => {
            const selected = items.includes(a.id);
            const disabled = !selected && atMax;
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => onToggle(a.id)}
                disabled={disabled}
                title={a.filename}
                className={cn(
                  'relative aspect-square rounded border overflow-hidden bg-secondary/30 transition-colors',
                  selected ? 'border-primary ring-1 ring-primary' : 'border-border hover:border-primary/50',
                  disabled && 'opacity-40 cursor-not-allowed',
                )}
              >
                <img
                  src={a.thumbnail_url || a.url}
                  alt={a.filename}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                {selected && (
                  <span className="absolute top-1 right-1 bg-primary text-primary-foreground rounded-full p-0.5">
                    <Check className="h-3 w-3" />
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AiHint({ body }: { body: string }) {
  return (
    <div className="border border-blue-500/20 bg-blue-500/5 rounded-md p-3 text-xs flex items-start gap-2">
      <Sparkles className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
      <p className="text-muted-foreground leading-relaxed">{body}</p>
    </div>
  );
}
