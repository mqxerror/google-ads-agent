// ReferencePhotosPicker (Epic 16, story 16.5) — the operator attaches their OWN
// hotel/property photos from the ad_assets library so image generation anchors to
// real subjects. Extracted from DemandGenWizard's StepBrief into ONE shared,
// self-contained component (its own library grid — no dependency on either
// wizard's local LibraryPicker) so BOTH wizards consume it (FR1.12). The picked
// ids ride PMax's baseContext as referenceAssetIds (asset-anchored generation).

import { useEffect, useState } from 'react';
import { FolderOpen, Image as ImageIcon, X, Search, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface LibAsset { id: string; filename: string; url: string; thumbnail_url?: string | null }

export default function ReferencePhotosPicker({
  accountId, value, onChange, maxItems = 6,
}: {
  accountId: string;
  value: string[];
  onChange: (ids: string[]) => void;
  maxItems?: number;
}) {
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState<LibAsset[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [meta, setMeta] = useState<Record<string, LibAsset>>({});

  useEffect(() => {
    let cancelled = false;
    const qs = new URLSearchParams({ asset_type: 'image', limit: '200' });
    if (accountId) qs.set('account_id', accountId);
    fetch(`/api/assets?${qs}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((rows: LibAsset[]) => {
        if (cancelled) return;
        setAssets(rows);
        setMeta(prev => {
          const next = { ...prev };
          rows.forEach(r => { next[r.id] = r; });
          return next;
        });
      })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); });
    return () => { cancelled = true; };
  }, [accountId]);

  const toggle = (id: string) => {
    onChange(value.includes(id) ? value.filter(x => x !== id) : (value.length < maxItems ? [...value, id] : value));
  };

  const q = search.trim().toLowerCase();
  const visible = (assets || []).filter(a => !q || a.filename.toLowerCase().includes(q));
  const atMax = value.length >= maxItems;

  return (
    <div className="border border-border rounded-md p-3 bg-secondary/20 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <ImageIcon className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
          <div>
            <span className="text-xs font-medium">Reference photos (optional)</span>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Attach your OWN hotel / property photos from the library. Image generation anchors to
              these real subjects instead of inventing a generic scene.
            </p>
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen(v => !v)} className="gap-1.5 shrink-0">
          <FolderOpen className="h-3.5 w-3.5" />
          {value.length ? `${value.length} attached` : 'Attach'}
        </Button>
      </div>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map(id => {
            const m = meta[id];
            return (
              <span key={id} className="relative inline-flex">
                {m ? (
                  <img src={m.thumbnail_url || m.url} alt={m.filename} className="h-12 w-12 rounded border border-border object-cover" loading="lazy" />
                ) : (
                  <span className="h-12 w-12 rounded border border-border bg-secondary/40 flex items-center justify-center">
                    <ImageIcon className="h-4 w-4 text-muted-foreground" />
                  </span>
                )}
                <button
                  type="button" onClick={() => toggle(id)}
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

      {open && (
        <div className="mt-1 border border-border rounded-md bg-background/60 p-2">
          <div className="flex items-center gap-2 mb-2">
            <p className="text-[10px] text-muted-foreground flex-1">
              {value.length}/{maxItems} selected{atMax ? ' (max)' : ''}.
            </p>
            <div className="relative">
              <Search className="h-3 w-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter by filename" className="h-7 w-40 pl-6 text-xs" />
            </div>
            <button onClick={() => setOpen(false)} className="p-1 hover:bg-secondary rounded text-muted-foreground" aria-label="Close library">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          {error ? (
            <p className="text-[10px] text-red-500 flex items-center gap-1"><AlertCircle className="h-3 w-3" /> {error}</p>
          ) : assets === null ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground py-3"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading library…</div>
          ) : visible.length === 0 ? (
            <p className="text-xs text-muted-foreground py-3">{q ? 'No images match.' : 'No images in the library yet.'}</p>
          ) : (
            <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-1.5 max-h-48 overflow-y-auto">
              {visible.map(a => {
                const selected = value.includes(a.id);
                const disabled = !selected && atMax;
                return (
                  <button
                    key={a.id} type="button" onClick={() => toggle(a.id)} disabled={disabled} title={a.filename}
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
      )}
    </div>
  );
}
