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
  FolderOpen, Search, Check, Clapperboard, Link2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import StudioPanel, {
  type CopyDraftResult,
  type StudioPanelContext,
} from '@/components/studio/StudioPanel';
import {
  studioListSouls,
  videoEngineEstimate,
  type SoulCharacter,
  type StudioJobStatus,
  type VideoEngineEstimate,
} from '@/lib/api';

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
      const saved = localStorage.getItem('pmax-wizard-bundle');
      if (!saved) return EMPTY_BUNDLE;
      // Merge over defaults so bundles saved before new fields (e.g. `brief`)
      // were added don't come back with undefined keys.
      const parsed: PMaxBundle = { ...EMPTY_BUNDLE, ...JSON.parse(saved) };
      // Sanitize image slots on restore: the wizard's own flows (upload /
      // generate / library) only ever produce LOCAL asset UUIDs. A Google
      // resource name (customers/.../assets/...) or bare numeric asset id
      // in a saved bundle means a prior attempt's server-side UUID→resource
      // swap leaked into localStorage — those refs bypass the server's
      // aspect crop on resubmit (the live ASPECT_RATIO_NOT_ALLOWED), so
      // drop them and let the operator re-pick from local sources.
      const isLocalRef = (r: string) => !!r && !/^\d+$/.test(r) && !r.includes('/');
      parsed.logos = (parsed.logos || []).filter(isLocalRef);
      parsed.landscape = (parsed.landscape || []).filter(isLocalRef);
      parsed.square = (parsed.square || []).filter(isLocalRef);
      parsed.portrait = (parsed.portrait || []).filter(isLocalRef);
      return parsed;
    } catch { return EMPTY_BUNDLE; }
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string; campaignId?: string } | null>(null);

  const setField = useCallback(<K extends keyof PMaxBundle>(key: K, value: PMaxBundle[K]) => {
    setBundle(prev => {
      const next = { ...prev, [key]: value };
      try { localStorage.setItem('pmax-wizard-bundle', JSON.stringify(next)); } catch {}
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
          // State keeps raw rows (incl. blank "Add another" rows), so
          // trim + drop empties here.
          audience_signals: bundle.audienceSignals.map(s => s.trim()).filter(Boolean).length
            ? bundle.audienceSignals.map(s => s.trim()).filter(Boolean).map(s => ({ search_theme: s }))
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
      try { localStorage.removeItem('pmax-wizard-bundle'); } catch {}
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
        {stepId === 'videos'   && <StepVideos   bundle={bundle} setField={setField} accountId={accountId} />}
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
  const [resuming, setResuming] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const applyDraft = useCallback((result: CopyDraftResult) => {
    if (result.headlines?.length) setField('headlines', result.headlines);
    if (result.long_headlines?.length) setField('longHeadlines', result.long_headlines);
    if (result.descriptions?.length) setField('descriptions', result.descriptions);
  }, [setField]);

  // Poll-based: the draft takes 1-3 min and a single long request died
  // whenever the dev proxy or a server blipped. Job id lives in
  // localStorage so a page refresh resumes it. Returns the result so
  // StudioPanel can PREVIEW it before the operator applies (copy-mode
  // contract); the refresh-resume path applies directly.
  const pollDraftResult = useCallback(async (draftId: string): Promise<CopyDraftResult> => {
    const started = Date.now();
    while (Date.now() - started < 6 * 60_000) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/pmax/draft-copy/${draftId}`);
        const job = await res.json();
        if (job.status === 'done') {
          localStorage.removeItem('pmax-draft-id');
          return (job.result || {}) as CopyDraftResult;
        }
        if (job.status === 'error') {
          localStorage.removeItem('pmax-draft-id');
          throw new Error(job.message || 'draft failed');
        }
        // still running — keep polling (transient fetch errors just retry)
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
      }
    }
    throw new Error('Draft timed out after 6 minutes — try again.');
  }, []);

  // Host-injected drafter for StudioPanel copy mode — the panel itself
  // never calls PMax endpoints (decoupling rule). The operator's extra
  // intent from the panel's input rides along inside the brief.
  const draftForPanel = useCallback(async (intent: string): Promise<CopyDraftResult> => {
    const brief = intent.trim()
      ? `${bundle.brief}\n\nOperator emphasis for this draft: ${intent.trim()}`.trim()
      : bundle.brief;
    const res = await fetch(`/api/accounts/${accountId}/pmax/draft-copy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        brief,
        final_url: bundle.finalUrl,
        business_name: bundle.businessName,
        campaign_name: bundle.name,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.draft_id) throw new Error(data.detail?.message || data.error || `HTTP ${res.status}`);
    localStorage.setItem('pmax-draft-id', data.draft_id);
    return pollDraftResult(data.draft_id);
  }, [accountId, bundle.brief, bundle.finalUrl, bundle.businessName, bundle.name, pollDraftResult]);

  // Resume polling a draft that was in flight when the page was
  // refreshed — applies directly (the panel may not be open).
  useEffect(() => {
    const pending = localStorage.getItem('pmax-draft-id');
    if (!pending) return;
    setResuming(true);
    pollDraftResult(pending)
      .then(applyDraft)
      .catch(e => setDraftError(e instanceof Error ? e.message : String(e)))
      .finally(() => setResuming(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-5">
      {/* Creative Director draft — opens the shared Studio panel; the
          result previews there before it replaces the lists below. */}
      <div className="border border-border bg-secondary/20 rounded-md p-3 text-xs">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <p className="text-muted-foreground leading-relaxed">
              Let the <b>Creative Director</b> draft headlines and descriptions from your
              brief and landing page ({bundle.finalUrl || 'set the Final URL in step 1'}).
              You preview the draft before it replaces what's typed below.
            </p>
          </div>
          <Button size="sm" onClick={() => setPanelOpen(true)} disabled={resuming || !bundle.finalUrl} className="gap-1.5 shrink-0">
            {resuming ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {resuming ? 'Resuming draft…' : 'Draft with Creative Director'}
          </Button>
        </div>
        {draftError && (
          <p className="mt-2 flex items-center gap-1.5 text-red-500">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {draftError}
          </p>
        )}
      </div>

      <StudioPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        mode="copy"
        accountId={accountId}
        context={{
          brief: bundle.brief,
          businessName: bundle.businessName,
          finalUrl: bundle.finalUrl,
          slot: 'Text assets',
        }}
        onDraftCopy={draftForPanel}
        onUseCopy={applyDraft}
      />
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

/** Per-asset preview metadata for the post-crop preview (no-silent-crop
 * addendum). The actual aspect comes from the loaded image's natural
 * dimensions client-side — DB width/height is null for older uploads. */
interface SlotAssetMeta { url: string; filename: string }

function StepImages({ bundle, setField, accountId }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void; accountId: string }) {
  // Shared campaign context for the StudioPanel each slot opens. Slot
  // label/aspect get appended per slot in ImageGroup.
  const baseContext: StudioPanelContext = {
    brief: bundle.brief,
    businessName: bundle.businessName,
    finalUrl: bundle.finalUrl,
  };
  // id → preview url for every slot item, sourced from the library
  // list and merged with fresh generations/uploads as they land.
  const [assetMeta, setAssetMeta] = useState<Record<string, SlotAssetMeta>>({});
  useEffect(() => {
    let cancelled = false;
    const qs = new URLSearchParams({ asset_type: 'image', limit: '500' });
    if (accountId) qs.set('account_id', accountId);
    fetch(`/api/assets?${qs}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((rows: { id: string; url: string; filename: string }[]) => {
        if (cancelled) return;
        setAssetMeta(prev => {
          const next = { ...prev };
          rows.forEach(r => { next[r.id] = { url: r.url, filename: r.filename }; });
          return next;
        });
      })
      .catch(() => { /* previews degrade to id chips */ });
    return () => { cancelled = true; };
  }, [accountId]);
  const registerAsset = useCallback((id: string, meta: SlotAssetMeta) => {
    setAssetMeta(prev => ({ ...prev, [id]: meta }));
  }, []);

  return (
    <div className="space-y-5">
      <AiHint
        body="Upload assets, pick from the Studio library, or click Generate to open the Studio panel with the slot's aspect locked. Every slot shows the image exactly as Google will receive it — mismatched aspects get center-cropped and are flagged below."
      />
      <ImageGroup
        label="Logos"
        spec="Auto-cropped to 1:1 at submit · min 128×128 · transparent bg preferred"
        slotAspect="1:1"
        googleAspect={1}
        googleAspectLabel="1:1"
        items={bundle.logos}
        onChange={v => setField('logos', v)}
        accountId={accountId}
        minItems={RULES.logos.min}
        maxItems={5}
        promptContext={baseContext}
        assetMeta={assetMeta}
        onAssetKnown={registerAsset}
      />
      <ImageGroup
        label="Landscape marketing image (1.91:1)"
        spec="Any aspect works — auto-cropped to 1.91:1 at submit · min 600×314 · 1200×628 recommended"
        slotAspect="16:9"
        googleAspect={1.91}
        googleAspectLabel="1.91:1"
        items={bundle.landscape}
        onChange={v => setField('landscape', v)}
        accountId={accountId}
        minItems={RULES.landscape.min}
        maxItems={20}
        promptContext={baseContext}
        assetMeta={assetMeta}
        onAssetKnown={registerAsset}
      />
      <ImageGroup
        label="Square marketing image (1:1)"
        spec="Any aspect works — auto-cropped to 1:1 at submit · min 300×300 · 1200×1200 recommended"
        slotAspect="1:1"
        googleAspect={1}
        googleAspectLabel="1:1"
        items={bundle.square}
        onChange={v => setField('square', v)}
        accountId={accountId}
        minItems={RULES.square.min}
        maxItems={20}
        promptContext={baseContext}
        assetMeta={assetMeta}
        onAssetKnown={registerAsset}
      />
      <ImageGroup
        label="Portrait marketing image (4:5)"
        spec="Optional · auto-cropped to 4:5 at submit · min 480×600 · 960×1200 recommended"
        slotAspect="4:5"
        googleAspect={0.8}
        googleAspectLabel="4:5"
        items={bundle.portrait}
        onChange={v => setField('portrait', v)}
        accountId={accountId}
        minItems={0}
        maxItems={20}
        promptContext={baseContext}
        assetMeta={assetMeta}
        onAssetKnown={registerAsset}
      />
    </div>
  );
}

// ── Step 4: Videos — agent-made slideshow ad + YouTube upload ───────

interface StoryScene {
  type: 'logo' | 'hero' | 'broll' | 'stat' | 'cta' | 'higgsfield' | 'soul';
  headline?: string;
  caption?: string;
  scene_label?: string;
  image_filename?: string;
  logo_filename?: string;
  brand_name?: string;
  tagline?: string;
  stat_value?: string;
  stat_label?: string;
  cta?: string;
  composition?: string;
  motion?: string;
  text_treatment?: string;
  _speak_text?: string;
  // higgsfield scenes (Epic 11 P1): an AI-generated clip spliced into
  // the slideshow. Server forces the model + snaps the duration.
  prompt?: string;
  model?: string;
  duration?: number;
  // soul scenes (Epic 11 P2): opening Soul-presenter clip — motion +
  // voiceover, no lip-sync. soul_id is server-resolved, never edited.
  soul_id?: string;
  script?: string;
  look_prompt?: string;
}

interface VideoPanelState {
  imageIds: string[];
  scenes: StoryScene[] | null;
  imageLookup: Record<string, string>;
  renderedAsset: { asset_id: string; url: string; duration?: number } | null;
  // YouTube sub-panel — persisted too so a page refresh mid-flow doesn't
  // wipe the typed title/description, the chosen thumbnail, or the fact
  // that the video was already uploaded (re-uploading made duplicates).
  ytTitle: string;
  ytDescription: string;
  titleOptions: string[];
  thumb: { id: string; url: string } | null;
  uploadedId: string | null;
}

const EMPTY_PANEL: VideoPanelState = {
  imageIds: [], scenes: null, imageLookup: {}, renderedAsset: null,
  ytTitle: '', ytDescription: '', titleOptions: [], thumb: null, uploadedId: null,
};

const VIDEO_PANEL_KEY = 'pmax-video-state';

function StepVideos({ bundle, setField, accountId }: { bundle: PMaxBundle; setField: <K extends keyof PMaxBundle>(k: K, v: PMaxBundle[K]) => void; accountId: string }) {
  // Seed source images from what the operator already picked in StepImages
  // (library/upload UUIDs only — Google resource names can't feed the renderer).
  const [panel, setPanelRaw] = useState<VideoPanelState>(() => {
    try {
      const saved = localStorage.getItem(VIDEO_PANEL_KEY);
      // Merge over defaults so panels saved before the YouTube fields were
      // persisted don't come back with undefined keys.
      if (saved) return { ...EMPTY_PANEL, ...JSON.parse(saved) };
    } catch { /* fall through to seed */ }
    const seeded = Array.from(new Set(
      [...bundle.logos, ...bundle.landscape, ...bundle.square, ...bundle.portrait]
        .filter(id => id && !id.includes('/')),
    )).slice(0, 8);
    return { ...EMPTY_PANEL, imageIds: seeded };
  });
  const setPanel = useCallback((updater: (p: VideoPanelState) => VideoPanelState) => {
    setPanelRaw(prev => {
      const next = updater(prev);
      try { localStorage.setItem(VIDEO_PANEL_KEY, JSON.stringify(next)); } catch { /* quota */ }
      return next;
    });
  }, []);

  const [showPicker, setShowPicker] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  // Epic 11 P1 — opt-in for AI-generated clips inside the slideshow.
  // Off by default: pure hyperframes is free; each clip costs credits.
  const [allowHiggsfield, setAllowHiggsfield] = useState(false);
  // Epic 11 P2 — optional Soul-presenter talking intro (default OFF).
  // Presenter-style: motion + voiceover, no lip-sync. The draft only
  // offers the scene when the picked character is ready server-side.
  const [soulCharacterId, setSoulCharacterId] = useState('');
  const [souls, setSouls] = useState<SoulCharacter[]>([]);
  useEffect(() => {
    let cancelled = false;
    studioListSouls(accountId)
      .then(s => { if (!cancelled) setSouls(s.filter(x => x.status === 'ready' && x.soul_id)); })
      .catch(() => { if (!cancelled) setSouls([]); });
    return () => { cancelled = true; };
  }, [accountId]);
  const [rendering, setRendering] = useState(false);
  const [renderMsg, setRenderMsg] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  // Cost guardrail: summed credit estimate for AI scenes (higgsfield +
  // soul), fetched before the operator clicks Render. Cached clips
  // show as free re-renders.
  const [aiEstimate, setAiEstimate] = useState<VideoEngineEstimate | null>(null);
  const aiSceneCount = useMemo(
    () => (panel.scenes || []).filter(s => s.type === 'higgsfield' || s.type === 'soul').length,
    [panel.scenes],
  );
  const scenesKey = useMemo(() => JSON.stringify(panel.scenes), [panel.scenes]);
  useEffect(() => {
    if (!panel.scenes?.length || aiSceneCount === 0) { setAiEstimate(null); return; }
    let cancelled = false;
    const handle = window.setTimeout(() => {
      videoEngineEstimate({ scenes: panel.scenes as object[], aspect: '16:9' })
        .then(r => { if (!cancelled) setAiEstimate(r); })
        .catch(() => { if (!cancelled) setAiEstimate(null); });
    }, 600);
    return () => { cancelled = true; window.clearTimeout(handle); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenesKey, aiSceneCount]);

  // YouTube connect + upload
  const [ytConnected, setYtConnected] = useState<boolean | null>(null);
  const [connectPolling, setConnectPolling] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadWarning, setUploadWarning] = useState<string | null>(null);

  // YouTube title/description/thumbnail/uploadedId live in the persisted
  // panel (refresh-proof); these setters keep the existing call sites
  // reading naturally. Transient UI state (loaders, errors, toggles)
  // stays in plain useState below.
  const { ytTitle, ytDescription, titleOptions, thumb, uploadedId } = panel;
  const setYtTitle = useCallback((v: string) => setPanel(p => ({ ...p, ytTitle: v })), [setPanel]);
  const setYtDescription = useCallback((v: string) => setPanel(p => ({ ...p, ytDescription: v })), [setPanel]);
  const setTitleOptions = useCallback((v: string[]) => setPanel(p => ({ ...p, titleOptions: v })), [setPanel]);
  const setThumb = useCallback(
    (v: VideoPanelState['thumb'] | ((prev: VideoPanelState['thumb']) => VideoPanelState['thumb'])) =>
      setPanel(p => ({ ...p, thumb: typeof v === 'function' ? v(p.thumb) : v })),
    [setPanel],
  );
  const setUploadedId = useCallback((v: string | null) => setPanel(p => ({ ...p, uploadedId: v })), [setPanel]);

  const [metaLoading, setMetaLoading] = useState(false);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [frames, setFrames] = useState<{ id: string; url: string; t: number }[] | null>(null);
  const [framesLoading, setFramesLoading] = useState(false);
  const [framesError, setFramesError] = useState<string | null>(null);
  const [showFrames, setShowFrames] = useState(false);
  const [showThumbLib, setShowThumbLib] = useState(false);
  const [showThumbGen, setShowThumbGen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/youtube/status')
      .then(r => r.json())
      .then(d => { if (!cancelled) setYtConnected(!!d.connected); })
      .catch(() => { if (!cancelled) setYtConnected(false); });
    return () => { cancelled = true; };
  }, []);

  // Prefill the YouTube title from the campaign name once a render exists.
  useEffect(() => {
    if (panel.renderedAsset && !ytTitle) setYtTitle(bundle.name || 'PMax ad video');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panel.renderedAsset]);

  // ── Draft job ──
  const pollDraft = useCallback(async (jobId: string) => {
    const started = Date.now();
    while (Date.now() - started < 6 * 60_000) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/pmax/video/draft/${jobId}`);
        const job = await res.json();
        if (job.status === 'done') {
          localStorage.removeItem('pmax-video-draft-id');
          setPanel(p => ({ ...p, scenes: job.scenes, imageLookup: job.image_lookup || {}, renderedAsset: null }));
          return;
        }
        if (job.status === 'error') {
          localStorage.removeItem('pmax-video-draft-id');
          throw new Error(job.message || 'draft failed');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
      }
    }
    throw new Error('Script draft timed out after 6 minutes — try again.');
  }, [setPanel]);

  const startDraft = async () => {
    setDrafting(true);
    setDraftError(null);
    try {
      const res = await fetch('/api/pmax/video/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: accountId,
          brief: bundle.brief,
          business_name: bundle.businessName,
          final_url: bundle.finalUrl,
          campaign_name: bundle.name,
          image_ids: panel.imageIds,
          // Epic 11 P1 engine prefs — server caps at 2 and forces the
          // model regardless of what the script agent asks for.
          allow_higgsfield: allowHiggsfield,
          video_model: 'veo3_1_lite',
          max_higgsfield_scenes: 2,
          // Epic 11 P2 — Soul talking intro (server verifies readiness
          // and resolves the higgsfield soul_id itself).
          soul_character_id: soulCharacterId || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.job_id) throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
      localStorage.setItem('pmax-video-draft-id', data.job_id);
      await pollDraft(data.job_id);
    } catch (e) {
      setDraftError(e instanceof Error ? e.message : String(e));
    } finally {
      setDrafting(false);
    }
  };

  // ── Render job ──
  const pollRender = useCallback(async (jobId: string) => {
    const started = Date.now();
    while (Date.now() - started < 15 * 60_000) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/pmax/video/render/${jobId}`);
        const job = await res.json();
        if (job.status === 'done') {
          localStorage.removeItem('pmax-video-render-id');
          setPanel(p => ({ ...p, renderedAsset: { asset_id: job.asset_id, url: job.url, duration: job.duration } }));
          return;
        }
        if (job.status === 'error') {
          localStorage.removeItem('pmax-video-render-id');
          throw new Error(job.message || 'render failed');
        }
        if (job.message) setRenderMsg(job.message);
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
      }
    }
    throw new Error('Render timed out after 15 minutes — check the Studio library; it may still finish.');
  }, [setPanel]);

  const startRender = async () => {
    if (!panel.scenes?.length) return;
    setRendering(true);
    setRenderError(null);
    setRenderMsg('Starting render…');
    try {
      const res = await fetch('/api/pmax/video/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: accountId,
          scenes: panel.scenes,
          sync_audio_to_scenes: true,
          quality: 'draft',
          brief: `PMax ad video — ${bundle.name || 'campaign'}`,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.job_id) throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
      localStorage.setItem('pmax-video-render-id', data.job_id);
      await pollRender(data.job_id);
    } catch (e) {
      setRenderError(e instanceof Error ? e.message : String(e));
    } finally {
      setRendering(false);
      setRenderMsg(null);
    }
  };

  // Resume in-flight jobs after a page refresh (same pattern as StepText).
  useEffect(() => {
    const draftId = localStorage.getItem('pmax-video-draft-id');
    if (draftId) {
      setDrafting(true);
      pollDraft(draftId)
        .catch(e => setDraftError(e instanceof Error ? e.message : String(e)))
        .finally(() => setDrafting(false));
    }
    const renderId = localStorage.getItem('pmax-video-render-id');
    if (renderId) {
      setRendering(true);
      setRenderMsg('Resuming render…');
      pollRender(renderId)
        .catch(e => setRenderError(e instanceof Error ? e.message : String(e)))
        .finally(() => { setRendering(false); setRenderMsg(null); });
    }
    const metaId = localStorage.getItem('pmax-video-meta-id');
    if (metaId) {
      setMetaLoading(true);
      pollMetadata(metaId)
        .catch(e => setMetaError(e instanceof Error ? e.message : String(e)))
        .finally(() => setMetaLoading(false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── YouTube connect + upload ──
  const connectYouTube = async () => {
    setUploadError(null);
    try {
      const res = await fetch('/api/youtube/auth-url');
      const data = await res.json();
      if (!res.ok || !data.auth_url) throw new Error(data.detail || `HTTP ${res.status}`);
      window.open(data.auth_url, '_blank', 'noopener');
      setConnectPolling(true);
      const started = Date.now();
      while (Date.now() - started < 5 * 60_000) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const s = await (await fetch('/api/youtube/status')).json();
          if (s.connected) { setYtConnected(true); break; }
        } catch { /* transient — keep polling */ }
      }
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setConnectPolling(false);
    }
  };

  // Wrong-account recovery: drop the stored token, then run the normal
  // connect flow (auth URL now forces Google's account chooser).
  const switchYouTubeAccount = async () => {
    setUploadError(null);
    try {
      await fetch('/api/youtube/disconnect', { method: 'POST' });
      setYtConnected(false);
      await connectYouTube();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
    }
  };

  // ── YouTube metadata draft (job+poll, same pattern as the script draft) ──
  const pollMetadata = useCallback(async (jobId: string) => {
    const started = Date.now();
    while (Date.now() - started < 6 * 60_000) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/pmax/video/metadata/${jobId}`);
        const job = await res.json();
        if (job.status === 'done') {
          localStorage.removeItem('pmax-video-meta-id');
          const titles: string[] = job.titles || [];
          setTitleOptions(titles);
          if (titles[0]) setYtTitle(titles[0]);          // first option preselected
          if (job.description) setYtDescription(job.description);
          return;
        }
        if (job.status === 'error') {
          localStorage.removeItem('pmax-video-meta-id');
          throw new Error(job.message || 'metadata draft failed');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
      }
    }
    throw new Error('Metadata draft timed out after 6 minutes — try again.');
  }, [setTitleOptions, setYtTitle, setYtDescription]);

  const generateMetadata = async () => {
    setMetaLoading(true);
    setMetaError(null);
    try {
      const res = await fetch('/api/pmax/video/metadata', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: accountId,
          brief: bundle.brief,
          business_name: bundle.businessName,
          final_url: bundle.finalUrl,
          campaign_name: bundle.name,
          scenes: panel.scenes || [],
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.job_id) throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
      localStorage.setItem('pmax-video-meta-id', data.job_id);
      await pollMetadata(data.job_id);
    } catch (e) {
      setMetaError(e instanceof Error ? e.message : String(e));
    } finally {
      setMetaLoading(false);
    }
  };

  // ── Thumbnail: extract 4 frames from the rendered video ──
  const pickFrames = async () => {
    if (frames) { setShowFrames(v => !v); return; }      // already extracted — just toggle
    if (!panel.renderedAsset) return;
    setFramesLoading(true);
    setFramesError(null);
    try {
      const res = await fetch('/api/pmax/video/frames', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_id: panel.renderedAsset.asset_id, account_id: accountId }),
      });
      const data = await res.json();
      if (!res.ok || !data.frames?.length) throw new Error(data.detail?.message || data.detail || `HTTP ${res.status}`);
      setFrames(data.frames);
      setShowFrames(true);
    } catch (e) {
      setFramesError(e instanceof Error ? e.message : String(e));
    } finally {
      setFramesLoading(false);
    }
  };

  // A re-render invalidates the extracted frames (they belong to the old cut).
  useEffect(() => {
    setFrames(null);
    setShowFrames(false);
  }, [panel.renderedAsset?.asset_id]);

  const uploadToYouTube = async () => {
    if (!panel.renderedAsset) return;
    setUploading(true);
    setUploadError(null);
    setUploadWarning(null);
    try {
      const res = await fetch('/api/youtube/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: panel.renderedAsset.asset_id,
          title: ytTitle.trim() || bundle.name || 'PMax ad video',
          description: ytDescription.trim()
            || `${bundle.businessName ? bundle.businessName + ' — ' : ''}${bundle.finalUrl}`.trim(),
          thumbnail_asset_id: thumb?.id || '',
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.video_id) throw new Error(data.detail || `HTTP ${res.status}`);
      setUploadedId(data.video_id);
      if (data.warning) setUploadWarning(data.warning);
      const existing = bundle.videoIds.filter(Boolean);
      if (!existing.includes(data.video_id)) setField('videoIds', [...existing, data.video_id]);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  const setScene = (i: number, patch: Partial<StoryScene>) =>
    setPanel(p => ({ ...p, scenes: (p.scenes || []).map((s, j) => (j === i ? { ...s, ...patch } : s)) }));

  const nImages = panel.imageIds.length;
  const canDraft = nImages >= 3 && nImages <= 8 && !drafting && !rendering;
  const renderEta = panel.scenes ? Math.round((panel.scenes.length / 2) * 75 + 30) : 0;

  return (
    <div className="space-y-5">
      {/* ── Create-a-video panel ── */}
      <div className="border border-border rounded-md bg-secondary/20">
        <div className="px-4 py-3 border-b border-border flex items-center gap-2">
          <Clapperboard className="h-4 w-4 text-primary" />
          <div className="flex-1">
            <p className="text-xs font-medium">Create a video</p>
            <p className="text-[10px] text-muted-foreground">
              Slideshow ad from your images — the agent writes the script, renders the video, and uploads it to YouTube as unlisted.
            </p>
          </div>
        </div>
        <div className="p-4 space-y-4">
          {/* 1 — source images */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium">1 · Source images</span>
              <span className={cn('text-[10px]', nImages < 3 ? 'text-amber-500' : 'text-muted-foreground')}>
                {nImages}/8 selected · pick 3-8
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowPicker(v => !v)}
              className={cn(
                'cursor-pointer border border-dashed border-border rounded-md px-3 py-1.5 text-xs flex items-center gap-1.5 hover:bg-secondary/50 transition-colors',
                showPicker && 'bg-secondary/50 border-solid',
              )}
            >
              <FolderOpen className="h-3.5 w-3.5" />
              {nImages ? `Change images (${nImages})` : 'Pick from library'}
            </button>
            {showPicker && (
              <LibraryPicker
                accountId={accountId}
                items={panel.imageIds}
                onToggle={id => setPanel(p => ({
                  ...p,
                  imageIds: p.imageIds.includes(id)
                    ? p.imageIds.filter(x => x !== id)
                    : p.imageIds.length < 8 ? [...p.imageIds, id] : p.imageIds,
                }))}
                slotAspect="16:9"
                maxItems={8}
                onClose={() => setShowPicker(false)}
              />
            )}
          </div>

          {/* 2 — script draft */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium">2 · Script &amp; storyboard</span>
              {panel.scenes && <span className="text-[10px] text-muted-foreground">{panel.scenes.length} scenes · everything editable</span>}
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <Button size="sm" onClick={startDraft} disabled={!canDraft} className="gap-1.5">
                {drafting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                {drafting ? 'Writing script… 1-3 min (reads your landing page)' : panel.scenes ? 'Rewrite script' : 'Write script & preview storyboard'}
              </Button>
              <label
                className="flex items-center gap-1.5 cursor-pointer select-none text-[10px] text-muted-foreground"
                title="Lets the script use up to 2 AI-generated clips (Veo Lite, about 8 credits each) when no library image fits a beat. Clips are cached — re-renders reuse them for free."
              >
                <input
                  type="checkbox"
                  checked={allowHiggsfield}
                  onChange={e => setAllowHiggsfield(e.target.checked)}
                  disabled={drafting || rendering}
                />
                Allow up to 2 AI clips (costs credits)
              </label>
              <label
                className="flex items-center gap-1.5 select-none text-[10px] text-muted-foreground"
                title={souls.length
                  ? 'Opens the video with a short presenter clip of your trained Soul — motion + voiceover, no lip-sync. Costs credits; cached on re-render.'
                  : 'Train a Soul character in Studio → Souls first (5-15 min), then it appears here.'}
              >
                Talking intro
                <select
                  value={soulCharacterId}
                  onChange={e => setSoulCharacterId(e.target.value)}
                  disabled={drafting || rendering || !souls.length}
                  className="h-6 rounded border border-border bg-background px-1.5 text-[10px] disabled:opacity-50"
                >
                  <option value="">Off</option>
                  {souls.map(s => <option key={s.id} value={s.id}>{s.name} (Soul)</option>)}
                </select>
              </label>
            </div>
            {draftError && (
              <p className="mt-1.5 text-[11px] text-red-500 flex items-center gap-1">
                <AlertCircle className="h-3 w-3 shrink-0" /> {draftError}
              </p>
            )}
            {panel.scenes && (
              <div className="mt-2 space-y-1.5">
                {panel.scenes.map((s, i) => (
                  <SceneRow key={i} index={i} scene={s} imageLookup={panel.imageLookup} onChange={patch => setScene(i, patch)} />
                ))}
              </div>
            )}
          </div>

          {/* 3 — render */}
          {panel.scenes && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-medium">3 · Render</span>
                {!panel.renderedAsset && <span className="text-[10px] text-muted-foreground">~{Math.ceil(renderEta / 60)} min, with voiceover</span>}
              </div>
              <Button size="sm" onClick={startRender} disabled={rendering || drafting} className="gap-1.5">
                {rendering ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Video className="h-3.5 w-3.5" />}
                {rendering ? 'Rendering…' : panel.renderedAsset ? 'Re-render video' : 'Render video'}
              </Button>
              {aiSceneCount > 0 && (
                <p className="mt-1.5 text-[10px] text-warning">
                  {aiEstimate
                    ? <>AI scenes ≈ {aiEstimate.total_credits}{aiEstimate.unknown_count > 0 ? '+' : ''} credits
                        {aiEstimate.cached_hits > 0 ? ` · ${aiEstimate.cached_hits} cached (free)` : ''}
                        {aiEstimate.unknown_count > 0 ? ' · some stages could not be priced' : ''}</>
                    : `${aiSceneCount} AI scene${aiSceneCount > 1 ? 's' : ''} will cost credits at render — estimate unavailable right now`}
                </p>
              )}
              {rendering && renderMsg && (
                <p className="mt-1.5 text-[11px] text-muted-foreground">{renderMsg}</p>
              )}
              {renderError && (
                <p className="mt-1.5 text-[11px] text-red-500 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" /> {renderError}
                </p>
              )}
              {panel.renderedAsset && (
                <div className="mt-2">
                  <video
                    controls
                    src={panel.renderedAsset.url}
                    className="w-full max-w-md rounded-md border border-border bg-black"
                  />
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {panel.renderedAsset.duration ? `${Math.round(panel.renderedAsset.duration)}s · ` : ''}saved to the Studio library
                  </p>
                </div>
              )}
            </div>
          )}

          {/* 4 — YouTube */}
          {panel.renderedAsset && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-medium">4 · YouTube</span>
                <span className="text-[10px] text-muted-foreground">
                  {ytConnected === null ? 'checking…' : ytConnected ? 'channel connected' : 'one-time connect needed'}
                </span>
              </div>
              {ytConnected === false && (
                <div className="space-y-1.5">
                  <Button size="sm" variant="outline" onClick={connectYouTube} disabled={connectPolling} className="gap-1.5">
                    {connectPolling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2 className="h-3.5 w-3.5 text-red-500" />}
                    {connectPolling ? 'Waiting for Google approval…' : 'Connect YouTube'}
                  </Button>
                  <p className="text-[10px] text-muted-foreground">
                    Opens Google consent in a new tab. Approve once with the channel's Google account — this page updates by itself.
                  </p>
                </div>
              )}
              {ytConnected && (
                <div className="space-y-2.5">
                  {/* AI metadata draft — fills title options + description below */}
                  <div>
                    <Button size="sm" variant="outline" onClick={generateMetadata} disabled={metaLoading || uploading} className="gap-1.5">
                      {metaLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      {metaLoading ? 'Drafting title & description… 1-2 min' : 'Generate title & description'}
                    </Button>
                    {metaError && (
                      <p className="mt-1.5 text-[11px] text-red-500 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3 shrink-0" /> {metaError}
                      </p>
                    )}
                  </div>

                  {/* Title + clickable options */}
                  <div className="space-y-1.5">
                    <Input
                      value={ytTitle}
                      onChange={e => setYtTitle(e.target.value.slice(0, 100))}
                      placeholder="Video title"
                      className="text-sm h-8"
                    />
                    {titleOptions.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {titleOptions.map(t => (
                          <button
                            key={t}
                            type="button"
                            onClick={() => setYtTitle(t)}
                            title={t}
                            className={cn(
                              'text-[10px] border rounded-full px-2 py-0.5 max-w-full truncate transition-colors',
                              ytTitle === t
                                ? 'border-primary bg-primary/10 text-foreground'
                                : 'border-border text-muted-foreground hover:border-primary/50',
                            )}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Description — editable; falls back to business + URL when empty */}
                  <textarea
                    value={ytDescription}
                    onChange={e => setYtDescription(e.target.value.slice(0, 5000))}
                    rows={4}
                    placeholder="Video description (optional — Generate fills this; stays editable)"
                    className="w-full text-xs rounded-md border border-border bg-background p-2 resize-y placeholder:text-muted-foreground/60"
                  />

                  {/* Thumbnail: video frame · library image · generated 16:9 */}
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[10px] text-muted-foreground shrink-0">Thumbnail</span>
                      {thumb && (
                        <span className="relative inline-flex shrink-0">
                          <img src={thumb.url} alt="Selected thumbnail" className="h-9 w-16 rounded border border-border object-cover" />
                          <button
                            type="button"
                            onClick={() => setThumb(null)}
                            className="absolute -top-1.5 -right-1.5 bg-background border border-border rounded-full p-0.5 hover:bg-secondary"
                            aria-label="Clear thumbnail"
                          >
                            <X className="h-2.5 w-2.5" />
                          </button>
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={pickFrames}
                        disabled={framesLoading}
                        className={cn(
                          'cursor-pointer border border-dashed border-border rounded-md px-2.5 py-1 text-[11px] flex items-center gap-1.5 hover:bg-secondary/50 transition-colors disabled:opacity-60',
                          showFrames && 'bg-secondary/50 border-solid',
                        )}
                      >
                        {framesLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ImageIcon className="h-3 w-3" />}
                        Pick frame
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowThumbLib(v => !v)}
                        className={cn(
                          'cursor-pointer border border-dashed border-border rounded-md px-2.5 py-1 text-[11px] flex items-center gap-1.5 hover:bg-secondary/50 transition-colors',
                          showThumbLib && 'bg-secondary/50 border-solid',
                        )}
                      >
                        <FolderOpen className="h-3 w-3" />
                        From library
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowThumbGen(true)}
                        className="cursor-pointer border border-dashed border-violet-500/50 rounded-md px-2.5 py-1 text-[11px] flex items-center gap-1.5 hover:bg-violet-500/10 transition-colors text-violet-600 dark:text-violet-300"
                      >
                        <Sparkles className="h-3 w-3" />
                        Generate
                      </button>
                    </div>
                    {framesError && (
                      <p className="mt-1.5 text-[11px] text-red-500 flex items-center gap-1">
                        <AlertCircle className="h-3 w-3 shrink-0" /> {framesError}
                      </p>
                    )}
                    {showFrames && frames && (
                      <div className="flex gap-1.5 mt-1.5 flex-wrap">
                        {frames.map(f => (
                          <button
                            key={f.id}
                            type="button"
                            onClick={() => { setThumb({ id: f.id, url: f.url }); setShowFrames(false); }}
                            className={cn(
                              'relative h-14 aspect-video rounded border overflow-hidden bg-secondary/30 transition-colors',
                              thumb?.id === f.id ? 'border-primary ring-1 ring-primary' : 'border-border hover:border-primary/50',
                            )}
                            title={`Frame at ${f.t}s`}
                          >
                            <img src={f.url} alt={`Frame at ${f.t}s`} className="w-full h-full object-cover" loading="lazy" />
                            <span className="absolute bottom-0.5 right-1 text-[9px] text-white/90 bg-black/50 rounded px-1">{Math.round(f.t)}s</span>
                          </button>
                        ))}
                      </div>
                    )}
                    {showThumbLib && (
                      <LibraryPicker
                        accountId={accountId}
                        items={thumb ? [thumb.id] : []}
                        onToggle={(id, asset) => {
                          setThumb(prev => prev?.id === id ? null : { id, url: asset?.thumbnail_url || asset?.url || '' });
                          setShowThumbLib(false);
                        }}
                        slotAspect="16:9"
                        maxItems={1}
                        onClose={() => setShowThumbLib(false)}
                      />
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={uploadToYouTube} disabled={uploading || !ytTitle.trim()} className="gap-1.5 shrink-0">
                      {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      {uploading ? 'Uploading…' : 'Upload to YouTube'}
                    </Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Uploaded as unlisted — PMax accepts unlisted videos.
                    {' '}
                    <button onClick={switchYouTubeAccount} disabled={connectPolling} className="underline hover:text-foreground disabled:opacity-50">
                      Wrong channel? Switch account
                    </button>
                  </p>
                  {uploadedId && (
                    <p className="text-[11px] text-green-600 dark:text-green-400 flex items-center gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                      Uploaded — video ID <code className="font-mono">{uploadedId}</code> added below.
                    </p>
                  )}
                  {uploadWarning && (
                    <p className="text-[11px] text-amber-600 dark:text-amber-400 flex items-center gap-1.5">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {uploadWarning}
                    </p>
                  )}
                </div>
              )}
              {uploadError && (
                <p className="mt-1.5 text-[11px] text-red-500 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3 shrink-0" /> {uploadError}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Manual entry stays available ── */}
      <p className="text-xs text-muted-foreground">
        PMax requires at least one YouTube video. Paste the video ID (the
        bit after <code>?v=</code> in the YouTube URL) — or use the panel
        above to create and upload one.
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

      {/* Thumbnail generation — shared Studio panel, 16:9 locked
          (YouTube renders thumbnails at 1280×720). "Use in slot"
          pins the chosen image as the thumbnail. */}
      <StudioPanel
        open={showThumbGen}
        onClose={() => setShowThumbGen(false)}
        mode="image"
        accountId={accountId}
        context={{
          brief: bundle.brief,
          businessName: bundle.businessName,
          finalUrl: bundle.finalUrl,
          slot: 'YouTube thumbnail',
          aspect: '16:9',
        }}
        onUse={asset => {
          if (asset.status === 'completed' && asset.asset_id) {
            setThumb({ id: asset.asset_id, url: asset.thumbnail_url || asset.url || '' });
          }
        }}
      />
    </div>
  );
}

/** One editable storyboard scene: type badge + thumbnail + on-screen text +
 * spoken line. Field shown depends on type; everything writes back into the
 * scenes array that the render endpoint consumes unchanged. */
function SceneRow({ index, scene, imageLookup, onChange }: {
  index: number;
  scene: StoryScene;
  imageLookup: Record<string, string>;
  onChange: (patch: Partial<StoryScene>) => void;
}) {
  const thumb = scene.image_filename ? imageLookup[scene.image_filename] : scene.logo_filename ? imageLookup[scene.logo_filename] : null;
  return (
    <div className="border border-border rounded-md bg-background p-2 flex gap-2">
      {thumb ? (
        <img src={thumb} alt="" className="h-14 w-14 rounded object-cover shrink-0 border border-border" loading="lazy" />
      ) : (
        <div className="h-14 w-14 rounded bg-secondary/50 shrink-0 flex items-center justify-center text-[9px] uppercase text-muted-foreground border border-border">
          {scene.type === 'higgsfield' ? 'AI clip' : scene.type === 'soul' ? 'Soul' : scene.type}
        </div>
      )}
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <span className="text-[9px] uppercase tracking-wide font-medium text-muted-foreground shrink-0 w-8">{index + 1} · {scene.type}</span>
          {scene.type === 'broll' && scene.composition && (
            <span className="text-[9px] text-muted-foreground/70 font-mono truncate">{scene.composition} · {scene.motion}</span>
          )}
        </div>
        {scene.type === 'hero' && (
          <Input value={scene.headline || ''} onChange={e => onChange({ headline: e.target.value })} placeholder="Headline" className="h-7 text-xs" />
        )}
        {scene.type === 'broll' && (
          <Input value={scene.caption || ''} onChange={e => onChange({ caption: e.target.value })} placeholder="On-screen caption" className="h-7 text-xs" />
        )}
        {scene.type === 'cta' && (
          <Input value={scene.cta || ''} onChange={e => onChange({ cta: e.target.value })} placeholder="Call to action" className="h-7 text-xs" />
        )}
        {scene.type === 'stat' && (
          <div className="flex gap-1.5">
            <Input value={scene.stat_value || ''} onChange={e => onChange({ stat_value: e.target.value })} placeholder="37" className="h-7 text-xs w-20" />
            <Input value={scene.stat_label || ''} onChange={e => onChange({ stat_label: e.target.value })} placeholder="years of experience" className="h-7 text-xs flex-1" />
          </div>
        )}
        {scene.type === 'logo' && (
          <div className="flex gap-1.5">
            <Input value={scene.brand_name || ''} onChange={e => onChange({ brand_name: e.target.value })} placeholder="Brand name" className="h-7 text-xs flex-1" />
            <Input value={scene.tagline || ''} onChange={e => onChange({ tagline: e.target.value })} placeholder="Tagline" className="h-7 text-xs flex-1" />
          </div>
        )}
        {scene.type === 'soul' && (
          <>
            <Input
              value={scene.look_prompt || ''}
              onChange={e => onChange({ look_prompt: e.target.value })}
              placeholder="Presenter look & setting (optional — e.g. navy suit, bright modern office)"
              className="h-7 text-xs"
            />
            <p className="text-[9px] text-warning">
              Soul presenter clip — speaks the line below (motion + voiceover, no lip-sync) · costs credits at render (cached on re-render)
            </p>
          </>
        )}
        {scene.type === 'higgsfield' && (
          <>
            <Input
              value={scene.prompt || ''}
              onChange={e => onChange({ prompt: e.target.value })}
              placeholder="Cinematic shot description for the AI clip"
              className="h-7 text-xs"
            />
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] text-muted-foreground shrink-0">Clip</span>
              <Input
                type="number" min={2} max={15}
                value={scene.duration ?? 6}
                onChange={e => onChange({ duration: Math.max(2, Math.min(15, Number(e.target.value) || 6)) })}
                className="h-7 w-14 text-xs font-mono"
                title="Seconds. Veo snaps to 4/6/8 server-side."
              />
              <span className="text-[9px] text-warning">
                s · {scene.model || 'veo3_1_lite'} · costs credits at render (cached on re-render)
              </span>
            </div>
          </>
        )}
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] text-muted-foreground shrink-0">Spoken</span>
          <Input
            value={scene._speak_text || ''}
            onChange={e => onChange({ _speak_text: e.target.value })}
            placeholder="Voiceover line for this scene (blank = silent)"
            className="h-7 text-xs flex-1"
          />
        </div>
      </div>
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
        // Store raw rows (same as the text-asset lists) — filtering
        // empties here made "Add another" a no-op: the freshly appended
        // '' row was stripped before it could render. Empties are
        // dropped at submit/review time instead.
        onChange={v => setField('audienceSignals', v)}
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
      <ReviewRow label="Audience signals" value={bundle.audienceSignals.filter(s => s.trim()).length ? bundle.audienceSignals.filter(s => s.trim()).join(', ') : '— (Google explores from scratch)'} />
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
  label, spec, slotAspect, googleAspect, googleAspectLabel,
  items, onChange, accountId, minItems, maxItems = 20, promptContext,
  assetMeta, onAssetKnown,
}: {
  label: string; spec: string; slotAspect: SlotAspect;
  /** Google's EXACT target ratio for this slot (1.91, 1, 0.8) — the
   * post-crop preview frames every item at this ratio. */
  googleAspect: number; googleAspectLabel: string;
  items: string[]; onChange: (v: string[]) => void;
  accountId: string; minItems: number; maxItems?: number;
  promptContext?: StudioPanelContext;
  assetMeta: Record<string, SlotAssetMeta>;
  onAssetKnown: (id: string, meta: SlotAssetMeta) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [showLib, setShowLib] = useState(false);

  // "Use in slot" from the StudioPanel — the chosen asset id is the
  // SAME local-UUID shape upload/library produce, so the orchestrator's
  // aspect-crop bridge resolves it unchanged.
  const handleUse = (asset: StudioJobStatus) => {
    if (asset.status !== 'completed' || !asset.asset_id) return;
    if (asset.url) onAssetKnown(asset.asset_id, { url: asset.url, filename: asset.asset_id });
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
      if (json?.url) onAssetKnown(String(ref), { url: json.url, filename: json.filename || String(ref) });
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
      <div className="flex flex-wrap gap-2 items-start">
        {items.map((ref, i) => {
          const meta = assetMeta[ref];
          if (meta) {
            return (
              <SlotThumb
                key={ref + i}
                meta={meta}
                targetRatio={googleAspect}
                targetLabel={googleAspectLabel}
                onRemove={() => onChange(items.filter((_, j) => j !== i))}
              />
            );
          }
          // No preview available (e.g. a Google resource name that never
          // lived in the local library) — fall back to the id chip.
          return (
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
          );
        })}
        <button
          type="button"
          onClick={() => setPanelOpen(true)}
          className="cursor-pointer border border-dashed border-primary/40 rounded-md px-3 py-1.5 text-xs flex items-center gap-1.5 hover:bg-primary/10 transition-colors text-primary"
          title={`Open the Studio panel with the ${slotAspect} aspect locked to this slot`}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Generate
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
      {/* Shared Studio panel — slides over with the slot's aspect
          locked so the operator can't generate a 16:9 for the square
          group. Stays mounted: jobs keep streaming while it's closed
          and finished results wait on reopen. */}
      <StudioPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        mode="image"
        accountId={accountId}
        context={{
          ...promptContext,
          slot: label,
          aspect: slotAspect,
        }}
        onUse={handleUse}
      />
    </div>
  );
}

/** One slot item rendered AS GOOGLE WILL RECEIVE IT: framed at the
 * slot's exact target ratio with a CSS center-crop (object-cover) —
 * the same crop the server applies at submit. When the source image's
 * own ratio differs by more than 2%, the frame turns amber and a
 * "will be cropped" flag appears (no-silent-crop addendum). */
function SlotThumb({ meta, targetRatio, targetLabel, onRemove }: {
  meta: SlotAssetMeta;
  targetRatio: number;
  targetLabel: string;
  onRemove: () => void;
}) {
  const [naturalRatio, setNaturalRatio] = useState<number | null>(null);
  const mismatch = naturalRatio !== null
    && Math.abs(naturalRatio - targetRatio) / targetRatio > 0.02;
  return (
    <div className="w-32">
      <div
        className={cn(
          'relative rounded-md border overflow-hidden bg-secondary/30 group',
          mismatch ? 'border-warning' : 'border-border',
        )}
        style={{ aspectRatio: String(targetRatio) }}
        title={`${meta.filename} — preview shows the exact ${targetLabel} center-crop Google receives`}
      >
        <img
          src={meta.url}
          alt={meta.filename}
          className="w-full h-full object-cover"
          loading="lazy"
          onLoad={e => {
            const im = e.currentTarget;
            if (im.naturalWidth && im.naturalHeight) {
              setNaturalRatio(im.naturalWidth / im.naturalHeight);
            }
          }}
        />
        <button
          onClick={onRemove}
          className="absolute top-1 right-1 bg-background/80 border border-border rounded-full p-0.5 hover:bg-secondary"
          aria-label="Remove"
        >
          <X className="h-3 w-3" />
        </button>
      </div>
      {mismatch ? (
        <p className="text-[9px] text-warning mt-0.5 flex items-center gap-0.5 leading-tight">
          <AlertCircle className="h-2.5 w-2.5 shrink-0" /> will be cropped to {targetLabel}
        </p>
      ) : (
        <p className="text-[9px] text-muted-foreground mt-0.5 truncate">{targetLabel}</p>
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
 * allowed — the orchestrator center-crops local images to the slot's
 * exact Google aspect at submit — so the target aspect is shown as
 * guidance, not a filter. */
function LibraryPicker({
  accountId, items, onToggle, slotAspect, maxItems, onClose,
}: {
  accountId: string; items: string[];
  // Second arg carries the full asset so single-select callers (YouTube
  // thumbnail) can keep the URL for a preview without re-fetching.
  onToggle: (assetId: string, asset?: LibraryAsset) => void;
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
          Target aspect <span className="font-mono">{slotAspect}</span> — any aspect works; we center-crop to the slot's exact Google ratio at submit (image just needs to be big enough).
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
                onClick={() => onToggle(a.id, a)}
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
