/**
 * StudioHome — Studio Home, the calm chooser (Epic A / redesign plan §2.3).
 *
 * The former Studio hub body. Now a fork at the door: THREE door cards
 * over the shared Library / Souls / Presets tabs. Each door states its
 * engine identity explicitly (that is the whole point of the fork —
 * kill the ambiguity where the engine hid inside mode names):
 *   - AI Video Studio  → /studio/ai-video   (Higgsfield generative video)
 *   - Kinetic Studio   → /studio/kinetic     (Hyperframes GSAP + Brand Reel, local)
 *   - Image Studio     → opens StudioPanel in image mode (§2.4 — no page shell)
 *
 * Library / Souls / Presets stay here as shared substrate (every studio
 * writes to the same ad_assets library; Souls are used by both image and
 * video Higgsfield paths). See research/studio-redesign-plan.md §2.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Clapperboard, Image as ImageIcon, Loader2, Lock, Sparkles, Type, Upload,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { fetchCampaigns, studioBalance } from '@/lib/api';
import type { MarketingHook, SoulCharacter } from '@/lib/api';
import MarketingPresetsPanel from './MarketingPresetsPanel';
import StudioPanel, { type StudioPanelPreset } from './StudioPanel';
import AssetLibrary, { ASSETS_QUERY_KEY } from './AssetLibrary';
import SoulCreator from './SoulCreator';

type HubSection = 'library' | 'souls' | 'presets';

const SECTIONS: { key: HubSection; label: string }[] = [
  { key: 'library', label: 'Library' },
  { key: 'souls', label: 'Souls' },
  { key: 'presets', label: 'Presets' },
];

export default function StudioHome() {
  const accountId = useClientAccountId();
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [section, setSection] = useState<HubSection>('library');
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelMode, setPanelMode] = useState<'image' | 'video'>('image');
  const [preset, setPreset] = useState<StudioPanelPreset | undefined>(undefined);
  const [panelEverOpened, setPanelEverOpened] = useState(false);

  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', accountId],
    queryFn: () => fetchCampaigns(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  // Higgsfield credit balance — fetched lazily once the panel has been
  // opened (a CLI shell-out; no point on every Studio visit), then
  // refreshed every 60s while the Studio stays mounted.
  const [balanceCredits, setBalanceCredits] = useState<number | null>(null);
  useEffect(() => {
    if (!panelEverOpened) return;
    let cancelled = false;
    const load = () =>
      studioBalance()
        .then((b) => { if (!cancelled) setBalanceCredits(b.credits); })
        .catch(() => { if (!cancelled) setBalanceCredits(null); });
    load();
    const interval = window.setInterval(load, 60_000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [panelEverOpened]);

  // Resume chip: shows when a drafting/storyboard project exists.
  // A backend agent is building the video-projects endpoint in parallel;
  // guard the fetch so a missing/failing endpoint just hides the chip
  // (never breaks Home). Epic B/C wire the real project resume flow.
  const [resumeProject, setResumeProject] = useState<{ id: string; title: string } | null>(null);
  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    fetch(`/api/studio/video-projects?account_id=${encodeURIComponent(accountId)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((rows) => {
        if (cancelled || !Array.isArray(rows)) return;
        const inProgress = rows.find(
          (p: { status?: string }) => p?.status === 'drafting' || p?.status === 'storyboard',
        );
        if (inProgress) {
          setResumeProject({
            id: inProgress.id,
            title: inProgress.title || 'Untitled project',
          });
        }
      })
      .catch(() => { /* endpoint not up yet — no chip, no error */ });
    return () => { cancelled = true; };
  }, [accountId]);

  const refreshAssets = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [ASSETS_QUERY_KEY] });
  }, [queryClient]);

  const openCreate = useCallback((mode: 'image' | 'video' = 'image', p?: StudioPanelPreset) => {
    setPanelMode(mode);
    if (p) setPreset(p);
    setPanelOpen(true);
    setPanelEverOpened(true);
  }, []);

  const handleUseHook = useCallback((h: MarketingHook) => {
    // Marketing Studio hooks are pre-engineered concepts — flow the
    // prompt into the panel with the Marketing Studio image model.
    openCreate('image', { prompt: h.prompt, model: 'marketing_studio_image' });
  }, [openCreate]);

  const handleTestGenerate = useCallback((soul: SoulCharacter) => {
    if (!soul.soul_id) return;
    openCreate('image', { model: 'text2image_soul_v2', soulId: soul.soul_id });
  }, [openCreate]);

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const errors: string[] = [];
    try {
      for (const f of Array.from(files)) {
        const fd = new FormData();
        fd.append('file', f);
        if (accountId) fd.append('account_id', accountId);
        try {
          const r = await fetch('/api/assets/upload', { method: 'POST', body: fd });
          if (!r.ok) {
            let detail = `${r.status}`;
            try {
              const body = await r.json();
              if (body?.detail) detail = `${r.status} — ${body.detail}`;
            } catch {
              try { detail = `${r.status} — ${(await r.text()).slice(0, 200)}`; } catch { /* noop */ }
            }
            // Common failure: backend running without python-multipart (shows as 500).
            if (detail.includes('multipart') || detail.includes('500')) {
              detail += ' — restart backend (deps changed)';
            }
            errors.push(`${f.name}: ${detail}`);
          }
        } catch (e) {
          errors.push(`${f.name}: network error — ${e instanceof Error ? e.message : 'unknown'}`);
        }
      }
      refreshAssets();
      if (errors.length > 0) {
        alert(`Upload finished with ${errors.length} error${errors.length === 1 ? '' : 's'}:\n\n` + errors.join('\n'));
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [accountId, refreshAssets]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-accent" />
            Studio
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Create video and image assets, manage Souls and presets
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {panelEverOpened && (
            <span
              className={cn(
                'text-[10px] font-mono px-2 py-1 rounded border',
                balanceCredits === null
                  ? 'border-border text-muted-foreground'
                  : balanceCredits < 50
                    ? 'border-danger/40 text-danger bg-danger-soft'
                    : balanceCredits < 200
                      ? 'border-warning/40 text-warning bg-warning-soft'
                      : 'border-success/30 text-success bg-success-soft',
              )}
              title="Your Higgsfield credit balance. Refreshes every 60s."
            >
              {balanceCredits ?? '—'} credits
            </span>
          )}
          <span
            className="inline-flex items-center gap-1 text-[10px] text-success bg-success-soft border border-success/30 rounded-md px-2 py-1.5"
            title="Uploaded media is stored on this machine only — never sent to Google or any cloud service."
          >
            <Lock className="h-3 w-3" />
            local only
          </span>
          <button
            onClick={() => navigate('/')}
            className="text-xs text-muted-foreground hover:text-foreground px-2 py-1"
          >
            Back to campaigns
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-secondary hover:bg-secondary/80 text-sm border border-border"
            title="Upload local files to your library (stored on this machine)"
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload
          </button>
          {/* THE one primary action — opens the shared Studio panel in
              image mode. "Write script" and "New video" moved to the
              Kinetic Studio door (plan §2.2.5); this stays for quick
              single-shot image generation. */}
          <button
            onClick={() => openCreate('image')}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-accent text-on-accent hover:bg-accent-hover text-sm font-medium"
            title="Generate an image with the Studio panel"
          >
            <Sparkles className="h-4 w-4" />
            Create
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".mp4,.mov,.webm,.png,.jpg,.jpeg,.gif,.webp,.mp3,.wav"
            onChange={(e) => handleUpload(e.target.files)}
            className="hidden"
          />
        </div>
      </div>

      {/* Door cards — the fork (plan §2.3). Three TRUE choice-cards, each
          carrying DISTINCT meta so this is not an identical icon-grid:
          AI Video = resume chip + model-count/credits; Kinetic = a
          "local · free" no-credits badge; Image = model-count/credits. */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        {/* AI Video Studio */}
        <DoorCard
          glyph={<Clapperboard className="h-5 w-5 text-accent" />}
          title="AI Video Studio"
          blurb="Generative video with a Video Director"
          engine="Higgsfield · Veo, Kling, Seedance, Soul"
          chip="12 models · credits"
          cta="Open studio"
          onOpen={() =>
            navigate(resumeProject ? `/studio/ai-video/${resumeProject.id}` : '/studio/ai-video')
          }
          resume={resumeProject?.title}
        />
        {/* Kinetic Studio */}
        <DoorCard
          glyph={<Type className="h-5 w-5 text-accent" />}
          title="Kinetic Studio"
          blurb="Motion graphics and kinetic typography"
          engine="Hyperframes (GSAP) + Brand Reel"
          chip="local · free"
          chipTone="success"
          cta="Open studio"
          onOpen={() => navigate('/studio/kinetic')}
        />
        {/* Image Studio — §13 default: the door opens the existing
            StudioPanel in image mode; NOT a page shell (plan §2.4). */}
        <DoorCard
          glyph={<ImageIcon className="h-5 w-5 text-accent" />}
          title="Image Studio"
          blurb="Generative images and Soul portraits"
          engine="Higgsfield · Nano Banana, GPT Image, Soul"
          chip="10 models · credits"
          cta="Create image"
          onOpen={() => openCreate('image')}
        />
      </div>

      {/* Section tabs — Library / Souls / Presets. Shared substrate,
          stays on Home (plan §2.1). §13 default: Presets stay on Home. */}
      <div className="flex items-center gap-1 border-b border-border mb-4">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            onClick={() => setSection(s.key)}
            className={cn(
              'px-3 py-1.5 text-sm -mb-px border-b-2 transition-colors',
              section === s.key
                ? 'border-accent text-accent font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === 'library' && (
        <AssetLibrary
          accountId={accountId}
          campaigns={campaigns.map((c) => ({ id: c.id, name: c.name }))}
          onCreate={() => openCreate('image')}
          onUpload={() => fileInputRef.current?.click()}
        />
      )}

      {section === 'souls' && (
        <SoulCreator accountId={accountId} onTestGenerate={handleTestGenerate} />
      )}

      {section === 'presets' && (
        <MarketingPresetsPanel onUseHook={handleUseHook} />
      )}

      {/* The shared Studio panel — stays mounted so jobs survive
          close/reopen (brief §7). No campaign context in the hub. */}
      <StudioPanel
        open={panelOpen}
        onClose={() => setPanelOpen(false)}
        mode={panelMode}
        onModeChange={setPanelMode}
        accountId={accountId}
        preset={preset}
        onJobSettled={refreshAssets}
      />
    </div>
  );
}

/**
 * DoorCard — a single studio door (plan §2.3). Within DESIGN.md:
 * bg-card + border-border + resting shadow, hover lifts to elevated
 * shadow + border-accent/40 (transform/opacity only, ~180ms). Keyboard
 * focusable (real <button>). One glyph tinted text-accent per card; the
 * mono chip is what makes the engine identity explicit at the door.
 */
function DoorCard({
  glyph, title, blurb, engine, chip, chipTone = 'muted', cta, onOpen, resume,
}: {
  glyph: React.ReactNode;
  title: string;
  blurb: string;
  engine: string;
  chip: string;
  chipTone?: 'muted' | 'success';
  cta: string;
  onOpen: () => void;
  resume?: string;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'group text-left flex flex-col gap-2 rounded-lg border border-border bg-card p-4',
        'shadow-[var(--shadow-resting)] transition-[transform,box-shadow,border-color]',
        'duration-200 ease-[var(--ease-out-quint)]',
        'hover:-translate-y-0.5 hover:shadow-[var(--shadow-elevated)] hover:border-accent/40',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-accent-soft">
          {glyph}
        </span>
        <span
          className={cn(
            'text-[10px] font-mono px-2 py-0.5 rounded border',
            chipTone === 'success'
              ? 'border-success/30 text-success bg-success-soft'
              : 'border-border text-muted-foreground bg-surface-2',
          )}
        >
          {chip}
        </span>
      </div>
      <div className="text-[18px] font-semibold leading-tight">{title}</div>
      <p className="text-xs text-muted-foreground leading-snug">{blurb}</p>
      <p className="text-[12px] text-muted-foreground mt-auto">{engine}</p>
      <div className="flex items-center justify-between gap-2 pt-1">
        <span className="text-sm text-accent font-medium group-hover:underline">
          {cta} →
        </span>
        {resume && (
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded border border-accent/30 text-accent bg-accent-soft max-w-[45%] truncate"
            title={`Resume in-progress project: ${resume}`}
          >
            Resume: {resume}
          </span>
        )}
      </div>
    </button>
  );
}
