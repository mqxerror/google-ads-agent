import { useState, useCallback, useRef, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { studioBalance } from '@/lib/api';
import {
  Film, Upload, Trash2, Download, Sparkles, Search, Loader2, Image as ImageIcon, Music, FileQuestion, X, Target, Wand2, Lock,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns } from '@/lib/api';
import VideoCreator from '@/components/chat/VideoCreator';
import ScriptGenerator from './ScriptGenerator';
import HiggsfieldGenerator from './HiggsfieldGenerator';
import SoulCharactersPanel from './SoulCharactersPanel';

interface AdAsset {
  id: string;
  account_id: string | null;
  campaign_id: string | null;
  type: 'video' | 'image' | 'audio' | 'other';
  filename: string;
  url: string;
  width?: number;
  height?: number;
  duration?: number;
  size_bytes?: number;
  script?: string;
  thumbnail_url?: string;
  source: 'generated' | 'uploaded';
  voice_id?: string;
  avatar_id?: string;
  created_at: string;
}

type Tab = 'all' | 'video' | 'image' | 'audio';
type Source = 'all' | 'uploaded' | 'generated';

async function fetchAssets(accountId: string, filter: { type?: string; q?: string; campaign_id?: string | null; source?: string }): Promise<AdAsset[]> {
  const qs = new URLSearchParams({ account_id: accountId, limit: '200' });
  if (filter.type) qs.set('asset_type', filter.type);
  if (filter.q) qs.set('q', filter.q);
  if (filter.campaign_id) qs.set('campaign_id', filter.campaign_id);
  if (filter.source) qs.set('source', filter.source);
  const r = await fetch(`/api/assets?${qs}`);
  if (!r.ok) return [];
  return r.json();
}

function formatSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

function formatDuration(s?: number): string {
  if (!s) return '';
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m > 0 ? `${m}:${String(r).padStart(2, '0')}` : `${r}s`;
}

function formatRelativeTime(iso?: string): string {
  if (!iso) return '';
  // SQLite stores 'YYYY-MM-DD HH:MM:SS' in UTC — append Z so JS parses as UTC
  const t = new Date(iso.replace(' ', 'T') + 'Z').getTime();
  if (!Number.isFinite(t)) return '';
  const diffSec = Math.max(0, (Date.now() - t) / 1000);
  if (diffSec < 60)        return 'just now';
  if (diffSec < 3600)      return `${Math.floor(diffSec / 60)} min ago`;
  if (diffSec < 86400)     return `${Math.floor(diffSec / 3600)} h ago`;
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} d ago`;
  return new Date(t).toLocaleDateString();
}

function TypeIcon({ type }: { type: string }) {
  if (type === 'video') return <Film className="h-4 w-4" />;
  if (type === 'image') return <ImageIcon className="h-4 w-4" />;
  if (type === 'audio') return <Music className="h-4 w-4" />;
  return <FileQuestion className="h-4 w-4" />;
}

export default function StudioPage() {
  const accountId = useClientAccountId();
  const queryClient = useQueryClient();
  const { setShowStudio } = useAppStore();
  // Higgsfield credit balance — fetched lazily on first showHiggsfield
  // toggle (no point loading on every Studio open if the user isn't
  // generating). Refreshes every 60s while visible, and after each
  // generation settles via the refresh() chain.
  const [balanceCredits, setBalanceCredits] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>('all');
  const [sourceFilter, setSourceFilter] = useState<Source>('all');
  const [q, setQ] = useState('');
  const [showCreator, setShowCreator] = useState(false);
  const [showScripter, setShowScripter] = useState(false);
  const [showHiggsfield, setShowHiggsfield] = useState(false);
  const [showSouls, setShowSouls] = useState(false);

  // Lazy-load balance when the Higgsfield panel opens, then refresh
  // every 60s. Keeps a fresh number visible without polling when the
  // user isn't generating.
  useEffect(() => {
    if (!showHiggsfield) return;
    let cancelled = false;
    const load = () =>
      studioBalance()
        .then((b) => { if (!cancelled) setBalanceCredits(b.credits); })
        .catch(() => { if (!cancelled) setBalanceCredits(null); });
    load();
    const interval = window.setInterval(load, 60_000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [showHiggsfield]);
  const [preview, setPreview] = useState<AdAsset | null>(null);
  const [uploading, setUploading] = useState(false);
  const [campaignScope, setCampaignScope] = useState<string | null>(null);
  const [initialScript, setInitialScript] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', accountId],
    queryFn: () => fetchCampaigns(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  const { data: assets = [], isLoading } = useQuery({
    queryKey: ['ad-assets', accountId, tab, q, campaignScope, sourceFilter],
    queryFn: () => fetchAssets(accountId, {
      type: tab === 'all' ? undefined : tab,
      q: q || undefined,
      campaign_id: campaignScope,
      source: sourceFilter === 'all' ? undefined : sourceFilter,
    }),
    enabled: !!accountId,
    staleTime: 10_000,
  });

  const scopedCampaign = campaigns.find((c) => c.id === campaignScope);

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['ad-assets'] });
  }, [queryClient]);

  const handleUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    const errors: string[] = [];
    try {
      for (const f of Array.from(files)) {
        const fd = new FormData();
        fd.append('file', f);
        if (accountId) fd.append('account_id', accountId);
        if (campaignScope) fd.append('campaign_id', campaignScope);
        try {
          const r = await fetch('/api/assets/upload', { method: 'POST', body: fd });
          if (!r.ok) {
            let detail = `${r.status}`;
            try {
              const body = await r.json();
              if (body?.detail) detail = `${r.status} — ${body.detail}`;
            } catch {
              try { detail = `${r.status} — ${(await r.text()).slice(0, 200)}`; } catch {}
            }
            // Common failure: backend running without python-multipart (shows as 500).
            // Surface that clearly so the user knows to restart the backend.
            if (detail.includes('multipart') || detail.includes('500')) {
              detail += ' — restart backend (deps changed)';
            }
            errors.push(`${f.name}: ${detail}`);
          }
        } catch (e) {
          errors.push(`${f.name}: network error — ${e instanceof Error ? e.message : 'unknown'}`);
        }
      }
      refresh();
      if (errors.length > 0) {
        // Use a single grouped alert so the user sees all failures at once
        alert(`Upload finished with ${errors.length} error${errors.length === 1 ? '' : 's'}:\n\n` + errors.join('\n'));
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [accountId, campaignScope, refresh]);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm('Delete this asset permanently?')) return;
    const r = await fetch(`/api/assets/${id}`, { method: 'DELETE' });
    if (r.ok) refresh();
  }, [refresh]);

  const counts = {
    all: assets.length,
    video: assets.filter(a => a.type === 'video').length,
    image: assets.filter(a => a.type === 'image').length,
    audio: assets.filter(a => a.type === 'audio').length,
  };

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-pink-400" />
              Ad Studio
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Generate, upload, and manage creative for your campaigns
            </p>
          </div>
          {/* Campaign scope — filters library and threads context into script+video gen */}
          <div className="flex items-center gap-1.5 bg-secondary/40 border border-border rounded-md px-2 py-1">
            <Target className="h-3 w-3 text-muted-foreground" />
            <select
              value={campaignScope ?? ''}
              onChange={(e) => setCampaignScope(e.target.value || null)}
              className="bg-transparent text-xs focus:outline-none max-w-[220px]"
              title="Campaign context — filters library and informs generated scripts"
            >
              <option value="">All campaigns (no context)</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Higgsfield credit balance — visible only after the user
              has opened the Higgsfield panel (so we don't shell out
              `higgsfield account balance` on every Studio open).
              Tooltip shows the operator the upstream plan. */}
          {showHiggsfield && (
            <div
              className={cn(
                'text-[10px] font-mono px-2 py-1 rounded border',
                balanceCredits === null
                  ? 'border-border text-muted-foreground'
                  : balanceCredits < 50
                    ? 'border-red-500/40 text-red-600 dark:text-red-400 bg-red-500/5'
                    : balanceCredits < 200
                      ? 'border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/5'
                      : 'border-green-500/30 text-green-600 dark:text-green-400 bg-green-500/5'
              )}
              title="Your Higgsfield credit balance. Refreshes every 60s."
            >
              {balanceCredits ?? '—'} credits
            </div>
          )}
          <button
            onClick={() => setShowStudio(false)}
            className="text-xs text-muted-foreground hover:text-foreground px-2 py-1"
          >
            Back to campaigns
          </button>
          <div className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-md px-2 py-1.5"
               title="Uploaded media is stored on this machine only — never sent to Google or any cloud service.">
            <Lock className="h-3 w-3" />
            local only
          </div>
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
            onClick={() => setShowScripter(v => !v)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border transition-colors',
              showScripter
                ? 'bg-pink-500/25 border-pink-500/50 text-pink-300'
                : 'bg-secondary hover:bg-secondary/80 border-border'
            )}
          >
            <Wand2 className="h-4 w-4" />
            Write script
          </button>
          <button
            onClick={() => setShowHiggsfield(v => !v)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border transition-colors',
              showHiggsfield
                ? 'bg-violet-500/25 border-violet-500/50 text-violet-300'
                : 'bg-secondary hover:bg-secondary/80 border-border'
            )}
            title="Generate images via Higgsfield (Nano Banana Pro, FLUX.2, Soul V2, Marketing Studio)"
          >
            <Sparkles className="h-4 w-4" />
            Generate (Higgsfield)
          </button>
          <button
            onClick={() => setShowSouls(v => !v)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm border transition-colors',
              showSouls
                ? 'bg-violet-500/25 border-violet-500/50 text-violet-300'
                : 'bg-secondary hover:bg-secondary/80 border-border'
            )}
            title="Train + manage Soul characters (face-consistent generation)"
          >
            <Wand2 className="h-4 w-4" />
            Souls
          </button>
          <button
            onClick={() => setShowCreator(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-pink-500/20 hover:bg-pink-500/30 text-pink-300 text-sm border border-pink-500/40"
          >
            <Film className="h-4 w-4" />
            New video
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

      {/* Script generator panel */}
      {showScripter && (
        <div className="mb-4">
          <ScriptGenerator
            accountId={accountId}
            campaignId={campaignScope}
            campaignName={scopedCampaign?.name ?? null}
            onUseScript={(block) => {
              setInitialScript(block);
              setShowCreator(true);
              setShowScripter(false);
            }}
          />
        </div>
      )}

      {/* Higgsfield generator panel (V13 / S2) — generations land in
          ad_assets via the row-as-source-of-truth pattern; refresh on
          settled to surface them in the library grid below. */}
      {showHiggsfield && (
        <div className="mb-4">
          <HiggsfieldGenerator
            accountId={accountId}
            campaignId={campaignScope ?? undefined}
            onSettled={() => refresh()}
            caption="Image generation — Higgsfield CLI"
          />
        </div>
      )}

      {/* Soul characters panel (V14 / S5) — train face-consistent
          character references that the generator's Soul-aware models
          (text2image_soul_v2 / soul_cinematic / soul_cast) reference
          via --soul-id, producing recognizably the same person across
          every render. */}
      {showSouls && (
        <div className="mb-4">
          <SoulCharactersPanel accountId={accountId} />
        </div>
      )}

      {/* Inline video creator drawer */}
      {showCreator && (
        <div className="mb-5 border border-pink-500/30 rounded-lg overflow-hidden bg-card">
          <VideoCreator
            open={showCreator}
            onClose={() => { setShowCreator(false); setInitialScript(''); }}
            onVideoReady={() => { refresh(); setShowCreator(false); setInitialScript(''); }}
            initialScript={initialScript || undefined}
            accountId={accountId}
            campaignId={campaignScope}
          />
        </div>
      )}

      {/* Tabs + source filter + search */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-1 border border-border rounded-md p-0.5 bg-secondary/30">
          {(['all', 'video', 'image', 'audio'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'px-3 py-1 rounded text-xs capitalize transition-colors',
                tab === t ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {t} <span className="ml-1 text-muted-foreground/70">{counts[t]}</span>
            </button>
          ))}
        </div>

        {/* Source filter — separates uploaded files from AI-generated renders */}
        <div className="flex items-center gap-1 border border-border rounded-md p-0.5 bg-secondary/30">
          {([
            { key: 'all' as Source, label: 'All sources' },
            { key: 'uploaded' as Source, label: 'Uploaded' },
            { key: 'generated' as Source, label: 'AI-generated' },
          ]).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setSourceFilter(key)}
              className={cn(
                'px-2.5 py-1 rounded text-[11px] transition-colors',
                sourceFilter === key
                  ? key === 'uploaded' ? 'bg-emerald-500/20 text-emerald-300'
                  : key === 'generated' ? 'bg-pink-500/20 text-pink-300'
                  : 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by filename or script..."
            className="w-full pl-7 pr-2 py-1.5 text-xs bg-secondary/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        {/* Refresh — pulls fresh asset list (renders triggered outside the
            planner via the API don't auto-refresh the React Query cache). */}
        <button
          onClick={refresh}
          className="px-2.5 py-1.5 text-[11px] bg-secondary/30 hover:bg-secondary/50 border border-border rounded-md flex items-center gap-1"
          title="Reload asset list"
        >
          ↻ Refresh
        </button>
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="text-muted-foreground text-sm py-12 text-center">
          <Loader2 className="h-4 w-4 animate-spin inline mr-2" /> Loading library...
        </div>
      ) : assets.length === 0 ? (
        <div className="border border-dashed border-border rounded-lg py-16 text-center">
          <Sparkles className="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">
            {q
              ? 'No assets match your search.'
              : scopedCampaign
                ? `No assets yet for ${scopedCampaign.name}. Generate or upload one.`
                : 'No assets yet. Generate a video or upload one to get started.'}
          </p>
          {!q && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => setShowCreator(true)}
                className="text-xs px-3 py-1.5 rounded bg-pink-500/20 text-pink-300 hover:bg-pink-500/30"
              >
                Create your first video
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-xs px-3 py-1.5 rounded bg-secondary text-foreground hover:bg-secondary/80"
              >
                Upload media
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {assets.map((a) => (
            <div
              key={a.id}
              className="group border border-border rounded-lg overflow-hidden bg-card hover:border-primary/40 transition-colors"
            >
              {/* Preview */}
              <button
                onClick={() => setPreview(a)}
                className="block w-full aspect-video bg-black relative overflow-hidden"
                title="Click to preview"
              >
                {a.type === 'video' ? (
                  <video src={a.url} poster={a.thumbnail_url} muted preload="metadata" className="w-full h-full object-cover" />
                ) : a.type === 'image' ? (
                  <img src={a.url} alt={a.filename} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <TypeIcon type={a.type} />
                  </div>
                )}
                <div className="absolute top-1 left-1 flex items-center gap-1 bg-black/60 text-white text-[9px] px-1.5 py-0.5 rounded">
                  <TypeIcon type={a.type} />
                  <span>{a.type}</span>
                </div>
                {a.source === 'generated' && (
                  <span className="absolute top-1 right-1 text-[9px] bg-pink-500/80 text-white px-1.5 py-0.5 rounded">
                    AI
                  </span>
                )}
              </button>

              {/* Meta */}
              <div className="p-2 space-y-1">
                <div className="text-xs font-medium truncate" title={a.filename}>
                  {a.filename}
                </div>
                {a.script && (
                  <div className="text-[10px] text-muted-foreground line-clamp-2 italic">
                    "{a.script}"
                  </div>
                )}
                <div className="flex items-center gap-2 text-[9px] text-muted-foreground/80">
                  {a.width && a.height && <span>{a.width}×{a.height}</span>}
                  {a.duration && <span>{formatDuration(a.duration)}</span>}
                  {a.size_bytes && <span>{formatSize(a.size_bytes)}</span>}
                  {a.created_at && (
                    <span className="ml-auto text-violet-300/70" title={a.created_at + ' UTC'}>
                      {formatRelativeTime(a.created_at)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 pt-1">
                  <a
                    href={a.url}
                    download={a.filename}
                    className="flex-1 text-center text-[10px] px-2 py-1 rounded bg-secondary/60 hover:bg-secondary text-foreground inline-flex items-center justify-center gap-1"
                  >
                    <Download className="h-3 w-3" /> Download
                  </a>
                  <button
                    onClick={() => handleDelete(a.id)}
                    className="text-[10px] px-2 py-1 rounded bg-secondary/60 hover:bg-red-500/20 hover:text-red-400 text-muted-foreground"
                    title="Delete"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview modal */}
      {preview && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center p-6 z-50"
          onClick={() => setPreview(null)}
        >
          <div
            className="bg-card border border-border rounded-lg max-w-3xl w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-sm font-medium truncate">{preview.filename}</span>
              <button onClick={() => setPreview(null)} className="p-1 text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="bg-black">
              {preview.type === 'video' ? (
                <video src={preview.url} poster={preview.thumbnail_url} controls autoPlay className="w-full max-h-[70vh]" />
              ) : preview.type === 'image' ? (
                <img src={preview.url} alt={preview.filename} className="w-full max-h-[70vh] object-contain" />
              ) : (
                <div className="p-8 text-center text-muted-foreground">Preview not supported for this type</div>
              )}
            </div>
            {preview.script && (
              <div className="px-4 py-3 border-t border-border text-xs">
                <div className="text-muted-foreground mb-1 text-[10px]">Script</div>
                <div className="italic">"{preview.script}"</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
