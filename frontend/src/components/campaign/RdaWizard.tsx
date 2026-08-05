/**
 * RdaWizard — Responsive Display Ad creation flow (P5, FR6.3).
 *
 * THE ACCEPTANCE TEST OF THE CORE. This shell defines NO creative logic: every
 * limit arrives from the registry via useRdaRules(); the text bench, coverage,
 * image generation, brand kit, drafts and confirm modal are all IMPORTED shared
 * components (Epics 15–18). Building the whole Display builder required ZERO
 * changes to any core component (creative_images.py / components/creative/*) —
 * the proof the core is real (shell-gate: < 647 lines, import-only). It POSTs the
 * SAME RdaOrchestrator the chat agent / MCP tool drives.
 * Steps: brief & budget → text (short headlines · the SINGLE long headline ·
 * descriptions) → images (Smart ASPECT Set marketing images + real logos) →
 * review & submit (created PAUSED).
 */

import { useState, useCallback, useMemo } from 'react';
import {
  ArrowLeft, ArrowRight, Images, CheckCircle2, Circle, Sparkles, Loader2,
  AlertCircle, DollarSign, ImageIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRdaRules } from '@/lib/creativeSpecs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import DraftManager from '@/components/creative/DraftManager';
import TextWorkbench from '@/components/creative/TextWorkbench';
import { useDraftJob, type CopyJobResult } from '@/components/creative/useDraftJob';
import { useAngles } from '@/lib/angles';
import { distributeRows } from '@/lib/copyRows';
import CoveragePanel from '@/components/creative/CoveragePanel';
import BrandKitPanel from '@/components/creative/BrandKitPanel';
import PolicyHintCard from '@/components/creative/PolicyHintCard';
import BusinessNameField from '@/components/creative/BusinessNameField';
import ReferencePhotosPicker from '@/components/creative/ReferencePhotosPicker';
import ConfirmCreateModal from '@/components/creative/ConfirmCreateModal';
import { isLocalAssetRef, touchCacheTs } from '@/components/creative/crashCache';
import SmartAspectSet, {
  type SmartAspectSlot, type SmartAspectSetProps,
} from '@/components/creative/SmartAspectSet';
import TargetingFields from '@/components/campaign/TargetingFields';

// The RDA marketing-image slot set for the Smart ASPECT Set (logos are the
// operator's real uploads, not generated — see the image step).
const RDA_MARKETING_SLOTS: SmartAspectSlot[] = [
  { slot: 'landscape', label: 'Landscape (1.91:1)', aspect: 1.91 },
  { slot: 'square', label: 'Square (1:1)', aspect: 1 },
];
// Registry slot key → RDA bundle field (Smart ASPECT Set onAssign target).
const RDA_SLOT_FIELD: Record<string, keyof RdaBundle> = {
  landscape: 'landscape', square: 'square',
};

// SmartAspectSet's campaignType prop is typed 'pmax' | 'demand_gen'; the backend
// batch renderer reads the on-image/logo policy from the registry by name and
// accepts 'rda' (creative_specs.get('rda')). Passing the true type keeps the RDA
// policy (logo_overlay=forbid) correct WITHOUT modifying the shared component (a
// widened union there would be a forbidden core change) — composition, not edit.
const RDA_CAMPAIGN_TYPE = 'rda' as SmartAspectSetProps['campaignType'];

const STEPS = [
  { id: 'brief',  label: 'Brief & budget'  },
  { id: 'text',   label: 'Text assets'     },
  { id: 'images', label: 'Image assets'    },
  { id: 'review', label: 'Review & submit' },
] as const;

interface RdaBundle {
  name: string;
  dailyBudget: string;         // dollars; → micros on submit
  finalUrl: string;
  businessName: string;
  brief: string;
  referenceAssetIds: string[]; // operator photos anchoring generation (local ids)
  targetCpa: string;           // optional dollars; blank = pure Maximize Conversions
  locationIds: string;
  excludedLocationIds: string;
  languageIds: string;
  headlines: string[];
  headlineAngles: (string | null)[];
  longHeadlines: string[];     // exactly one
  longHeadlineAngles: (string | null)[];
  descriptions: string[];
  descriptionAngles: (string | null)[];
  ctaText: string;
  logos: string[];             // 1:1 logo (real, required)
  landscapeLogos: string[];    // 4:1 landscape logo (real, optional)
  landscape: string[];         // 1.91:1 marketing (generated)
  square: string[];            // 1:1 marketing (generated)
}

const EMPTY_BUNDLE: RdaBundle = {
  name: '', dailyBudget: '', finalUrl: '', businessName: '', brief: '',
  referenceAssetIds: [],
  targetCpa: '', locationIds: '', excludedLocationIds: '', languageIds: '1000',  // default: English
  headlines: [''], headlineAngles: [],
  longHeadlines: [''], longHeadlineAngles: [],
  descriptions: [''], descriptionAngles: [],
  ctaText: '',
  logos: [], landscapeLogos: [], landscape: [], square: [],
};

const STORAGE_KEY = 'rda-wizard-bundle';

interface RdaWizardProps {
  onClose: () => void;
  onBackToTypePicker: () => void;
}

export default function RdaWizard({ onClose, onBackToTypePicker }: RdaWizardProps) {
  const accountId = useClientAccountId();
  const [stepIdx, setStepIdx] = useState(0);
  const [bundle, setBundle] = useState<RdaBundle>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return EMPTY_BUNDLE;
      const parsed: RdaBundle = { ...EMPTY_BUNDLE, ...JSON.parse(saved) };
      // Only LOCAL asset ids survive a reload — a Google resource name leaking
      // back in would bypass the server-side aspect crop on resubmit.
      parsed.logos = (parsed.logos || []).filter(isLocalAssetRef);
      parsed.landscapeLogos = (parsed.landscapeLogos || []).filter(isLocalAssetRef);
      parsed.landscape = (parsed.landscape || []).filter(isLocalAssetRef);
      parsed.square = (parsed.square || []).filter(isLocalAssetRef);
      parsed.referenceAssetIds = (parsed.referenceAssetIds || []).filter(isLocalAssetRef);
      return parsed;
    } catch { return EMPTY_BUNDLE; }
  });
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok: boolean; message: string; campaignId?: string } | null>(null);
  const rules = useRdaRules();

  const setField = useCallback(<K extends keyof RdaBundle>(key: K, value: RdaBundle[K]) => {
    setBundle(prev => {
      const next = { ...prev, [key]: value };
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); } catch {}
      touchCacheTs(STORAGE_KEY);
      return next;
    });
  }, []);

  const loadBundle = useCallback((next: RdaBundle) => {
    const merged: RdaBundle = { ...EMPTY_BUNDLE, ...next };
    setBundle(merged);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(merged)); } catch {}
    touchCacheTs(STORAGE_KEY);
  }, []);

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
      const lh = bundle.longHeadlines.filter(s => s.trim());
      const d = bundle.descriptions.filter(s => s.trim());
      if (h.length < rules.headlines.min) missing.push(`${rules.headlines.min - h.length} more headline`);
      if (lh.length < rules.longHeadlines.min) missing.push('the long headline');
      if (lh.length > rules.longHeadlines.max) missing.push('only one long headline is allowed');
      if (d.length < rules.descriptions.min) missing.push(`${rules.descriptions.min - d.length} more description`);
      if (h.some(s => s.length > rules.headlines.maxChars)) missing.push(`a headline is over ${rules.headlines.maxChars} chars`);
      if (lh.some(s => s.length > rules.longHeadlines.maxChars)) missing.push(`the long headline is over ${rules.longHeadlines.maxChars} chars`);
      if (d.some(s => s.length > rules.descriptions.maxChars)) missing.push(`a description is over ${rules.descriptions.maxChars} chars`);
    } else if (stepId === 'images') {
      if (bundle.logos.length < rules.logos.min) missing.push('a logo');
      if (bundle.landscape.length < rules.landscape.min) missing.push('a landscape marketing image');
      if (bundle.square.length < rules.square.min) missing.push('a square marketing image');
    }
    return missing.length ? `To continue: ${missing.join(' · ')}` : null;
  }, [stepId, bundle, rules]);

  const stepValid = useMemo(() => {
    switch (stepId) {
      case 'brief': {
        const b = parseFloat(bundle.dailyBudget);
        const cpaOk = !bundle.targetCpa.trim() || parseFloat(bundle.targetCpa) > 0;
        return !!bundle.name.trim() && !!bundle.finalUrl.trim()
          && !!bundle.businessName.trim()
          && bundle.businessName.length <= rules.businessNameMaxChars
          && Number.isFinite(b) && b > 0 && cpaOk;
      }
      case 'text': {
        const h = bundle.headlines.filter(s => s.trim());
        const lh = bundle.longHeadlines.filter(s => s.trim());
        const d = bundle.descriptions.filter(s => s.trim());
        return h.length >= rules.headlines.min && h.length <= rules.headlines.max
          && lh.length >= rules.longHeadlines.min && lh.length <= rules.longHeadlines.max
          && d.length >= rules.descriptions.min && d.length <= rules.descriptions.max
          && h.every(s => s.length <= rules.headlines.maxChars)
          && lh.every(s => s.length <= rules.longHeadlines.maxChars)
          && d.every(s => s.length <= rules.descriptions.maxChars);
      }
      case 'images':
        return bundle.logos.length >= rules.logos.min
          && bundle.landscape.length >= rules.landscape.min
          && bundle.square.length >= rules.square.min;
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
        ? Math.round(parseFloat(bundle.targetCpa) * 1_000_000) : null;
      const res = await fetch(`/api/accounts/${accountId}/campaigns/rda`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: bundle.name,
          budget_micros,
          final_urls: [bundle.finalUrl],
          business_name: bundle.businessName,
          headlines: bundle.headlines.map(s => s.trim()).filter(Boolean),
          long_headlines: bundle.longHeadlines.map(s => s.trim()).filter(Boolean),
          descriptions: bundle.descriptions.map(s => s.trim()).filter(Boolean),
          call_to_action_text: bundle.ctaText.trim() || null,
          logos: bundle.logos,
          landscape_logos: bundle.landscapeLogos,
          marketing_images: { landscape: bundle.landscape, square: bundle.square },
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
          <h1 className="text-2xl font-bold flex items-center gap-2"><Images className="h-6 w-6 text-primary" /> Responsive Display</h1>
          <p className="text-sm text-muted-foreground">Auto-fitting image &amp; text ads across the Google Display Network — assets included.</p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-1 mb-6 text-[10px]">
        {STEPS.map((s, i) => (
          <div key={s.id} className="flex items-center flex-1">
            <div className={cn(
              'flex items-center gap-1.5 px-2 py-1 rounded-md',
              i === stepIdx && 'bg-primary text-primary-foreground font-medium',
              i !== stepIdx && 'text-muted-foreground',
            )}>
              {i < stepIdx ? <CheckCircle2 className="h-3 w-3" /> : <Circle className="h-3 w-3" />}
              <span className="whitespace-nowrap">{s.label}</span>
            </div>
            {i < STEPS.length - 1 && <div className="h-px flex-1 bg-border mx-1" />}
          </div>
        ))}
      </div>

      <div className="border border-border rounded-lg p-6 bg-card mb-4">
        {stepId === 'brief'  && <StepBrief  bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'text'   && <StepText   bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'images' && <StepImages bundle={bundle} setField={setField} accountId={accountId} />}
        {stepId === 'review' && (
          <div className="space-y-4">
            <DraftManager<RdaBundle> accountId={accountId} campaignType="rda" bundle={bundle} onLoad={loadBundle} storageKey={STORAGE_KEY} />
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

      <ConfirmCreateModal
        open={confirmOpen}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={doSubmit}
        campaignType="Responsive Display"
        campaignName={bundle.name}
        dailyBudget={bundle.dailyBudget}
        icon={<Images className="h-4 w-4 text-primary" />}
      />
    </div>
  );
}

// ── Step components ─────────────────────────────────────────────────

type SetField = <K extends keyof RdaBundle>(k: K, v: RdaBundle[K]) => void;

function StepBrief({ bundle, setField, accountId }: { bundle: RdaBundle; setField: SetField; accountId: string }) {
  const rules = useRdaRules();
  return (
    <div className="space-y-4">
      <div>
        <label className="text-xs font-medium mb-1.5 block">Campaign name *</label>
        <Input value={bundle.name} onChange={e => setField('name', e.target.value)} placeholder="e.g. Panama QIV — Display — Aug 2026" />
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

      <BusinessNameField value={bundle.businessName} onChange={v => setField('businessName', v)} max={rules.businessNameMaxChars} />

      <div>
        <label className="text-xs font-medium mb-1.5 block">Campaign brief (optional)</label>
        <textarea
          value={bundle.brief}
          onChange={e => setField('brief', e.target.value)}
          rows={3}
          placeholder="Who is this for, what's the offer, what makes it different? The Creative Director uses this (plus your landing page) to draft copy in the Text step — and to generate on-brand images in the Assets step."
          className="w-full text-sm rounded-md border border-border bg-background p-2.5 resize-none placeholder:text-muted-foreground/60"
        />
      </div>

      <ReferencePhotosPicker accountId={accountId} value={bundle.referenceAssetIds} onChange={ids => setField('referenceAssetIds', ids)} />

      <div className="border border-border rounded-md p-3 bg-secondary/20">
        <div className="flex items-center gap-2 mb-1.5">
          <DollarSign className="h-3.5 w-3.5 text-primary" />
          <span className="text-xs font-semibold">Bidding — Maximize Conversions</span>
        </div>
        <p className="text-[10px] text-muted-foreground mb-2">
          Display bids to get the most conversions for your budget. Add an optional target CPA to steer toward a cost-per-conversion.
        </p>
        <label className="text-xs font-medium mb-1.5 block">Target CPA (USD, optional)</label>
        <Input type="number" step="0.01" min="0.01" value={bundle.targetCpa} onChange={e => setField('targetCpa', e.target.value)} placeholder="Leave blank for pure Maximize Conversions" />
      </div>

      <div className="border border-border rounded-md p-3 bg-secondary/20">
        <TargetingFields
          locationIds={bundle.locationIds}
          excludedLocationIds={bundle.excludedLocationIds}
          languageIds={bundle.languageIds}
          onChange={setField}
        />
      </div>
    </div>
  );
}

function StepText({ bundle, setField, accountId }: { bundle: RdaBundle; setField: SetField; accountId: string }) {
  const rules = useRdaRules();
  const angleOptions = useAngles();
  const [localError, setLocalError] = useState<string | null>(null);

  // Apply a drafted, angle-tagged result into the three text benches. RDA's
  // long headline is the SINGLE long_headline row.
  const applyResult = useCallback((r: CopyJobResult) => {
    const d = distributeRows(r.rows || []);
    if (r.business_name) setField('businessName', r.business_name.slice(0, rules.businessNameMaxChars));
    setField('headlines', d.headlines.length ? d.headlines : ['']);
    setField('headlineAngles', d.headlineAngles);
    setField('longHeadlines', d.longHeadlines.length ? d.longHeadlines : ['']);
    setField('longHeadlineAngles', d.longHeadlineAngles);
    setField('descriptions', d.descriptions.length ? d.descriptions : ['']);
    setField('descriptionAngles', d.descriptionAngles);
  }, [setField, rules.businessNameMaxChars]);

  const draftJob = useDraftJob(accountId, 'rda-copy-draft-id', applyResult);

  const draft = useCallback(async () => {
    setLocalError(null);
    try {
      const r = await draftJob.start({
        campaign_type: 'rda', mode: 'draft', brief: bundle.brief,
        final_url: bundle.finalUrl, business_name: bundle.businessName, campaign_name: bundle.name,
      });
      applyResult(r);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : String(e));
    }
  }, [draftJob, bundle.brief, bundle.finalUrl, bundle.businessName, bundle.name, applyResult]);

  const drafting = draftJob.status === 'running' || draftJob.resuming;
  const draftError = draftJob.error || localError;

  return (
    <div className="space-y-5">
      <div className="border border-border bg-secondary/20 rounded-md p-3 text-xs">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-primary mt-0.5 shrink-0" />
            <p className="text-muted-foreground leading-relaxed">
              Let the <b>Creative Director</b> draft the business name, headlines and descriptions from your
              brief and landing page ({bundle.finalUrl || 'set the Final URL in step 1'}). Each row wears its <b>angle</b>.
            </p>
          </div>
          <Button size="sm" onClick={draft} disabled={drafting || !bundle.finalUrl} className="gap-1.5 shrink-0">
            {drafting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {drafting ? 'Drafting…' : 'Draft with Creative Director'}
          </Button>
        </div>
        {draftError && (
          <p className="mt-2 flex items-center gap-1.5 text-red-500">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" /> {draftError}
          </p>
        )}
      </div>

      <PolicyHintCard />

      <CoveragePanel
        headlines={bundle.headlines} headlineAngles={bundle.headlineAngles}
        headlinesMax={rules.headlines.max}
        descriptions={bundle.descriptions} descriptionsMax={rules.descriptions.max}
        totalImageCap={Number.isFinite(rules.imageMax) ? rules.imageMax : null}
        imageSlots={[
          { slot: 'landscape', label: 'Landscape', count: bundle.landscape.length },
          { slot: 'square', label: 'Square', count: bundle.square.length },
          { slot: 'logos', label: 'Logo', count: bundle.logos.length },
        ]}
      />

      <BrandKitPanel accountId={accountId} finalUrl={bundle.finalUrl} />

      <TextWorkbench
        label="Short headlines"
        hint={`≥${rules.headlines.min}, each ≤${rules.headlines.maxChars} chars · up to ${rules.headlines.max}`}
        items={bundle.headlines} onChange={v => setField('headlines', v)}
        maxChars={rules.headlines.maxChars} minItems={rules.headlines.min} maxItems={rules.headlines.max}
        angles={bundle.headlineAngles} onMetaChange={a => setField('headlineAngles', a)} angleOptions={angleOptions}
      />
      <TextWorkbench
        label="Long headline (exactly one)"
        hint={`exactly 1 · ≤${rules.longHeadlines.maxChars} chars`}
        items={bundle.longHeadlines} onChange={v => setField('longHeadlines', v)}
        maxChars={rules.longHeadlines.maxChars} minItems={rules.longHeadlines.min} maxItems={rules.longHeadlines.max}
        angles={bundle.longHeadlineAngles} onMetaChange={a => setField('longHeadlineAngles', a)} angleOptions={angleOptions}
      />
      <TextWorkbench
        label="Descriptions"
        hint={`≥${rules.descriptions.min}, each ≤${rules.descriptions.maxChars} chars · up to ${rules.descriptions.max}`}
        items={bundle.descriptions} onChange={v => setField('descriptions', v)}
        maxChars={rules.descriptions.maxChars} minItems={rules.descriptions.min} maxItems={rules.descriptions.max}
        angles={bundle.descriptionAngles} onMetaChange={a => setField('descriptionAngles', a)} angleOptions={angleOptions}
      />
      <div>
        <label className="text-xs font-medium mb-1.5 block">Call to action (optional)</label>
        <Input value={bundle.ctaText} onChange={e => setField('ctaText', e.target.value)} placeholder="e.g. Learn more, Get started, Apply now" />
        <p className="text-[10px] text-muted-foreground mt-1">Leave blank to let Google auto-select the CTA label.</p>
      </div>
    </div>
  );
}

function StepImages({ bundle, setField, accountId }: { bundle: RdaBundle; setField: SetField; accountId: string }) {
  const rules = useRdaRules();
  const [fullSetOpen, setFullSetOpen] = useState(false);

  // Smart ASPECT Set assigns each finished marketing tile to its slot.
  const handleAssign = useCallback((slot: string, id: string) => {
    const field = RDA_SLOT_FIELD[slot];
    if (!field) return;
    const cur = (bundle[field] as string[]) || [];
    if (!cur.includes(id)) setField(field, [...cur, id] as RdaBundle[typeof field]);
  }, [bundle, setField]);

  return (
    <div className="space-y-5">
      <div className="border border-border bg-secondary/20 rounded-md p-3 text-[11px] leading-relaxed text-muted-foreground">
        <b className="text-foreground">Generate</b> the marketing images with the Smart ASPECT Set (aspect locked per slot), then attach your <b>real logo(s)</b> below — logos are never AI-generated.
      </div>

      <button
        type="button"
        onClick={() => setFullSetOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-md border border-dashed border-primary/50 bg-primary/5 px-4 py-2 text-xs font-medium text-primary hover:bg-primary/10"
      >
        <Sparkles className="h-4 w-4" />
        Generate the marketing images (landscape + square)
      </button>
      <SmartAspectSet
        open={fullSetOpen}
        onClose={() => setFullSetOpen(false)}
        accountId={accountId}
        campaignType={RDA_CAMPAIGN_TYPE}
        artDirection={bundle.brief}
        slots={RDA_MARKETING_SLOTS}
        referenceAssetIds={bundle.referenceAssetIds.length ? bundle.referenceAssetIds : undefined}
        logoAssetId={bundle.logos[0]}
        onAssign={handleAssign}
      />

      <SlotSummary label="Landscape marketing (1.91:1)" count={bundle.landscape.length} required={rules.landscape.min > 0} />
      <SlotSummary label="Square marketing (1:1)" count={bundle.square.length} required={rules.square.min > 0} />

      <div>
        <label className="text-xs font-medium mb-1.5 flex items-center gap-1.5"><ImageIcon className="h-3.5 w-3.5" /> Logo — 1:1 (required) · attached logos are cropped to 1:1 at submit</label>
        <ReferencePhotosPicker accountId={accountId} value={bundle.logos} onChange={ids => setField('logos', ids)} maxItems={rules.logos.max} />
      </div>
      <div>
        <label className="text-xs font-medium mb-1.5 flex items-center gap-1.5"><ImageIcon className="h-3.5 w-3.5" /> Landscape logo — 4:1 (optional) · cropped to 4:1 at submit</label>
        <ReferencePhotosPicker accountId={accountId} value={bundle.landscapeLogos} onChange={ids => setField('landscapeLogos', ids)} maxItems={rules.landscapeLogo.max} />
      </div>
    </div>
  );
}

function SlotSummary({ label, count, required }: { label: string; count: number; required: boolean }) {
  const ok = count > 0 || !required;
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-secondary/20 px-3 py-2 text-xs">
      <span className="flex items-center gap-1.5">
        {ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : <AlertCircle className="h-3.5 w-3.5 text-warning" />}
        {label}{required && <span className="text-muted-foreground">· required</span>}
      </span>
      <span className="tabular-nums text-muted-foreground">{count} image{count === 1 ? '' : 's'}</span>
    </div>
  );
}

function StepReview({ bundle, submitResult, submitting }: {
  bundle: RdaBundle;
  submitResult: { ok: boolean; message: string; campaignId?: string } | null;
  submitting: boolean;
}) {
  const geo = (raw: string) => raw.split(',').map(s => s.trim()).filter(Boolean);
  return (
    <div className="space-y-4 text-sm">
      <ReviewRow label="Campaign name" value={bundle.name} />
      <ReviewRow label="Daily budget" value={`$${parseFloat(bundle.dailyBudget || '0').toFixed(2)}/d`} />
      <ReviewRow label="Bidding" value={bundle.targetCpa.trim() ? `Maximize Conversions · tCPA $${parseFloat(bundle.targetCpa).toFixed(2)}` : 'Maximize Conversions'} />
      <ReviewRow label="Final URL" value={bundle.finalUrl} />
      <ReviewRow label="Business name" value={bundle.businessName} />
      <ReviewRow label="Targeting" value={`geo incl: ${geo(bundle.locationIds).join(', ') || 'all'} · geo excl: ${geo(bundle.excludedLocationIds).join(', ') || 'none'} · lang: ${geo(bundle.languageIds).join(', ') || 'all'}`} />
      <ReviewRow label="Text assets" value={`${bundle.headlines.filter(s => s.trim()).length} headlines · ${bundle.longHeadlines.filter(s => s.trim()).length} long headline · ${bundle.descriptions.filter(s => s.trim()).length} descriptions${bundle.ctaText.trim() ? ` · CTA "${bundle.ctaText.trim()}"` : ''}`} />
      <ReviewRow label="Image assets" value={`${bundle.landscape.length} landscape · ${bundle.square.length} square · ${bundle.logos.length} logo · ${bundle.landscapeLogos.length} landscape logo`} />
      <div className="mt-4 border border-amber-500/30 bg-amber-500/5 rounded-md p-3 text-xs">
        <strong>Campaign will be created PAUSED.</strong> Review the ad in the Google Ads UI before enabling — once enabled, it starts spending immediately.
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
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Creating budget, campaign, targeting, assets, and ad...
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
