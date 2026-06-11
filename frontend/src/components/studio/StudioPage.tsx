/**
 * StudioPage — the calm Studio hub (Epic 12, pass 1).
 *
 * Slimmed per the redesign brief: Asset Library + Soul Creator +
 * Presets, with ONE "Create" button that opens the shared StudioPanel
 * (no campaign context — the in-flow panels carry context instead).
 * The old inline generator toolbars (HiggsfieldGenerator) retired in
 * Phase B; upload and the legacy video tools (script writer + brand
 * reel) stay reachable as quiet actions.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Film, Loader2, Lock, Sparkles, Upload, Wand2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns, studioBalance } from '@/lib/api';
import type { MarketingHook, SoulCharacter } from '@/lib/api';
import VideoCreator from '@/components/chat/VideoCreator';
import ScriptGenerator from './ScriptGenerator';
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

export default function StudioPage() {
  const accountId = useClientAccountId();
  const queryClient = useQueryClient();
  const { setShowStudio } = useAppStore();

  const [section, setSection] = useState<HubSection>('library');
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelMode, setPanelMode] = useState<'image' | 'video'>('image');
  const [preset, setPreset] = useState<StudioPanelPreset | undefined>(undefined);
  const [panelEverOpened, setPanelEverOpened] = useState(false);

  const [showScripter, setShowScripter] = useState(false);
  const [showCreator, setShowCreator] = useState(false);
  const [initialScript, setInitialScript] = useState('');
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
            <Sparkles className="h-5 w-5 text-primary" />
            Studio
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Your asset library, Soul characters, and preset concepts in one place
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
            onClick={() => setShowStudio(false)}
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
          <button
            onClick={() => setShowScripter((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border transition-colors',
              showScripter ? 'bg-accent-soft border-accent/40 text-accent' : 'bg-secondary hover:bg-secondary/80 border-border',
            )}
            title="Write a spoken-ad script (feeds the brand-reel video tool)"
          >
            <Wand2 className="h-4 w-4" />
            Write script
          </button>
          <button
            onClick={() => setShowCreator(true)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border transition-colors',
              showCreator ? 'bg-accent-soft border-accent/40 text-accent' : 'bg-secondary hover:bg-secondary/80 border-border',
            )}
            title="Brand-reel video tool (avatar + voiceover)"
          >
            <Film className="h-4 w-4" />
            New video
          </button>
          {/* THE one primary action — opens the shared Studio panel */}
          <button
            onClick={() => openCreate(panelMode)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-accent-hover text-sm font-medium"
            title="Generate an image or video with the Studio panel"
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

      {/* Script generator drawer (legacy video tool — kept reachable) */}
      {showScripter && (
        <div className="mb-4">
          <ScriptGenerator
            accountId={accountId}
            campaignId={null}
            campaignName={null}
            onUseScript={(block) => {
              setInitialScript(block);
              setShowCreator(true);
              setShowScripter(false);
            }}
          />
        </div>
      )}

      {/* Brand-reel video creator drawer (legacy video tool) */}
      {showCreator && (
        <div className="mb-5 border border-border rounded-lg overflow-hidden bg-card">
          <VideoCreator
            open={showCreator}
            onClose={() => { setShowCreator(false); setInitialScript(''); }}
            onVideoReady={() => { refreshAssets(); setShowCreator(false); setInitialScript(''); }}
            initialScript={initialScript || undefined}
            accountId={accountId}
            campaignId={null}
          />
        </div>
      )}

      {/* Section tabs — Library / Souls / Presets */}
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
