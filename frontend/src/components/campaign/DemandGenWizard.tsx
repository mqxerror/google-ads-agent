/**
 * DemandGenWizard — Demand Gen campaign creation flow.
 *
 * The first-class campaign-creation surface for Demand Gen, mirroring
 * PMaxWizard so the visual builder and the chat agent both drive the SAME
 * `DemandGenOrchestrator` (POST /api/accounts/{id}/campaigns/demand-gen → the
 * MCP `demand_gen_create_demand_gen_campaign` tool's orchestrator). No logic
 * duplication — this is a thin client over the shared recipe.
 *
 * Six steps, each gating the next against Google's hard minimums so the user
 * can't reach Submit with an invalid bundle:
 *   1. Brief & budget  — name, $/day, final URL, business name, bidding.
 *   2. Targeting       — geo include / exclude ids, language ids.
 *   3. Text assets     — headlines (≥1, ≤5, ≤40c), descriptions (≥1, ≤5, ≤90c),
 *                        optional call-to-action text.
 *   4. Image assets    — logos (≥1), landscape 1.91:1 / square 1:1 (≥1 of the
 *                        two), optional portrait 4:5 + tall 9:16. Picked from
 *                        the Studio ad_assets library (generated + uploaded).
 *   5. Channels        — YouTube (in-stream / in-feed / shorts) · Discover ·
 *                        Display · Gmail. Gmail is OFF by default (explicit).
 *   6. Review & submit — created PAUSED; success shows the campaign id.
 *
 * Server-side `demand_gen_orchestrator._validate_bundle` re-checks all of the
 * above; this client mirror keeps Next/Submit disabled until satisfied and
 * surfaces the same errors inline.
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import {
  ArrowLeft, ArrowRight, Megaphone, CheckCircle2, Circle, Plus, X,
  Upload, Image as ImageIcon, Sparkles, Loader2, AlertCircle,
  FolderOpen, Search, Globe, Languages, DollarSign, Video, Compass,
  Monitor, Mail, ShieldAlert,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import StudioPanel, {
  type CopyDraftResult,
  type StudioPanelContext,
} from '@/components/studio/StudioPanel';
import type { StudioJobStatus } from '@/lib/api';

const STEPS = [
  { id: 'brief',     label: 'Brief & budget'   },
  { id: 'targeting', label: 'Targeting'        },
  { id: 'text',      label: 'Text assets'      },
  { id: 'images',    label: 'Image assets'     },
  { id: 'channels',  label: 'Channels'         },
  { id: 'review',    label: 'Review & submit'  },
] as const;

// Google's Demand Gen hard minimums — the orchestrator validates these too;
// this is the client-side mirror so Next/Submit stays disabled until satisfied.
const RULES = {
  headlines:    { min: 1, max: 5, maxChars: 40 },
  descriptions: { min: 1, max: 5, maxChars: 90 },
  businessNameMaxChars: 25,
  logos:        { min: 1, max: 5 },
};

type ChannelKey =
  | 'youtube_in_stream' | 'youtube_in_feed' | 'youtube_shorts'
  | 'discover' | 'display' | 'gmail';

// Order + labels for the channel toggles. Gmail deliberately last + flagged.
const CHANNEL_ROWS: { key: ChannelKey; label: string; hint: string; icon: typeof Video }[] = [
  { key: 'youtube_in_stream', label: 'YouTube — in-stream', hint: 'Skippable ads before/during videos', icon: Video },
  { key: 'youtube_in_feed',   label: 'YouTube — in-feed',   hint: 'Ads in search + related feeds',       icon: Video },
  { key: 'youtube_shorts',    label: 'YouTube — Shorts',    hint: 'Vertical Shorts placements',           icon: Video },
  { key: 'discover',          label: 'Discover',            hint: 'Google Discover feed',                 icon: Compass },
  { key: 'display',           label: 'Display',             hint: 'Gmail-free Display inventory',          icon: Monitor },
  { key: 'gmail',             label: 'Gmail',               hint: 'Promotions/Social inbox tabs',          icon: Mail },
];

interface DGBundle {
  name: string;
  dailyBudget: string;         // dollars; → micros on submit
  finalUrl: string;
  businessName: string;
  brief: string;
  corporateBrand: boolean;     // assisted image gen uses the demand_gen preset
  referenceAssetIds: string[]; // operator's own hotel/property photos (local ids)
  targetCpa: string;           // optional dollars; blank = pure Maximize Conversions
  locationIds: string;         // comma-separated geo target constant ids
  excludedLocationIds: string;
  languageIds: string;         // comma-separated language constant ids
  headlines: string[];
  descriptions: string[];
  ctaText: string;
  logos: string[];             // local ad_asset ids
  landscape: string[];
  square: string[];
  portrait: string[];
  tallPortrait: string[];
  channels: Record<ChannelKey, boolean>;
}

const EMPTY_BUNDLE: DGBundle = {
  name: '', dailyBudget: '', finalUrl: '', businessName: '', brief: '',
  corporateBrand: true, referenceAssetIds: [],
  targetCpa: '', locationIds: '', excludedLocationIds: '', languageIds: '',
  headlines: [''], descriptions: [''], ctaText: '',
  logos: [], landscape: [], square: [], portrait: [], tallPortrait: [],
  channels: {
    youtube_in_stream: true, youtube_in_feed: true, youtube_shorts: true,
    discover: true, display: true, gmail: false,
  },
};

const STORAGE_KEY = 'demandgen-wizard-bundle';

interface DemandGenWizardProps {
  onClose: () => void;
  onBackToTypePicker: () => void;
}

export default function DemandGenWizard({ onClose, onBackToTypePicker }: DemandGenWizardProps) {
  const accountId = useClientAccountId();
  const [stepIdx, setStepIdx] = useState(0);
  const [bundle, setBundle] = useState<DGBundle>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return EMPTY_BUNDLE;
      const parsed: DGBundle = { ...EMPTY_BUNDLE, ...JSON.parse(saved) };
      parsed.channels = { ...EMPTY_BUNDLE.channels, ...(parsed.channels || {}) };
      // Only LOCAL asset ids (upload / generate / library) survive a reload —
      // a Google resource name or bare numeric id leaking back in would bypass
      // the server-side aspect crop on resubmit, so drop those (same guard as
      // PMaxWizard).
      const isLocalRef = (r: string) => !!r && !/^\d+$/.test(r) && !r.includes('/');
      parsed.logos = (parsed.logos || []).filter(isLocalRef);
      parsed.landscape = (parsed.landscape || []).filter(isLocalRef);
      parsed.square = (parsed.square || []).filter(isLocalRef);
      parsed.portrait = (parsed.portrait || []).filter(isLocalRef);
      parsed.tallPortrait = (parsed.tallPortrait || []).filter(isLocalRef);
      // Reference photos are library ids too — keep only local refs so a leaked
      // Google resource name can't ride back in as a bogus reference.
      parsed.referenceAssetIds = (parsed.referenceAssetIds || []).filter(isLocalRef);
      return parsed;
    } catch { return EMPTY_BUNDLE; }
  });
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string; campaignId?: string } | null>(null);

  const setField = useCallback(<K extends keyof DGBundle>(key: K, value: DGBundle[K]) => {
    setBundle(prev => {
      const next = { ...prev, [key]: value };
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const stepId = STEPS[stepIdx].id;

  const stepHint = useMemo(() => {
    const missing: string[] = [];
    if (stepId === 'brief') {
      if (!bundle.name.trim()) missing.push('campaign name');
      if (!(parseFloat(bundle.dailyBudget) > 0)) missing.push('daily budget');
      if (!bundle.finalUrl.trim()) missing.push('final URL');
      if (!bundle.businessName.trim()) missing.push('business name');
      else if (bundle.businessName.length > RULES.businessNameMaxChars) missing.push(`business name over ${RULES.businessNameMaxChars} chars`);
      if (bundle.targetCpa.trim() && !(parseFloat(bundle.targetCpa) > 0)) missing.push('a valid target CPA (or leave it blank)');
    } else if (stepId === 'text') {
      const h = bundle.headlines.filter(s => s.trim());
      const d = bundle.descriptions.filter(s => s.trim());
      if (h.length < RULES.headlines.min) missing.push(`${RULES.headlines.min - h.length} more headline`);
      if (d.length < RULES.descriptions.min) missing.push(`${RULES.descriptions.min - d.length} more description`);
      if (h.some(s => s.length > RULES.headlines.maxChars)) missing.push('a headline is over 40 chars');
      if (d.some(s => s.length > RULES.descriptions.maxChars)) missing.push('a description is over 90 chars');
    } else if (stepId === 'images') {
      if (bundle.logos.length < RULES.logos.min) missing.push('a logo');
      if (bundle.landscape.length + bundle.square.length < 1) missing.push('a landscape or square marketing image');
    } else if (stepId === 'channels') {
      if (!Object.values(bundle.channels).some(Boolean)) missing.push('at least one channel ON');
    }
    return missing.length ? `To continue: ${missing.join(' · ')}` : null;
  }, [stepId, bundle]);

  const stepValid = useMemo(() => {
    switch (stepId) {
      case 'brief': {
        const b = parseFloat(bundle.dailyBudget);
        const cpaOk = !bundle.targetCpa.trim() || parseFloat(bundle.targetCpa) > 0;
        return !!bundle.name.trim()
          && !!bundle.finalUrl.trim()
          && !!bundle.businessName.trim()
          && bundle.businessName.length <= RULES.businessNameMaxChars
          && Number.isFinite(b) && b > 0
          && cpaOk;
      }
      case 'targeting':
        return true; // optional — Google defaults to all-geo / all-language
      case 'text': {
        const h = bundle.headlines.filter(s => s.trim());
        const d = bundle.descriptions.filter(s => s.trim());
        return h.length >= RULES.headlines.min && h.length <= RULES.headlines.max
          && d.length >= RULES.descriptions.min && d.length <= RULES.descriptions.max
          && h.every(s => s.length <= RULES.headlines.maxChars)
          && d.every(s => s.length <= RULES.descriptions.maxChars);
      }
      case 'images':
        return bundle.logos.length >= RULES.logos.min
          && (bundle.landscape.length + bundle.square.length) >= 1;
      case 'channels':
        return Object.values(bundle.channels).some(Boolean);
      case 'review':
        return true;
    }
  }, [stepId, bundle]);

  const parseIds = (raw: string): string[] =>
    raw.split(',').map(s => s.trim()).filter(s => /^\d+$/.test(s));

  const doSubmit = useCallback(async () => {
    if (!accountId) return;
    setConfirmOpen(false);
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const budget_micros = Math.round(parseFloat(bundle.dailyBudget) * 1_000_000);
      const target_cpa_micros = bundle.targetCpa.trim()
        ? Math.round(parseFloat(bundle.targetCpa) * 1_000_000)
        : null;
      const res = await fetch(`/api/accounts/${accountId}/campaigns/demand-gen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: bundle.name,
          budget_micros,
          final_urls: [bundle.finalUrl],
          business_name: bundle.businessName,
          headlines: bundle.headlines.map(s => s.trim()).filter(Boolean),
          descriptions: bundle.descriptions.map(s => s.trim()).filter(Boolean),
          call_to_action_text: bundle.ctaText.trim() || null,
          logos: bundle.logos,
          marketing_images: {
            landscape: bundle.landscape,
            square: bundle.square,
            portrait: bundle.portrait,
            tall_portrait: bundle.tallPortrait,
          },
          channels: bundle.channels,
          target_cpa_micros,
          location_ids: parseIds(bundle.locationIds),
          excluded_location_ids: parseIds(bundle.excludedLocationIds),
          language_ids: parseIds(bundle.languageIds),
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
        message: `Campaign ${json.campaign_id} created (PAUSED). Ad group ${json.ad_group_id}. ${(json.warnings || []).length} warning(s).`,
      });
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
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
            <Megaphone className="h-6 w-6 text-primary" />
            Demand Gen
          </h1>
          <p className="text-sm text-muted-foreground">
            Build a Demand Gen campaign across YouTube, Discover &amp; Display — assets included.
          </p>
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
              {i < stepIdx ? <CheckCircle2 className="h-3 w-3" /> : <Circle className="h-3 w-3" />}
              <span className="whitespace-nowrap">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="h-px flex-1 bg-border mx-1" />}
          </div>
        ))}
      </div>

      <div className="border border-border rounded-lg p-6 bg-card mb-4">
        {stepId === 'brief'     && <StepBrief     bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'targeting' && <StepTargeting bundle={bundle} setField={setField} />}
        {stepId === 'text'      && <StepText      bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'images'    && <StepImages    bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'channels'  && <StepChannels  bundle={bundle} setField={setField} />}
        {stepId === 'review'    && <StepReview    bundle={bundle} submitResult={submitResult} submitting={submitting} />}
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
            <Button onClick={() => setStepIdx(stepIdx + 1)} disabled={!stepValid} className="gap-1.5">
              Next <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        ) : submitResult?.ok ? (
          <Button onClick={onClose} className="gap-1.5">
            <CheckCircle2 className="h-4 w-4" /> Done
          </Button>
        ) : (
          <Button onClick={() => setConfirmOpen(true)} disabled={submitting} className="gap-1.5">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {submitting ? 'Creating...' : 'Create campaign'}
          </Button>
        )}
      </div>

      {/* Confirm-before-create modal */}
      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md border border-border rounded-lg bg-card p-6 shadow-lg">
            <h3 className="text-base font-semibold flex items-center gap-2 mb-2">
              <Megaphone className="h-4 w-4 text-primary" /> Create this Demand Gen campaign?
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              <strong className="text-foreground">“{bundle.name}”</strong> will be created in Google Ads at
              {' '}<strong className="text-foreground">${parseFloat(bundle.dailyBudget || '0').toFixed(2)}/day</strong>.
              It will start <strong className="text-foreground">PAUSED</strong> — no spend until you enable it in the Google Ads UI.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setConfirmOpen(false)}>Cancel</Button>
              <Button size="sm" onClick={doSubmit} className="gap-1.5">
                <Sparkles className="h-3.5 w-3.5" /> Yes, create (PAUSED)
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step components ─────────────────────────────────────────────────

type SetField = <K extends keyof DGBundle>(k: K, v: DGBundle[K]) => void;

function StepBrief({ bundle, setField, accountId }: { bundle: DGBundle; setField: SetField; accountId: string }) {
  const nameOver = bundle.businessName.length > RULES.businessNameMaxChars;
  const [showRefLib, setShowRefLib] = useState(false);
  // Preview meta for the attached reference chips (id → url/filename), sourced
  // from the same ad_assets library the picker reads.
  const [refMeta, setRefMeta] = useState<Record<string, SlotAssetMeta>>({});
  useEffect(() => {
    let cancelled = false;
    const qs = new URLSearchParams({ asset_type: 'image', limit: '500' });
    if (accountId) qs.set('account_id', accountId);
    fetch(`/api/assets?${qs}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((rows: { id: string; url: string; filename: string }[]) => {
        if (cancelled) return;
        setRefMeta(prev => {
          const next = { ...prev };
          rows.forEach(r => { next[r.id] = { url: r.url, filename: r.filename }; });
          return next;
        });
      })
      .catch(() => { /* chips degrade to placeholder tiles */ });
    return () => { cancelled = true; };
  }, [accountId]);

  const toggleRef = (id: string, asset?: LibraryAsset) => {
    if (asset?.url) setRefMeta(prev => ({ ...prev, [id]: { url: asset.url, filename: asset.filename } }));
    const cur = bundle.referenceAssetIds;
    setField('referenceAssetIds', cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id]);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium mb-1.5 block">Campaign name *</label>
        <Input value={bundle.name} onChange={e => setField('name', e.target.value)} placeholder="e.g. Panama QIV — Demand Gen — May 2026" />
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 block">Daily budget (USD) *</label>
        <Input type="number" step="0.01" min="0.01" value={bundle.dailyBudget} onChange={e => setField('dailyBudget', e.target.value)} placeholder="50.00" />
        <p className="text-[10px] text-muted-foreground mt-1">Average daily ≈ this number; Google may spend up to ~2× on high-traffic days.</p>
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 block">Final URL *</label>
        <Input value={bundle.finalUrl} onChange={e => setField('finalUrl', e.target.value)} placeholder="https://goldenvisas.mercan.com/panama" />
      </div>
      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <label className="text-xs font-medium">Business name *</label>
          <span className={cn('text-[10px] tabular-nums', nameOver ? 'text-red-500' : 'text-muted-foreground')}>
            {bundle.businessName.length}/{RULES.businessNameMaxChars}
          </span>
        </div>
        <Input
          value={bundle.businessName}
          onChange={e => setField('businessName', e.target.value.slice(0, RULES.businessNameMaxChars))}
          placeholder="Mercan"
          className={cn(nameOver && 'border-red-500')}
        />
        <p className="text-[10px] text-muted-foreground mt-1">Shown on the ad; keep it short and brand-faithful (≤{RULES.businessNameMaxChars} chars).</p>
      </div>

      {/* Campaign brief — fuels the assisted copy + image drafts */}
      <div>
        <label className="text-xs font-medium mb-1.5 block">Campaign brief (optional)</label>
        <textarea
          value={bundle.brief}
          onChange={e => setField('brief', e.target.value)}
          rows={3}
          placeholder="Who is this for, what's the offer, what makes it different? The Creative Director uses this (plus your landing page) to draft the business name, headlines & descriptions in the Text step — and to generate on-brand images in the Assets step."
          className="w-full text-sm rounded-md border border-border bg-background p-2.5 resize-none placeholder:text-muted-foreground/60"
        />
      </div>

      {/* Corporate-brand toggle — drives the demand_gen image preset */}
      <label className="flex items-start gap-2 cursor-pointer select-none border border-border rounded-md p-3 bg-secondary/20">
        <input
          type="checkbox"
          checked={bundle.corporateBrand}
          onChange={e => setField('corporateBrand', e.target.checked)}
          className="mt-0.5"
        />
        <span>
          <span className="text-xs font-medium">Corporate-brand images</span>
          <span className="block text-[10px] text-muted-foreground mt-0.5">
            Generated images use the Demand Gen preset — premium, editorial, text-free (Google renders the headline itself, so baked-in text gets disapproved). Turn off for a looser creative style.
          </span>
        </span>
      </label>

      {/* Reference photos — anchor image generation to the operator's real assets */}
      <div className="border border-border rounded-md p-3 bg-secondary/20 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <ImageIcon className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
            <div>
              <span className="text-xs font-medium">Reference photos (optional)</span>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Attach your OWN hotel / property photos from the library. Image generation in the Assets step anchors to these real subjects instead of inventing a generic scene.
              </p>
            </div>
          </div>
          <Button size="sm" variant="outline" onClick={() => setShowRefLib(v => !v)} className="gap-1.5 shrink-0">
            <FolderOpen className="h-3.5 w-3.5" />
            {bundle.referenceAssetIds.length ? `${bundle.referenceAssetIds.length} attached` : 'Attach'}
          </Button>
        </div>
        {bundle.referenceAssetIds.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {bundle.referenceAssetIds.map(id => {
              const meta = refMeta[id];
              return (
                <span key={id} className="relative inline-flex">
                  {meta ? (
                    <img src={meta.url} alt={meta.filename} className="h-12 w-12 rounded border border-border object-cover" loading="lazy" />
                  ) : (
                    <span className="h-12 w-12 rounded border border-border bg-secondary/40 flex items-center justify-center">
                      <ImageIcon className="h-4 w-4 text-muted-foreground" />
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => toggleRef(id)}
                    className="absolute -top-1.5 -right-1.5 bg-background border border-border rounded-full p-0.5 hover:bg-secondary"
                    aria-label="Remove reference"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </span>
              );
            })}
          </div>
        )}
        {showRefLib && (
          <LibraryPicker
            accountId={accountId}
            items={bundle.referenceAssetIds}
            onToggle={toggleRef}
            targetLabel="reference"
            maxItems={6}
            onClose={() => setShowRefLib(false)}
          />
        )}
      </div>

      {/* Bidding */}
      <div className="border border-border rounded-md p-3 bg-secondary/20">
        <div className="flex items-center gap-2 mb-1.5">
          <DollarSign className="h-3.5 w-3.5 text-primary" />
          <span className="text-xs font-semibold">Bidding — Maximize Conversions</span>
        </div>
        <p className="text-[10px] text-muted-foreground mb-2">
          Demand Gen bids to get the most conversions for your budget. Add an optional target CPA to steer toward a cost-per-conversion.
        </p>
        <label className="text-xs font-medium mb-1.5 block">Target CPA (USD, optional)</label>
        <Input
          type="number" step="0.01" min="0.01"
          value={bundle.targetCpa}
          onChange={e => setField('targetCpa', e.target.value)}
          placeholder="Leave blank for pure Maximize Conversions"
        />
      </div>
    </div>
  );
}

function StepTargeting({ bundle, setField }: { bundle: DGBundle; setField: SetField }) {
  return (
    <div className="space-y-4">
      <p className="text-[11px] text-muted-foreground leading-relaxed border border-border bg-secondary/20 rounded-md p-3">
        Targeting is optional — leave a field empty and Google targets all locations / all languages. Enter Google
        {' '}<b>geo target constant IDs</b> and <b>language constant IDs</b> (comma-separated numbers). Common ids:
        {' '}<span className="font-mono">2840</span> = United States · <span className="font-mono">2826</span> = United Kingdom ·
        {' '}<span className="font-mono">2124</span> = Canada · language <span className="font-mono">1000</span> = English ·
        {' '}<span className="font-mono">1003</span> = Spanish.
      </p>
      <div>
        <label className="text-xs font-medium flex items-center gap-1.5 mb-1.5"><Globe className="h-3.5 w-3.5" /> Included locations (geo ids)</label>
        <Input value={bundle.locationIds} onChange={e => setField('locationIds', e.target.value)} placeholder="2840, 2826" />
      </div>
      <div>
        <label className="text-xs font-medium flex items-center gap-1.5 mb-1.5"><Globe className="h-3.5 w-3.5 text-red-500" /> Excluded locations (geo ids)</label>
        <Input value={bundle.excludedLocationIds} onChange={e => setField('excludedLocationIds', e.target.value)} placeholder="e.g. 1014044 (a metro to carve out)" />
        <p className="text-[10px] text-muted-foreground mt-1">Negative geo criteria — carve regions OUT of the included target.</p>
      </div>
      <div>
        <label className="text-xs font-medium flex items-center gap-1.5 mb-1.5"><Languages className="h-3.5 w-3.5" /> Languages (language ids)</label>
        <Input value={bundle.languageIds} onChange={e => setField('languageIds', e.target.value)} placeholder="1000" />
      </div>
    </div>
  );
}

function StepText({ bundle, setField, accountId }: { bundle: DGBundle; setField: SetField; accountId: string }) {
  const [resuming, setResuming] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  // A DG draft fills business_name (Brief step), headlines + descriptions.
  const applyDraft = useCallback((result: CopyDraftResult) => {
    if (result.business_name) setField('businessName', result.business_name.slice(0, RULES.businessNameMaxChars));
    if (result.headlines?.length) setField('headlines', result.headlines);
    if (result.descriptions?.length) setField('descriptions', result.descriptions);
  }, [setField]);

  // Poll-based (mirrors PMax): the draft takes 1-3 min and a single long
  // request died whenever the dev proxy or a server blipped. The job id lives
  // in localStorage so a page refresh resumes it.
  const pollDraftResult = useCallback(async (draftId: string): Promise<CopyDraftResult> => {
    const started = Date.now();
    while (Date.now() - started < 6 * 60_000) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const res = await fetch(`/api/demand-gen/draft-copy/${draftId}`);
        const job = await res.json();
        if (job.status === 'done') {
          localStorage.removeItem('demandgen-draft-id');
          return (job.result || {}) as CopyDraftResult;
        }
        if (job.status === 'error') {
          localStorage.removeItem('demandgen-draft-id');
          throw new Error(job.message || 'draft failed');
        }
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to fetch') throw e;
      }
    }
    throw new Error('Draft timed out after 6 minutes — try again.');
  }, []);

  // Host-injected drafter for StudioPanel copy mode — the panel never calls a
  // campaign-specific endpoint itself. The operator's extra intent from the
  // panel's input rides along inside the brief.
  const draftForPanel = useCallback(async (intent: string): Promise<CopyDraftResult> => {
    const brief = intent.trim()
      ? `${bundle.brief}\n\nOperator emphasis for this draft: ${intent.trim()}`.trim()
      : bundle.brief;
    const res = await fetch(`/api/accounts/${accountId}/demand-gen/draft-copy`, {
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
    localStorage.setItem('demandgen-draft-id', data.draft_id);
    return pollDraftResult(data.draft_id);
  }, [accountId, bundle.brief, bundle.finalUrl, bundle.businessName, bundle.name, pollDraftResult]);

  // Resume a draft that was in flight when the page was refreshed — applies
  // directly (the panel may not be open).
  useEffect(() => {
    const pending = localStorage.getItem('demandgen-draft-id');
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
      {/* Creative Director draft — opens the shared Studio panel; the result
          previews there before it replaces the fields below (+ business name). */}
      <div className="border border-border bg-secondary/20 rounded-md p-3 text-xs">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <p className="text-muted-foreground leading-relaxed">
              Let the <b>Creative Director</b> draft the business name, headlines and descriptions from your
              brief and landing page ({bundle.finalUrl || 'set the Final URL in step 1'}).
              You preview the draft before it replaces what's below.
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

      <PolicyHint />
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
        label="Descriptions"
        hint={`≥${RULES.descriptions.min}, each ≤${RULES.descriptions.maxChars} chars · up to ${RULES.descriptions.max}`}
        items={bundle.descriptions}
        onChange={v => setField('descriptions', v)}
        maxChars={RULES.descriptions.maxChars}
        minItems={RULES.descriptions.min}
        maxItems={RULES.descriptions.max}
      />
      <div>
        <label className="text-xs font-medium mb-1.5 block">Call to action (optional)</label>
        <Input value={bundle.ctaText} onChange={e => setField('ctaText', e.target.value)} placeholder="e.g. Learn more, Get started, Apply now" />
        <p className="text-[10px] text-muted-foreground mt-1">Leave blank to let Google auto-select the CTA label.</p>
      </div>
    </div>
  );
}

/** Compliance reminder near the copy fields — the same policy traps that get
 * Demand Gen ads disapproved. Not enforced client-side (the account's own
 * policy differs), just surfaced. */
function PolicyHint() {
  return (
    <div className="border border-amber-500/30 bg-amber-500/5 rounded-md p-3 text-[11px] leading-relaxed">
      <div className="flex items-start gap-2">
        <ShieldAlert className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
        <p className="text-muted-foreground">
          <b className="text-foreground">Policy hints:</b> no prices or discounts in the copy · no citizenship / guaranteed-approval
          {' '}promises · avoid the symbols <span className="font-mono">~ | +</span> (Google flags them as gimmicky punctuation).
        </p>
      </div>
    </div>
  );
}

// ── Image assets ────────────────────────────────────────────────────

interface SlotAssetMeta { url: string; filename: string }

function StepImages({ bundle, setField, accountId }: { bundle: DGBundle; setField: SetField; accountId: string }) {
  // id → preview meta, sourced from the ad_assets library and merged with
  // fresh uploads as they land.
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

  // A short note naming the attached reference photos (filenames) so every
  // generated variant anchors to those real subjects, not a generic scene.
  const referenceNote = useMemo(() => {
    if (!bundle.referenceAssetIds.length) return undefined;
    const names = bundle.referenceAssetIds.map(id => assetMeta[id]?.filename).filter(Boolean);
    return names.length ? names.join(', ') : `${bundle.referenceAssetIds.length} attached image(s)`;
  }, [bundle.referenceAssetIds, assetMeta]);

  // Shared context every slot's StudioPanel opens with. The corporate-brand
  // toggle picks the demand_gen preset; the operator's reference photos condition
  // the generation. Slot label + aspect get appended per group in ImageGroup.
  const baseContext: StudioPanelContext = {
    brief: bundle.brief,
    businessName: bundle.businessName,
    finalUrl: bundle.finalUrl,
    preset: bundle.corporateBrand ? 'demand_gen' : undefined,
    referenceAssetIds: bundle.referenceAssetIds.length ? bundle.referenceAssetIds : undefined,
    referenceNote,
  };

  return (
    <div className="space-y-5">
      <div className="border border-border bg-secondary/20 rounded-md p-3 text-[11px] leading-relaxed text-muted-foreground">
        <b className="text-foreground">Generate</b> on-brand images per slot (the aspect is locked to the slot), pick from the
        {' '}Studio asset library, or upload files. Generated images anchor to your reference photos from step 1 and land in the
        {' '}library. Each slot shows the image exactly as Google will receive it — mismatched aspects get center-cropped at submit and are flagged.
      </div>
      <ImageGroup
        label="Logos" spec="Auto-cropped to 1:1 · min 128×128 · transparent bg preferred"
        targetRatio={1} targetLabel="1:1" slotAspect="1:1"
        items={bundle.logos} onChange={v => setField('logos', v)}
        accountId={accountId} minItems={RULES.logos.min} maxItems={RULES.logos.max}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <ImageGroup
        label="Landscape marketing image (1.91:1)" spec="Any aspect works — cropped to 1.91:1 · min 600×314 · 1200×628 recommended"
        targetRatio={1.91} targetLabel="1.91:1" slotAspect="16:9"
        items={bundle.landscape} onChange={v => setField('landscape', v)}
        accountId={accountId} minItems={0} maxItems={20}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <ImageGroup
        label="Square marketing image (1:1)" spec="Any aspect works — cropped to 1:1 · min 300×300 · 1200×1200 recommended"
        targetRatio={1} targetLabel="1:1" slotAspect="1:1"
        items={bundle.square} onChange={v => setField('square', v)}
        accountId={accountId} minItems={0} maxItems={20}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <p className="text-[10px] text-muted-foreground -mt-2">Provide at least one landscape or square marketing image. Portrait &amp; tall are optional extras.</p>
      <ImageGroup
        label="Portrait marketing image (4:5)" spec="Optional · cropped to 4:5 · min 480×600 · 960×1200 recommended"
        targetRatio={0.8} targetLabel="4:5" slotAspect="4:5"
        items={bundle.portrait} onChange={v => setField('portrait', v)}
        accountId={accountId} minItems={0} maxItems={20}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <ImageGroup
        label="Tall portrait image (9:16)" spec="Optional · cropped to 9:16 · for YouTube Shorts placements"
        targetRatio={0.5625} targetLabel="9:16" slotAspect="9:16"
        items={bundle.tallPortrait} onChange={v => setField('tallPortrait', v)}
        accountId={accountId} minItems={0} maxItems={20}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
    </div>
  );
}

function StepChannels({ bundle, setField }: { bundle: DGBundle; setField: SetField }) {
  const toggle = (key: ChannelKey) => {
    setField('channels', { ...bundle.channels, [key]: !bundle.channels[key] });
  };
  const anyOn = Object.values(bundle.channels).some(Boolean);
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-muted-foreground leading-relaxed">
        Choose where the ad can show. At least one channel must stay ON. <b>Gmail is OFF by default</b> — turn it on
        {' '}deliberately if you want inbox placements.
      </p>
      <div className="space-y-2">
        {CHANNEL_ROWS.map(({ key, label, hint, icon: Icon }) => {
          const on = bundle.channels[key];
          const isGmail = key === 'gmail';
          return (
            <button
              key={key}
              type="button"
              onClick={() => toggle(key)}
              className={cn(
                'w-full flex items-center gap-3 rounded-md border p-3 text-left transition-colors',
                on ? 'border-primary/50 bg-primary/5' : 'border-border bg-card hover:bg-secondary/40',
              )}
            >
              <Icon className={cn('h-4 w-4 shrink-0', on ? 'text-primary' : 'text-muted-foreground')} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium flex items-center gap-2">
                  {label}
                  {isGmail && (
                    <span className="text-[9px] uppercase tracking-wide rounded px-1.5 py-0.5 bg-amber-500/15 text-amber-600 dark:text-amber-400">
                      off by default
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-muted-foreground">{hint}</div>
              </div>
              {/* Switch */}
              <span className={cn(
                'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
                on ? 'bg-primary' : 'bg-secondary border border-border',
              )}>
                <span className={cn(
                  'inline-block h-3.5 w-3.5 rounded-full bg-background shadow transition-transform',
                  on ? 'translate-x-4' : 'translate-x-1',
                )} />
              </span>
            </button>
          );
        })}
      </div>
      {!anyOn && (
        <p className="text-[11px] text-warning flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5" /> At least one channel must be enabled.
        </p>
      )}
    </div>
  );
}

function StepReview({ bundle, submitResult, submitting }: {
  bundle: DGBundle;
  submitResult: { ok: boolean; message: string; campaignId?: string } | null;
  submitting: boolean;
}) {
  const activeChannels = CHANNEL_ROWS.filter(c => bundle.channels[c.key]).map(c => c.label);
  const geo = (raw: string) => raw.split(',').map(s => s.trim()).filter(Boolean);
  return (
    <div className="space-y-4 text-sm">
      <ReviewRow label="Campaign name" value={bundle.name} />
      <ReviewRow label="Daily budget" value={`$${parseFloat(bundle.dailyBudget || '0').toFixed(2)}/d`} />
      <ReviewRow label="Bidding" value={bundle.targetCpa.trim() ? `Maximize Conversions · tCPA $${parseFloat(bundle.targetCpa).toFixed(2)}` : 'Maximize Conversions'} />
      <ReviewRow label="Final URL" value={bundle.finalUrl} />
      <ReviewRow label="Business name" value={bundle.businessName} />
      <ReviewRow label="Targeting" value={`geo incl: ${geo(bundle.locationIds).join(', ') || 'all'} · geo excl: ${geo(bundle.excludedLocationIds).join(', ') || 'none'} · lang: ${geo(bundle.languageIds).join(', ') || 'all'}`} />
      <ReviewRow label="Text assets" value={`${bundle.headlines.filter(s => s.trim()).length} headlines · ${bundle.descriptions.filter(s => s.trim()).length} descriptions${bundle.ctaText.trim() ? ` · CTA "${bundle.ctaText.trim()}"` : ''}`} />
      <ReviewRow label="Image assets" value={`${bundle.logos.length} logo · ${bundle.landscape.length} landscape · ${bundle.square.length} square · ${bundle.portrait.length} portrait · ${bundle.tallPortrait.length} tall`} />
      <ReviewRow label="Channels" value={activeChannels.join(', ') || '—'} />
      <div className="mt-4 border border-amber-500/30 bg-amber-500/5 rounded-md p-3 text-xs">
        <strong>Campaign will be created PAUSED.</strong> Review the ad + channels in the Google Ads UI before enabling — once enabled, it starts spending immediately.
      </div>
      {submitResult && (
        <div className={cn(
          'mt-3 rounded-md p-3 text-xs flex items-start gap-2',
          submitResult.ok ? 'border border-green-500/30 bg-green-500/5 text-green-700 dark:text-green-300' : 'border border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300'
        )}>
          {submitResult.ok ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" /> : <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />}
          <span>
            {submitResult.message}
            {submitResult.ok && submitResult.campaignId && (
              <> <span className="font-mono font-semibold">#{submitResult.campaignId}</span></>
            )}
          </span>
        </div>
      )}
      {submitting && (
        <div className="text-xs text-muted-foreground flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Creating budget, campaign, targeting, assets, and ad...
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

// ── Reusable building blocks (mirrors PMaxWizard) ───────────────────

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
  const filled = items.filter(s => s.trim()).length;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs font-medium">{label}</label>
        <span className={cn('text-[10px]', filled < minItems ? 'text-amber-500' : 'text-muted-foreground')}>
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
              item.length > maxChars * 0.9 ? 'text-amber-500' : 'text-muted-foreground',
            )}>
              {item.length}/{maxChars}
            </span>
            <button onClick={() => removeRow(i)} className="p-1 hover:bg-secondary rounded text-muted-foreground" aria-label="Remove">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        {items.length < maxItems && (
          <button onClick={addRow} className="text-xs text-primary hover:underline flex items-center gap-1">
            <Plus className="h-3 w-3" /> Add another
          </button>
        )}
      </div>
    </div>
  );
}

function ImageGroup({
  label, spec, targetRatio, targetLabel, slotAspect,
  items, onChange, accountId, minItems, maxItems = 20,
  assetMeta, onAssetKnown, promptContext,
}: {
  label: string; spec: string; targetRatio: number; targetLabel: string;
  /** Higgsfield generation aspect for this slot (e.g. '16:9' for the 1.91:1
   * landscape — the closest supported aspect; the server center-crops the
   * negligible difference at submit). Locks the StudioPanel aspect selector. */
  slotAspect: string;
  items: string[]; onChange: (v: string[]) => void;
  accountId: string; minItems: number; maxItems?: number;
  assetMeta: Record<string, SlotAssetMeta>;
  onAssetKnown: (id: string, meta: SlotAssetMeta) => void;
  /** Shared campaign context for the Generate panel (brief, business name,
   * demand_gen preset, reference photos). Slot label + aspect appended here. */
  promptContext?: StudioPanelContext;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showLib, setShowLib] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);

  const toggleLibraryAsset = (assetId: string, asset?: LibraryAsset) => {
    if (asset?.url) onAssetKnown(assetId, { url: asset.url, filename: asset.filename });
    if (items.includes(assetId)) {
      onChange(items.filter((id) => id !== assetId));
    } else if (items.length < maxItems) {
      onChange([...items, assetId]);
    }
  };

  // "Use in slot" from the StudioPanel — the asset id is the same local-UUID
  // shape upload/library produce, so the orchestrator's aspect-crop bridge
  // resolves it unchanged at submit.
  const handleUse = (asset: StudioJobStatus) => {
    if (asset.status !== 'completed' || !asset.asset_id) return;
    if (asset.url) onAssetKnown(asset.asset_id, { url: asset.url, filename: asset.asset_id });
    if (items.includes(asset.asset_id)) return;
    if (items.length >= maxItems) return;
    onChange([...items, asset.asset_id]);
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
      const ref = json?.id || json?.asset_id || json?.resource_name;
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
        <span className={cn('text-[10px]', items.length < minItems ? 'text-amber-500' : 'text-muted-foreground')}>
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
                targetRatio={targetRatio}
                targetLabel={targetLabel}
                onRemove={() => onChange(items.filter((_, j) => j !== i))}
              />
            );
          }
          return (
            <div key={ref + i} className="flex items-center gap-1 border border-border rounded-md px-2 py-1 text-xs bg-secondary/30">
              <ImageIcon className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="font-mono text-[10px] truncate max-w-[200px]">{ref}</span>
              <button onClick={() => onChange(items.filter((_, j) => j !== i))} className="ml-1 hover:bg-secondary rounded p-0.5" aria-label="Remove">
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
          uploading && 'opacity-60 pointer-events-none',
        )}>
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {uploading ? 'Uploading...' : 'Upload'}
          <input
            type="file" accept="image/*" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); e.target.value = ''; }}
          />
        </label>
      </div>
      {error && (
        <p className="text-[10px] text-red-500 mt-1 flex items-center gap-1">
          <AlertCircle className="h-3 w-3" /> {error}
        </p>
      )}
      {showLib && (
        <LibraryPicker
          accountId={accountId}
          items={items}
          onToggle={toggleLibraryAsset}
          targetLabel={targetLabel}
          maxItems={maxItems}
          onClose={() => setShowLib(false)}
        />
      )}
      {/* Shared Studio panel — slot's aspect locked so the operator can't
          generate a 16:9 for the square slot. Stays mounted: jobs keep
          streaming while it's closed and finished results wait on reopen. */}
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

/** One slot item rendered as Google will receive it: framed at the slot's
 * exact target ratio with a CSS center-crop. When the source ratio differs by
 * >2%, the frame turns amber and a "will be cropped" flag appears. */
function SlotThumb({ meta, targetRatio, targetLabel, onRemove }: {
  meta: SlotAssetMeta; targetRatio: number; targetLabel: string; onRemove: () => void;
}) {
  const [naturalRatio, setNaturalRatio] = useState<number | null>(null);
  const mismatch = naturalRatio !== null && Math.abs(naturalRatio - targetRatio) / targetRatio > 0.02;
  return (
    <div className="w-32">
      <div
        className={cn('relative rounded-md border overflow-hidden bg-secondary/30 group', mismatch ? 'border-warning' : 'border-border')}
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
            if (im.naturalWidth && im.naturalHeight) setNaturalRatio(im.naturalWidth / im.naturalHeight);
          }}
        />
        <button onClick={onRemove} className="absolute top-1 right-1 bg-background/80 border border-border rounded-full p-0.5 hover:bg-secondary" aria-label="Remove">
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

interface LibraryAsset {
  id: string;
  filename: string;
  url: string;
  thumbnail_url?: string | null;
  created_at: string;
}

/** Inline expanding panel listing the account's existing image assets
 * (Higgsfield generations + uploads), newest first. Clicking a tile toggles
 * its ad_asset id in/out of the slot. Aspect mismatches are allowed — the
 * orchestrator center-crops to the slot's exact Google aspect at submit. */
function LibraryPicker({
  accountId, items, onToggle, targetLabel, maxItems, onClose,
}: {
  accountId: string; items: string[];
  onToggle: (assetId: string, asset?: LibraryAsset) => void;
  targetLabel: string; maxItems: number; onClose: () => void;
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
          Target aspect <span className="font-mono">{targetLabel}</span> — any aspect works; we center-crop to the slot's exact Google ratio at submit.
          {' '}{items.length}/{maxItems} selected{atMax ? ' (slot full)' : ''}.
        </p>
        <div className="relative">
          <Search className="h-3 w-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter by filename" className="h-7 w-44 pl-6 text-xs" />
        </div>
        <button onClick={onClose} className="p-1 hover:bg-secondary rounded text-muted-foreground" aria-label="Close library">
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
                <img src={a.thumbnail_url || a.url} alt={a.filename} className="w-full h-full object-cover" loading="lazy" />
                {selected && (
                  <span className="absolute top-0.5 right-0.5 bg-primary text-primary-foreground rounded-full p-0.5">
                    <CheckCircle2 className="h-3 w-3" />
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
