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
import { useDemandGenRules } from '@/lib/creativeSpecs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import DraftManager from '@/components/creative/DraftManager';
import TextWorkbench from '@/components/creative/TextWorkbench';
import { useDraftJob, type CopyJobResult } from '@/components/creative/useDraftJob';
import { useAngles } from '@/lib/angles';
import { distributeRows, toRows, buildDiversifyBody, type CopyRow } from '@/lib/copyRows';
import { findNearDupPairs } from '@/lib/nearDup';
import CoveragePanel from '@/components/creative/CoveragePanel';
import BrandKitPanel from '@/components/creative/BrandKitPanel';
import PolicyHintCard from '@/components/creative/PolicyHintCard';
import BusinessNameField from '@/components/creative/BusinessNameField';
import BrandPresetToggle from '@/components/creative/BrandPresetToggle';
import ReferencePhotosPicker from '@/components/creative/ReferencePhotosPicker';
import ConfirmCreateModal from '@/components/creative/ConfirmCreateModal';
import {
  isLocalAssetRef, readServerRef, readCacheTs, writeServerRef,
  clearCacheMeta, touchCacheTs, shouldOfferRestore,
} from '@/components/creative/crashCache';
import { apiGetDraft } from '@/components/creative/useNamedDrafts';
import StudioPanel, {
  type CopyDraftResult,
  type StudioPanelContext,
} from '@/components/studio/StudioPanel';
import SmartAspectSet, { type SmartAspectSlot } from '@/components/creative/SmartAspectSet';

// The full slot set for a Demand Gen campaign (Smart ASPECT Set — story 17.6).
const DG_FULL_SET_SLOTS: SmartAspectSlot[] = [
  { slot: 'landscape', label: 'Landscape (1.91:1)', aspect: 1.91 },
  { slot: 'square', label: 'Square (1:1)', aspect: 1 },
  { slot: 'portrait', label: 'Portrait (4:5)', aspect: 0.8 },
  { slot: 'tall_portrait', label: 'Tall portrait (9:16)', aspect: 0.5625 },
  { slot: 'logos', label: 'Logo (1:1)', aspect: 1 },
];
// Registry slot key → DG bundle field.
const DG_SLOT_FIELD: Record<string, keyof DGBundle> = {
  landscape: 'landscape', square: 'square', portrait: 'portrait',
  tall_portrait: 'tallPortrait', logos: 'logos',
};
import type { StudioJobStatus } from '@/lib/api';

const STEPS = [
  { id: 'brief',     label: 'Brief & budget'   },
  { id: 'targeting', label: 'Targeting'        },
  { id: 'text',      label: 'Text assets'      },
  { id: 'images',    label: 'Image assets'     },
  { id: 'channels',  label: 'Channels'         },
  { id: 'review',    label: 'Review & submit'  },
] as const;

// Demand Gen creative limits are FETCHED from the Creative Spec Registry via
// `useDemandGenRules()` (Epic 14, story 14.5) — no baked client constant (NFR-D1).
// Each component that validates reads `const rules = useDemandGenRules()`.

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
  // Epic 16 — angle + lock metadata parallel to the text rows (optional; absent
  // in pre-16 drafts, which still load). Angle chips + per-row rewrite + Diversify.
  headlineAngles: (string | null)[];
  headlineLocks: boolean[];
  descriptionAngles: (string | null)[];
  descriptionLocks: boolean[];
  dismissedDupPairs: [number, number][];
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
  headlines: [''], descriptions: [''],
  headlineAngles: [], headlineLocks: [], descriptionAngles: [], descriptionLocks: [],
  dismissedDupPairs: [],
  ctaText: '',
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
      // the server-side aspect crop on resubmit, so drop those. The predicate is
      // the shared, test-pinned `isLocalAssetRef` (story 15.4, behavior unchanged).
      parsed.logos = (parsed.logos || []).filter(isLocalAssetRef);
      parsed.landscape = (parsed.landscape || []).filter(isLocalAssetRef);
      parsed.square = (parsed.square || []).filter(isLocalAssetRef);
      parsed.portrait = (parsed.portrait || []).filter(isLocalAssetRef);
      parsed.tallPortrait = (parsed.tallPortrait || []).filter(isLocalAssetRef);
      // Reference photos are library ids too — keep only local refs so a leaked
      // Google resource name can't ride back in as a bogus reference.
      parsed.referenceAssetIds = (parsed.referenceAssetIds || []).filter(isLocalAssetRef);
      return parsed;
    } catch { return EMPTY_BUNDLE; }
  });
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string; campaignId?: string } | null>(null);
  const rules = useDemandGenRules();

  const [restore, setRestore] = useState<{ bundle: DGBundle; name: string; id: string; updatedAt: string } | null>(null);

  const setField = useCallback(<K extends keyof DGBundle>(key: K, value: DGBundle[K]) => {
    setBundle(prev => {
      const next = { ...prev, [key]: value };
      // Crash cache only (story 15.4): the server row is the source of truth;
      // this write-through just recovers unsaved edits after a crash. The `.ts`
      // sidecar lets the restore banner tell a stale cache from newer edits.
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
      touchCacheTs(STORAGE_KEY);
      return next;
    });
  }, []);

  // Replace the whole bundle when a named draft is loaded (story 15.2) / a JSON
  // template is imported (story 15.5). Writes through to the crash cache so a
  // refresh right after a load keeps the loaded content.
  const loadBundle = useCallback((next: DGBundle) => {
    const merged: DGBundle = { ...EMPTY_BUNDLE, ...next };
    merged.channels = { ...EMPTY_BUNDLE.channels, ...(next.channels || {}) };
    setBundle(merged);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(merged)); } catch {}
    touchCacheTs(STORAGE_KEY);
  }, []);

  // Restore banner (FR4.4): if the crash cache is NEWER than the named draft it
  // descends from AND differs, offer local-vs-server on open.
  useEffect(() => {
    if (!accountId) return;
    const ref = readServerRef(STORAGE_KEY);
    if (!ref) return;
    let cancelled = false;
    apiGetDraft<DGBundle>(accountId, ref.id)
      .then(row => {
        if (cancelled) return;
        const serverMerged: DGBundle = {
          ...EMPTY_BUNDLE, ...row.bundle,
          channels: { ...EMPTY_BUNDLE.channels, ...(row.bundle.channels || {}) },
        };
        const differs = JSON.stringify(bundle) !== JSON.stringify(serverMerged);
        if (shouldOfferRestore(readCacheTs(STORAGE_KEY), row.updated_at, differs)) {
          setRestore({ bundle: serverMerged, name: row.name, id: row.id, updatedAt: row.updated_at });
        }
      })
      .catch(() => { /* ref stale / draft deleted — no banner */ });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountId]);

  const stepId = STEPS[stepIdx].id;

  const stepHint = useMemo(() => {
    const missing: string[] = [];
    if (stepId === 'brief') {
      if (!bundle.name.trim()) missing.push('campaign name');
      if (!(parseFloat(bundle.dailyBudget) > 0)) missing.push('daily budget');
      if (!bundle.finalUrl.trim()) missing.push('final URL');
      if (!bundle.businessName.trim()) missing.push('business name');
      else if (bundle.businessName.length > rules.businessNameMaxChars) missing.push(`business name over ${rules.businessNameMaxChars} chars`);
      if (bundle.targetCpa.trim() && !(parseFloat(bundle.targetCpa) > 0)) missing.push('a valid target CPA (or leave it blank)');
    } else if (stepId === 'text') {
      const h = bundle.headlines.filter(s => s.trim());
      const d = bundle.descriptions.filter(s => s.trim());
      if (h.length < rules.headlines.min) missing.push(`${rules.headlines.min - h.length} more headline`);
      if (d.length < rules.descriptions.min) missing.push(`${rules.descriptions.min - d.length} more description`);
      if (h.some(s => s.length > rules.headlines.maxChars)) missing.push(`a headline is over ${rules.headlines.maxChars} chars`);
      if (d.some(s => s.length > rules.descriptions.maxChars)) missing.push(`a description is over ${rules.descriptions.maxChars} chars`);
    } else if (stepId === 'images') {
      if (bundle.logos.length < rules.logos.min) missing.push('a logo');
      if (bundle.landscape.length + bundle.square.length < 1) missing.push('a landscape or square marketing image');
    } else if (stepId === 'channels') {
      if (!Object.values(bundle.channels).some(Boolean)) missing.push('at least one channel ON');
    }
    return missing.length ? `To continue: ${missing.join(' · ')}` : null;
  }, [stepId, bundle, rules]);

  const stepValid = useMemo(() => {
    switch (stepId) {
      case 'brief': {
        const b = parseFloat(bundle.dailyBudget);
        const cpaOk = !bundle.targetCpa.trim() || parseFloat(bundle.targetCpa) > 0;
        return !!bundle.name.trim()
          && !!bundle.finalUrl.trim()
          && !!bundle.businessName.trim()
          && bundle.businessName.length <= rules.businessNameMaxChars
          && Number.isFinite(b) && b > 0
          && cpaOk;
      }
      case 'targeting':
        return true; // optional — Google defaults to all-geo / all-language
      case 'text': {
        const h = bundle.headlines.filter(s => s.trim());
        const d = bundle.descriptions.filter(s => s.trim());
        return h.length >= rules.headlines.min && h.length <= rules.headlines.max
          && d.length >= rules.descriptions.min && d.length <= rules.descriptions.max
          && h.every(s => s.length <= rules.headlines.maxChars)
          && d.every(s => s.length <= rules.descriptions.maxChars);
      }
      case 'images':
        return bundle.logos.length >= rules.logos.min
          && (bundle.landscape.length + bundle.square.length) >= 1;
      case 'channels':
        return Object.values(bundle.channels).some(Boolean);
      case 'review':
        return true;
    }
  }, [stepId, bundle, rules]);

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

      {/* Restore banner (story 15.4 / FR4.4) — local crash cache newer than the
          saved draft it descends from. Choosing server discards the local cache. */}
      {restore && (
        <div className="border border-amber-500/40 bg-amber-500/10 rounded-md p-3 mb-4 text-xs flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="text-foreground font-medium">Unsaved local edits recovered</p>
            <p className="text-muted-foreground">
              You have local changes newer than the saved draft “{restore.name}”. Keep your recovered
              edits, or load the saved version (discards local).
            </p>
          </div>
          <div className="flex flex-col gap-1.5 shrink-0">
            <Button size="sm" variant="outline" onClick={() => { clearCacheMeta(STORAGE_KEY); setRestore(null); }}>
              Keep my edits
            </Button>
            <Button size="sm" onClick={() => {
              loadBundle(restore.bundle);
              writeServerRef(STORAGE_KEY, { id: restore.id, updatedAt: restore.updatedAt, name: restore.name });
              setRestore(null);
            }}>
              Load saved
            </Button>
          </div>
        </div>
      )}

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
        {stepId === 'review'    && (
          <div className="space-y-4">
            <DraftManager<DGBundle> accountId={accountId} campaignType="demand_gen" bundle={bundle} onLoad={loadBundle} storageKey={STORAGE_KEY} />
            <StepReview bundle={bundle} submitResult={submitResult} submitting={submitting} />
          </div>
        )}
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
          <Button onClick={() => setConfirmOpen(true)} disabled={submitting || !rules.ready} className="gap-1.5">
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {submitting ? 'Creating...' : 'Create campaign'}
          </Button>
        )}
      </div>

      {/* Confirm-before-create modal (shared component, story 16.5) */}
      <ConfirmCreateModal
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={doSubmit}
        campaignType="Demand Gen"
        campaignName={bundle.name}
        dailyBudget={bundle.dailyBudget}
        icon={<Megaphone className="h-4 w-4 text-primary" />}
      />
    </div>
  );
}

// ── Step components ─────────────────────────────────────────────────

type SetField = <K extends keyof DGBundle>(k: K, v: DGBundle[K]) => void;

function StepBrief({ bundle, setField, accountId }: { bundle: DGBundle; setField: SetField; accountId: string }) {
  const rules = useDemandGenRules();
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

      {/* Shared assist components (story 16.5) — consumed by BOTH wizards. */}
      <BusinessNameField
        value={bundle.businessName}
        onChange={v => setField('businessName', v)}
        max={rules.businessNameMaxChars}
      />

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

      <BrandPresetToggle checked={bundle.corporateBrand} onChange={v => setField('corporateBrand', v)} />

      <ReferencePhotosPicker
        accountId={accountId}
        value={bundle.referenceAssetIds}
        onChange={ids => setField('referenceAssetIds', ids)}
      />

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
  const rules = useDemandGenRules();
  const angleOptions = useAngles();
  const { specs } = useCreativeSpecs();
  const threshold = specs?.engine?.near_dup_threshold;
  const [panelOpen, setPanelOpen] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [rewritingHl, setRewritingHl] = useState<number | null>(null);
  const [rewritingDesc, setRewritingDesc] = useState<number | null>(null);
  const [diversifying, setDiversifying] = useState(false);

  // Apply distributed rows into the field text + parallel angle arrays (locks
  // reset — a fresh draft has no locks). business_name too (Brief step field).
  const applyRows = useCallback((rows: CopyRow[], businessName?: string) => {
    const d = distributeRows(rows);
    if (businessName) setField('businessName', businessName.slice(0, rules.businessNameMaxChars));
    setField('headlines', d.headlines.length ? d.headlines : ['']);
    setField('headlineAngles', d.headlineAngles);
    setField('headlineLocks', d.headlines.map(() => false));
    setField('descriptions', d.descriptions.length ? d.descriptions : ['']);
    setField('descriptionAngles', d.descriptionAngles);
    setField('descriptionLocks', d.descriptions.map(() => false));
    setField('dismissedDupPairs', []);
  }, [setField, rules.businessNameMaxChars]);

  const applyHeadlineRows = useCallback((rows: CopyRow[]) => {
    setField('headlines', rows.map(r => r.text));
    setField('headlineAngles', rows.map(r => r.angle ?? null));
    setField('headlineLocks', rows.map(r => !!r.locked));
  }, [setField]);
  const applyDescriptionRows = useCallback((rows: CopyRow[]) => {
    setField('descriptions', rows.map(r => r.text));
    setField('descriptionAngles', rows.map(r => r.angle ?? null));
    setField('descriptionLocks', rows.map(r => !!r.locked));
  }, [setField]);

  // One copy-job hook per operation, each with its own resume key so a page
  // refresh mid-job resumes and applies (FR1.9).
  const draftJob = useDraftJob(accountId, 'demandgen-copy-draft-id',
    (r: CopyJobResult) => applyRows(r.rows, r.business_name));
  const hlRewriteJob = useDraftJob(accountId, 'demandgen-hl-rewrite-id',
    (r: CopyJobResult) => applyHeadlineRows(r.rows));
  const descRewriteJob = useDraftJob(accountId, 'demandgen-desc-rewrite-id',
    (r: CopyJobResult) => applyDescriptionRows(r.rows));
  const diversifyJob = useDraftJob(accountId, 'demandgen-diversify-id',
    (r: CopyJobResult) => applyHeadlineRows(r.rows));

  // StudioPanel copy preview shows the legacy field lists; onUseCopy distributes
  // the angle-tagged rows into the workbench.
  const applyDraft = useCallback((result: CopyDraftResult) => {
    if (result.rows?.length) applyRows(result.rows as CopyRow[], result.business_name);
    else {
      if (result.business_name) setField('businessName', result.business_name.slice(0, rules.businessNameMaxChars));
      if (result.headlines?.length) setField('headlines', result.headlines);
      if (result.descriptions?.length) setField('descriptions', result.descriptions);
    }
  }, [applyRows, setField, rules.businessNameMaxChars]);

  const draftForPanel = useCallback(async (intent: string): Promise<CopyDraftResult> => {
    const brief = intent.trim()
      ? `${bundle.brief}\n\nOperator emphasis for this draft: ${intent.trim()}`.trim()
      : bundle.brief;
    const r = await draftJob.start({
      campaign_type: 'demand_gen', mode: 'draft', brief,
      final_url: bundle.finalUrl, business_name: bundle.businessName, campaign_name: bundle.name,
    });
    const d = distributeRows(r.rows || []);
    return { business_name: r.business_name, headlines: d.headlines, descriptions: d.descriptions, rows: r.rows };
  }, [draftJob, bundle.brief, bundle.finalUrl, bundle.businessName, bundle.name]);

  const rewriteRow = useCallback(async (
    field: 'headline' | 'description', index: number, targetAngle: string,
  ) => {
    const isHl = field === 'headline';
    const rows = toRows(
      isHl ? bundle.headlines : bundle.descriptions,
      isHl ? bundle.headlineAngles : bundle.descriptionAngles,
      isHl ? 'headline' : 'description',
      isHl ? bundle.headlineLocks : bundle.descriptionLocks,
    );
    (isHl ? setRewritingHl : setRewritingDesc)(index);
    setLocalError(null);
    try {
      const job = isHl ? hlRewriteJob : descRewriteJob;
      const r = await job.start({
        campaign_type: 'demand_gen', mode: 'rewrite_row', rows, row_index: index,
        target_angle: targetAngle, brief: bundle.brief, final_url: bundle.finalUrl,
        business_name: bundle.businessName,
      });
      (isHl ? applyHeadlineRows : applyDescriptionRows)(r.rows);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : String(e));
    } finally {
      (isHl ? setRewritingHl : setRewritingDesc)(null);
    }
  }, [bundle, hlRewriteJob, descRewriteJob, applyHeadlineRows, applyDescriptionRows]);

  const dupCount = threshold == null ? 0
    : new Set(findNearDupPairs(bundle.headlines.filter(s => s.trim()), { threshold }).flat()).size;

  const diversify = useCallback(async () => {
    if (threshold == null) return;
    const rows = toRows(bundle.headlines, bundle.headlineAngles, 'headline', bundle.headlineLocks);
    const flagged = new Set(findNearDupPairs(bundle.headlines, { threshold }).flat());
    const body = buildDiversifyBody(rows, flagged, bundle.dismissedDupPairs);
    setDiversifying(true);
    setLocalError(null);
    try {
      const r = await diversifyJob.start({
        campaign_type: 'demand_gen', mode: 'diversify', ...body,
        brief: bundle.brief, final_url: bundle.finalUrl, business_name: bundle.businessName,
      });
      applyHeadlineRows(r.rows);
      if (r.dismissed_dup_pairs) setField('dismissedDupPairs', r.dismissed_dup_pairs);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : String(e));
    } finally {
      setDiversifying(false);
    }
  }, [threshold, bundle, diversifyJob, applyHeadlineRows, setField]);

  const resuming = draftJob.resuming;
  const draftError = draftJob.error || localError;

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
              Every drafted row wears its <b>angle</b>; you preview before it replaces what's below.
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

      <PolicyHintCard />

      <CoveragePanel
        headlines={bundle.headlines}
        headlineAngles={bundle.headlineAngles}
        headlinesMax={rules.headlines.max}
        descriptions={bundle.descriptions}
        descriptionsMax={rules.descriptions.max}
        totalImageCap={Number.isFinite(rules.imageMax) ? rules.imageMax : null}
        imageSlots={[
          { slot: 'landscape', label: 'Landscape', count: bundle.landscape.length },
          { slot: 'square', label: 'Square', count: bundle.square.length },
          { slot: 'portrait', label: 'Portrait', count: bundle.portrait.length },
          { slot: 'tall_portrait', label: 'Tall', count: bundle.tallPortrait.length },
          { slot: 'logos', label: 'Logo', count: bundle.logos.length },
        ]}
      />

      {/* Rationale surface (FR5.2). Demand Gen has no search-theme array, so no
          one-click theme target — the research grounds the copy + brand assets. */}
      <BrandKitPanel accountId={accountId} finalUrl={bundle.finalUrl} />

      <div className="flex items-center justify-between">
        <label className="text-xs font-medium">Headlines</label>
        <Button
          size="sm" variant="outline" onClick={diversify}
          disabled={diversifying || threshold == null || dupCount === 0}
          className="gap-1.5 h-7"
          title="Regenerate near-duplicate headlines toward missing angles (locked rows are kept)"
        >
          {diversifying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          {diversifying ? 'Diversifying…' : dupCount ? `Diversify (${dupCount} near-dup)` : 'Diversify'}
        </Button>
      </div>
      <TextWorkbench
        label="Headlines"
        hint={`≥${rules.headlines.min}, each ≤${rules.headlines.maxChars} chars · up to ${rules.headlines.max}`}
        items={bundle.headlines}
        onChange={v => setField('headlines', v)}
        maxChars={rules.headlines.maxChars}
        minItems={rules.headlines.min}
        maxItems={rules.headlines.max}
        angles={bundle.headlineAngles}
        locked={bundle.headlineLocks}
        onMetaChange={(a, l) => { setField('headlineAngles', a); setField('headlineLocks', l); }}
        onRewriteRow={(i, a) => rewriteRow('headline', i, a)}
        rewritingRow={rewritingHl}
        angleOptions={angleOptions}
      />
      <TextWorkbench
        label="Descriptions"
        hint={`≥${rules.descriptions.min}, each ≤${rules.descriptions.maxChars} chars · up to ${rules.descriptions.max}`}
        items={bundle.descriptions}
        onChange={v => setField('descriptions', v)}
        maxChars={rules.descriptions.maxChars}
        minItems={rules.descriptions.min}
        maxItems={rules.descriptions.max}
        angles={bundle.descriptionAngles}
        locked={bundle.descriptionLocks}
        onMetaChange={(a, l) => { setField('descriptionAngles', a); setField('descriptionLocks', l); }}
        onRewriteRow={(i, a) => rewriteRow('description', i, a)}
        rewritingRow={rewritingDesc}
        angleOptions={angleOptions}
      />
      <div>
        <label className="text-xs font-medium mb-1.5 block">Call to action (optional)</label>
        <Input value={bundle.ctaText} onChange={e => setField('ctaText', e.target.value)} placeholder="e.g. Learn more, Get started, Apply now" />
        <p className="text-[10px] text-muted-foreground mt-1">Leave blank to let Google auto-select the CTA label.</p>
      </div>
    </div>
  );
}

// PolicyHint was extracted to the shared creative/PolicyHintCard (story 16.5) —
// both wizards import it now.

// ── Image assets ────────────────────────────────────────────────────

interface SlotAssetMeta { url: string; filename: string }

function StepImages({ bundle, setField, accountId }: { bundle: DGBundle; setField: SetField; accountId: string }) {
  const rules = useDemandGenRules();
  const [fullSetOpen, setFullSetOpen] = useState(false);
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

  const handleFullSetAssign = useCallback((slot: string, id: string, url?: string | null) => {
    const field = DG_SLOT_FIELD[slot];
    if (!field) return;
    if (url) registerAsset(id, { url, filename: id });
    const cur = (bundle[field] as string[]) || [];
    if (!cur.includes(id)) setField(field, [...cur, id] as DGBundle[typeof field]);
  }, [bundle, setField, registerAsset]);

  return (
    <div className="space-y-5">
      <div className="border border-border bg-secondary/20 rounded-md p-3 text-[11px] leading-relaxed text-muted-foreground">
        <b className="text-foreground">Generate</b> on-brand images per slot (the aspect is locked to the slot), pick from the
        {' '}Studio asset library, or upload files. Generated images anchor to your reference photos from step 1 and land in the
        {' '}library. Each slot shows the image exactly as Google will receive it — mismatched aspects get center-cropped at submit and are flagged.
      </div>
      {/* Smart ASPECT Set — one art direction → the whole slot set in one queued
          action (story 17.6). */}
      <button
        type="button"
        onClick={() => setFullSetOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-primary/50 bg-primary/5 px-4 py-2 text-xs font-medium text-primary hover:bg-primary/10"
      >
        <Sparkles className="h-4 w-4" />
        Generate the full set (all slots in one action)
      </button>
      <SmartAspectSet
        open={fullSetOpen}
        onClose={() => setFullSetOpen(false)}
        accountId={accountId}
        campaignType="demand_gen"
        artDirection={bundle.brief}
        slots={DG_FULL_SET_SLOTS}
        referenceAssetIds={bundle.referenceAssetIds.length ? bundle.referenceAssetIds : undefined}
        logoAssetId={bundle.logos[0]}
        onAssign={handleFullSetAssign}
      />
      <ImageGroup
        label="Logos" spec="Auto-cropped to 1:1 · min 128×128 · transparent bg preferred"
        targetRatio={1} targetLabel="1:1" slotAspect="1:1"
        items={bundle.logos} onChange={v => setField('logos', v)}
        accountId={accountId} minItems={rules.logos.min} maxItems={rules.logos.max}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <ImageGroup
        label="Landscape marketing image (1.91:1)" spec="Any aspect works — cropped to 1.91:1 · min 600×314 · 1200×628 recommended"
        targetRatio={1.91} targetLabel="1.91:1" slotAspect="16:9"
        items={bundle.landscape} onChange={v => setField('landscape', v)}
        accountId={accountId} minItems={0} maxItems={rules.imageMax}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <ImageGroup
        label="Square marketing image (1:1)" spec="Any aspect works — cropped to 1:1 · min 300×300 · 1200×1200 recommended"
        targetRatio={1} targetLabel="1:1" slotAspect="1:1"
        items={bundle.square} onChange={v => setField('square', v)}
        accountId={accountId} minItems={0} maxItems={rules.imageMax}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <p className="text-[10px] text-muted-foreground -mt-2">Provide at least one landscape or square marketing image. Portrait &amp; tall are optional extras.</p>
      <ImageGroup
        label="Portrait marketing image (4:5)" spec="Optional · cropped to 4:5 · min 480×600 · 960×1200 recommended"
        targetRatio={0.8} targetLabel="4:5" slotAspect="4:5"
        items={bundle.portrait} onChange={v => setField('portrait', v)}
        accountId={accountId} minItems={0} maxItems={rules.imageMax}
        assetMeta={assetMeta} onAssetKnown={registerAsset} promptContext={baseContext}
      />
      <ImageGroup
        label="Tall portrait image (9:16)" spec="Optional · cropped to 9:16 · for YouTube Shorts placements"
        targetRatio={0.5625} targetLabel="9:16" slotAspect="9:16"
        items={bundle.tallPortrait} onChange={v => setField('tallPortrait', v)}
        accountId={accountId} minItems={0} maxItems={rules.imageMax}
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
// TextList was extracted to the shared creative/TextWorkbench (story 15.6) —
// both wizards now import it (paste-split + near-dup badge live there).

function ImageGroup({
  label, spec, targetRatio, targetLabel, slotAspect,
  items, onChange, accountId, minItems, maxItems,
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
