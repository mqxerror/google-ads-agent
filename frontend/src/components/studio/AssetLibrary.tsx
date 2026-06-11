/**
 * AssetLibrary — the Studio hub's redesigned media library (Epic 12,
 * story 12.2).
 *
 * Brief §5: filter rail (type · campaign · model · date) + dense quiet
 * grid, search, metadata on hover/expand (prompt, model, cost,
 * created), select-to-use, compare (2-up), delete/download, relative
 * times. Paginates past ~100 items via offset "Load more" pages.
 *
 * DECOUPLING: this component knows nothing about Google Ads. The host
 * supplies `campaigns` (id + name pairs for the filter rail) and an
 * optional `onUse` callback — same contract shape as StudioPanel.
 */

import { useMemo, useState } from 'react';
import { useInfiniteQuery, useQueryClient } from '@tanstack/react-query';
import {
  Check, Download, Film, FileQuestion, Image as ImageIcon, Loader2,
  Music, Search, Sparkles, Trash2, X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export interface AdAsset {
  id: string;
  account_id: string | null;
  campaign_id: string | null;
  type: 'video' | 'image' | 'audio' | 'other';
  filename: string;
  url: string;
  width?: number | null;
  height?: number | null;
  duration?: number | null;
  size_bytes?: number | null;
  script?: string | null;
  thumbnail_url?: string | null;
  source: 'generated' | 'uploaded';
  created_at: string;
  // Generation metadata (null for uploads / older renders)
  prompt?: string | null;
  model?: string | null;
  aspect_ratio?: string | null;
  generation_cost_credits?: number | null;
  status?: string | null;
}

interface AssetLibraryProps {
  accountId: string;
  campaigns: { id: string; name: string }[];
  /** Select-to-use: when provided, assets get a "Use" action. */
  onUse?: (asset: AdAsset) => void;
  /** Empty-state CTA — host opens the Studio panel. */
  onCreate?: () => void;
  /** Empty-state CTA — host opens its upload picker. */
  onUpload?: () => void;
}

const PAGE = 60;
export const ASSETS_QUERY_KEY = 'studio-assets';

type TypeFilter = 'all' | 'image' | 'video' | 'audio';
type SourceFilter = 'all' | 'generated' | 'uploaded';
type DateFilter = 'any' | 'today' | '7d' | '30d';

const DATE_LABELS: Record<DateFilter, string> = {
  any: 'Any time', today: 'Today', '7d': 'Last 7 days', '30d': 'Last 30 days',
};

function sinceFor(d: DateFilter): string | undefined {
  if (d === 'any') return undefined;
  const days = d === 'today' ? 1 : d === '7d' ? 7 : 30;
  return new Date(Date.now() - days * 86_400_000).toISOString();
}

async function fetchAssetsPage(
  accountId: string,
  f: { type?: string; source?: string; campaign?: string; model?: string; since?: string; q?: string },
  offset: number,
): Promise<AdAsset[]> {
  const qs = new URLSearchParams({
    account_id: accountId, limit: String(PAGE), offset: String(offset),
  });
  if (f.type) qs.set('asset_type', f.type);
  if (f.source) qs.set('source', f.source);
  if (f.campaign) qs.set('campaign_id', f.campaign);
  if (f.model) qs.set('model', f.model);
  if (f.since) qs.set('since', f.since);
  if (f.q) qs.set('q', f.q);
  const r = await fetch(`/api/assets?${qs}`);
  if (!r.ok) throw new Error(`assets list failed (${r.status})`);
  return r.json();
}

// ── formatters ────────────────────────────────────────────────────

function formatSize(bytes?: number | null): string {
  if (!bytes) return '';
  if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

function formatDuration(s?: number | null): string {
  if (!s) return '';
  const m = Math.floor(s / 60);
  const r = Math.round(s % 60);
  return m > 0 ? `${m}:${String(r).padStart(2, '0')}` : `${r}s`;
}

export function formatRelativeTime(iso?: string): string {
  if (!iso) return '';
  // SQLite stores 'YYYY-MM-DD HH:MM:SS' in UTC — append Z so JS parses as UTC
  const t = new Date(iso.replace(' ', 'T') + (iso.endsWith('Z') ? '' : 'Z')).getTime();
  if (!Number.isFinite(t)) return '';
  const diffSec = Math.max(0, (Date.now() - t) / 1000);
  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} h ago`;
  if (diffSec < 86400 * 7) return `${Math.floor(diffSec / 86400)} d ago`;
  return new Date(t).toLocaleDateString();
}

function TypeIcon({ type, className }: { type: string; className?: string }) {
  const cls = className ?? 'h-4 w-4';
  if (type === 'video') return <Film className={cls} />;
  if (type === 'image') return <ImageIcon className={cls} />;
  if (type === 'audio') return <Music className={cls} />;
  return <FileQuestion className={cls} />;
}

// ── component ─────────────────────────────────────────────────────

export default function AssetLibrary({ accountId, campaigns, onUse, onCreate, onUpload }: AssetLibraryProps) {
  const queryClient = useQueryClient();
  const [type, setType] = useState<TypeFilter>('all');
  const [source, setSource] = useState<SourceFilter>('all');
  const [campaign, setCampaign] = useState('');
  const [model, setModel] = useState('');
  const [date, setDate] = useState<DateFilter>('any');
  const [q, setQ] = useState('');
  const [detail, setDetail] = useState<AdAsset | null>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);

  const filters = useMemo(() => ({
    type: type === 'all' ? undefined : type,
    source: source === 'all' ? undefined : source,
    campaign: campaign || undefined,
    model: model || undefined,
    since: sinceFor(date),
    q: q.trim() || undefined,
  }), [type, source, campaign, model, date, q]);

  const query = useInfiniteQuery({
    queryKey: [ASSETS_QUERY_KEY, accountId, filters],
    queryFn: ({ pageParam }) => fetchAssetsPage(accountId, filters, pageParam as number),
    initialPageParam: 0,
    getNextPageParam: (last, all) => (last.length === PAGE ? all.length * PAGE : undefined),
    enabled: !!accountId,
    staleTime: 10_000,
  });

  // Hide rows that never produced a file (in-flight or failed
  // generations) — the panel surfaces those states, not the library.
  const assets = useMemo(
    () => (query.data?.pages.flat() ?? []).filter((a) => !!a.url),
    [query.data],
  );

  // Model facet derived from loaded pages (grows as pages load).
  const modelFacet = useMemo(() => {
    const set = new Set<string>();
    assets.forEach((a) => { if (a.model) set.add(a.model); });
    if (model) set.add(model);
    return Array.from(set).sort();
  }, [assets, model]);

  const campaignName = (id?: string | null) =>
    campaigns.find((c) => c.id === id)?.name ?? null;

  const hasFilters = type !== 'all' || source !== 'all' || !!campaign || !!model || date !== 'any' || !!q.trim();
  const clearFilters = () => {
    setType('all'); setSource('all'); setCampaign(''); setModel(''); setDate('any'); setQ('');
  };

  const refresh = () => queryClient.invalidateQueries({ queryKey: [ASSETS_QUERY_KEY] });

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this asset permanently?')) return;
    const r = await fetch(`/api/assets/${id}`, { method: 'DELETE' });
    if (r.ok) {
      setDetail((d) => (d?.id === id ? null : d));
      setCompareIds((ids) => ids.filter((x) => x !== id));
      refresh();
    }
  };

  const toggleCompare = (id: string) => {
    setCompareIds((ids) => {
      if (ids.includes(id)) return ids.filter((x) => x !== id);
      // 2-up: third pick replaces the older selection
      return ids.length >= 2 ? [ids[1], id] : [...ids, id];
    });
  };

  const compareAssets = compareIds
    .map((id) => assets.find((a) => a.id === id))
    .filter((a): a is AdAsset => !!a);

  return (
    <div className="flex gap-4 items-start">
      {/* ── Filter rail ── */}
      <aside className="w-44 shrink-0 space-y-4 sticky top-0">
        <RailGroup label="Type">
          {(['all', 'image', 'video', 'audio'] as TypeFilter[]).map((t) => (
            <RailItem key={t} active={type === t} onClick={() => setType(t)}>
              <span className="capitalize">{t === 'all' ? 'All types' : `${t}s`}</span>
            </RailItem>
          ))}
        </RailGroup>
        <RailGroup label="Source">
          {([
            ['all', 'All sources'], ['generated', 'AI-generated'], ['uploaded', 'Uploaded'],
          ] as [SourceFilter, string][]).map(([k, label]) => (
            <RailItem key={k} active={source === k} onClick={() => setSource(k)}>{label}</RailItem>
          ))}
        </RailGroup>
        <RailGroup label="Campaign">
          <select
            value={campaign}
            onChange={(e) => setCampaign(e.target.value)}
            className="w-full h-7 rounded border border-border bg-background px-1.5 text-xs"
          >
            <option value="">All campaigns</option>
            {campaigns.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </RailGroup>
        <RailGroup label="Model">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full h-7 rounded border border-border bg-background px-1.5 text-xs font-mono"
          >
            <option value="">All models</option>
            {modelFacet.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </RailGroup>
        <RailGroup label="Created">
          {(Object.keys(DATE_LABELS) as DateFilter[]).map((d) => (
            <RailItem key={d} active={date === d} onClick={() => setDate(d)}>{DATE_LABELS[d]}</RailItem>
          ))}
        </RailGroup>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="text-[11px] text-muted-foreground hover:text-foreground underline"
          >
            Clear filters
          </button>
        )}
      </aside>

      {/* ── Grid column ── */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search filename, prompt, or script…"
              className="w-full pl-7 pr-2 py-1.5 text-xs bg-secondary/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <span className="text-[11px] text-muted-foreground">
            {assets.length}{query.hasNextPage ? '+' : ''} asset{assets.length === 1 ? '' : 's'}
          </span>
          <button
            onClick={refresh}
            className="px-2.5 py-1.5 text-[11px] bg-secondary/30 hover:bg-secondary/50 border border-border rounded-md"
            title="Reload asset list"
          >
            ↻ Refresh
          </button>
        </div>

        {query.isLoading ? (
          <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="aspect-square rounded-md bg-secondary/40 animate-pulse" />
            ))}
          </div>
        ) : assets.length === 0 ? (
          <div className="border border-dashed border-border rounded-lg py-16 text-center">
            <Sparkles className="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              {hasFilters
                ? 'No assets match these filters.'
                : 'No assets yet. Generate your first asset or upload media to get started.'}
            </p>
            <div className="mt-4 flex items-center justify-center gap-2">
              {hasFilters ? (
                <button
                  onClick={clearFilters}
                  className="text-xs px-3 py-1.5 rounded bg-secondary text-foreground hover:bg-secondary/80"
                >
                  Clear filters
                </button>
              ) : (
                <>
                  {onCreate && (
                    <Button size="sm" onClick={onCreate} className="gap-1.5">
                      <Sparkles className="h-3.5 w-3.5" /> Generate your first asset
                    </Button>
                  )}
                  {onUpload && (
                    <Button size="sm" variant="outline" onClick={onUpload}>
                      Upload media
                    </Button>
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
              {assets.map((a) => (
                <AssetTile
                  key={a.id}
                  asset={a}
                  comparing={compareIds.includes(a.id)}
                  onOpen={() => setDetail(a)}
                  onToggleCompare={() => toggleCompare(a.id)}
                />
              ))}
            </div>
            {query.hasNextPage && (
              <div className="mt-4 text-center">
                <Button
                  size="sm" variant="outline"
                  onClick={() => query.fetchNextPage()}
                  disabled={query.isFetchingNextPage}
                  className="gap-1.5"
                >
                  {query.isFetchingNextPage && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Load more
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Compare bar ── */}
      {compareIds.length > 0 && !comparing && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-card border border-border rounded-lg shadow-lg px-3 py-2">
          <span className="text-xs text-muted-foreground">
            {compareIds.length} selected for compare
          </span>
          <Button
            size="sm"
            disabled={compareAssets.length < 2}
            onClick={() => setComparing(true)}
          >
            Compare 2-up
          </Button>
          <button
            onClick={() => setCompareIds([])}
            className="p-1 hover:bg-secondary rounded"
            aria-label="Clear compare selection"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* ── Detail expand ── */}
      {detail && (
        <AssetDetailModal
          asset={detail}
          campaignName={campaignName(detail.campaign_id)}
          onClose={() => setDetail(null)}
          onUse={onUse}
          onDelete={() => handleDelete(detail.id)}
          onCompare={() => { toggleCompare(detail.id); setDetail(null); }}
          inCompare={compareIds.includes(detail.id)}
        />
      )}

      {/* ── 2-up compare overlay ── */}
      {comparing && compareAssets.length === 2 && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6"
          onClick={() => setComparing(false)}
        >
          <div
            className="bg-card border border-border rounded-lg max-w-6xl w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-sm font-medium">Compare</span>
              <button
                onClick={() => setComparing(false)}
                className="p-1 text-muted-foreground hover:text-foreground"
                aria-label="Close compare"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-2 divide-x divide-border">
              {compareAssets.map((a) => (
                <div key={a.id} className="min-w-0">
                  <div className="bg-black flex items-center justify-center">
                    {a.type === 'video' ? (
                      <video src={a.url} poster={a.thumbnail_url ?? undefined} controls muted className="w-full max-h-[55vh] object-contain" />
                    ) : (
                      <img src={a.url} alt={a.filename} className="w-full max-h-[55vh] object-contain" />
                    )}
                  </div>
                  <div className="p-3 space-y-1 text-xs">
                    <div className="font-medium truncate" title={a.filename}>{a.filename}</div>
                    <MetaRows asset={a} campaignName={campaignName(a.campaign_id)} />
                    {onUse && (
                      <Button size="sm" className="mt-1.5 gap-1.5" onClick={() => onUse(a)}>
                        <Check className="h-3 w-3" /> Use this one
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── pieces ────────────────────────────────────────────────────────

function RailGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="label-section mb-1.5">{label}</div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function RailItem({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'block w-full text-left px-2 py-1 rounded text-xs transition-colors',
        active ? 'bg-accent-soft text-accent font-medium' : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50',
      )}
    >
      {children}
    </button>
  );
}

function AssetTile({ asset: a, comparing, onOpen, onToggleCompare }: {
  asset: AdAsset; comparing: boolean; onOpen: () => void; onToggleCompare: () => void;
}) {
  return (
    <div
      className={cn(
        'group relative rounded-md overflow-hidden border bg-card transition-colors',
        comparing ? 'border-primary ring-1 ring-primary' : 'border-border hover:border-primary/40',
      )}
    >
      <button onClick={onOpen} className="block w-full aspect-square bg-secondary/30 relative" title={a.filename}>
        {a.type === 'video' ? (
          <video src={a.url} poster={a.thumbnail_url ?? undefined} muted preload="metadata" className="w-full h-full object-cover" />
        ) : a.type === 'image' ? (
          <img src={a.url} alt={a.filename} loading="lazy" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-muted-foreground">
            <TypeIcon type={a.type} />
          </div>
        )}
        {/* Hover metadata overlay — prompt-or-filename, model, time */}
        <div className="absolute inset-x-0 bottom-0 bg-black/65 text-left px-1.5 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <p className="text-[10px] text-white leading-tight line-clamp-2">
            {a.prompt || a.filename}
          </p>
          <p className="text-[9px] text-white/70 font-mono truncate">
            {[a.model, formatRelativeTime(a.created_at)].filter(Boolean).join(' · ')}
          </p>
        </div>
      </button>
      {/* Quiet corner chips */}
      <span className="absolute top-1 left-1 bg-black/60 text-white text-[9px] px-1 py-0.5 rounded inline-flex items-center gap-0.5 pointer-events-none">
        <TypeIcon type={a.type} className="h-2.5 w-2.5" />
        {a.duration ? formatDuration(a.duration) : null}
      </span>
      <button
        onClick={(e) => { e.stopPropagation(); onToggleCompare(); }}
        className={cn(
          'absolute top-1 right-1 rounded px-1 py-0.5 text-[9px] transition-opacity',
          comparing
            ? 'bg-primary text-primary-foreground opacity-100'
            : 'bg-black/60 text-white opacity-0 group-hover:opacity-100',
        )}
        title={comparing ? 'Remove from compare' : 'Add to compare (2-up)'}
      >
        {comparing ? <Check className="h-2.5 w-2.5" /> : 'vs'}
      </button>
    </div>
  );
}

function MetaRows({ asset: a, campaignName }: { asset: AdAsset; campaignName: string | null }) {
  const rows: [string, string][] = [];
  if (a.model) rows.push(['Model', a.model]);
  if (a.generation_cost_credits != null) rows.push(['Cost', `${a.generation_cost_credits} credits`]);
  if (a.aspect_ratio) rows.push(['Aspect', a.aspect_ratio]);
  if (a.width && a.height) rows.push(['Size', `${a.width}×${a.height}`]);
  if (a.size_bytes) rows.push(['File', formatSize(a.size_bytes)]);
  if (a.duration) rows.push(['Duration', formatDuration(a.duration)]);
  if (campaignName) rows.push(['Campaign', campaignName]);
  rows.push(['Source', a.source === 'generated' ? 'AI-generated' : 'Uploaded']);
  if (a.created_at) rows.push(['Created', `${formatRelativeTime(a.created_at)} (${a.created_at} UTC)`]);
  return (
    <dl className="space-y-0.5">
      {rows.map(([k, v]) => (
        <div key={k} className="flex gap-2 text-[11px]">
          <dt className="w-16 shrink-0 text-muted-foreground">{k}</dt>
          <dd className="min-w-0 truncate" title={v}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function AssetDetailModal({ asset: a, campaignName, onClose, onUse, onDelete, onCompare, inCompare }: {
  asset: AdAsset;
  campaignName: string | null;
  onClose: () => void;
  onUse?: (asset: AdAsset) => void;
  onDelete: () => void;
  onCompare: () => void;
  inCompare: boolean;
}) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6"
      onClick={onClose}
    >
      <div
        className="bg-card border border-border rounded-lg max-w-4xl w-full overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
          <span className="text-sm font-medium truncate" title={a.filename}>{a.filename}</span>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex flex-col md:flex-row min-h-0 overflow-y-auto">
          <div className="md:flex-1 bg-black flex items-center justify-center min-w-0">
            {a.type === 'video' ? (
              <video src={a.url} poster={a.thumbnail_url ?? undefined} controls autoPlay className="w-full max-h-[60vh] object-contain" />
            ) : a.type === 'image' ? (
              <img src={a.url} alt={a.filename} className="w-full max-h-[60vh] object-contain" />
            ) : a.type === 'audio' ? (
              <audio src={a.url} controls className="w-full m-6" />
            ) : (
              <div className="p-8 text-center text-muted-foreground text-sm">Preview not supported</div>
            )}
          </div>
          <div className="md:w-72 shrink-0 border-t md:border-t-0 md:border-l border-border p-3 space-y-3">
            {a.prompt && (
              <div>
                <div className="label-section mb-1">Prompt</div>
                <p className="text-[11px] leading-snug text-foreground/90 max-h-36 overflow-y-auto whitespace-pre-wrap">
                  {a.prompt}
                </p>
              </div>
            )}
            {a.script && (
              <div>
                <div className="label-section mb-1">Script</div>
                <p className="text-[11px] italic leading-snug max-h-24 overflow-y-auto">"{a.script}"</p>
              </div>
            )}
            <div>
              <div className="label-section mb-1">Details</div>
              <MetaRows asset={a} campaignName={campaignName} />
            </div>
            <div className="space-y-1.5 pt-1">
              {onUse && (
                <Button size="sm" className="w-full gap-1.5" onClick={() => onUse(a)}>
                  <Check className="h-3.5 w-3.5" /> Use this asset
                </Button>
              )}
              <div className="flex items-center gap-1.5">
                <a
                  href={a.url}
                  download={a.filename}
                  className="flex-1 text-center text-xs px-2 py-1.5 rounded border border-border bg-secondary/40 hover:bg-secondary inline-flex items-center justify-center gap-1"
                >
                  <Download className="h-3 w-3" /> Download
                </a>
                <button
                  onClick={onCompare}
                  className="flex-1 text-xs px-2 py-1.5 rounded border border-border bg-secondary/40 hover:bg-secondary"
                >
                  {inCompare ? 'Remove compare' : 'Compare'}
                </button>
                <button
                  onClick={onDelete}
                  className="px-2 py-1.5 rounded border border-border bg-secondary/40 hover:bg-danger-soft hover:text-danger"
                  title="Delete permanently"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
