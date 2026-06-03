import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ScrollText, Search, Wrench, Sparkles, Wand2, Microscope, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';

interface ChangelogEntry {
  id: string;
  date: string;     // YYYY-MM-DD
  type: string;     // fix | feature | improvement | research | breaking
  title: string;
  tags: string[];
  body: string;
}

const TYPE_STYLE: Record<string, { label: string; bg: string; text: string; ring: string; Icon: typeof Wrench }> = {
  fix:         { label: 'Fix',         bg: 'bg-amber-500/15',  text: 'text-amber-300',  ring: 'ring-amber-500/30',  Icon: Wrench },
  feature:     { label: 'Feature',     bg: 'bg-pink-500/15',   text: 'text-pink-300',   ring: 'ring-pink-500/30',   Icon: Sparkles },
  improvement: { label: 'Improvement', bg: 'bg-blue-500/15',   text: 'text-blue-300',   ring: 'ring-blue-500/30',   Icon: Wand2 },
  research:    { label: 'Research',    bg: 'bg-purple-500/15', text: 'text-purple-300', ring: 'ring-purple-500/30', Icon: Microscope },
  breaking:    { label: 'Breaking',    bg: 'bg-red-500/15',    text: 'text-red-300',    ring: 'ring-red-500/30',    Icon: AlertTriangle },
};

function styleFor(type: string) {
  return TYPE_STYLE[type] ?? TYPE_STYLE.improvement;
}

function formatDate(iso: string): string {
  // Render YYYY-MM-DD as "Apr 22, 2026" without timezone games
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });
}

async function fetchChangelog(): Promise<ChangelogEntry[]> {
  const r = await fetch('/api/changelog?limit=200');
  if (!r.ok) return [];
  return r.json();
}

export default function ChangelogPage() {
  const { setShowChangelog } = useAppStore();
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [tagFilter, setTagFilter] = useState<string | null>(null);
  const [q, setQ] = useState('');

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['changelog'],
    queryFn: fetchChangelog,
    staleTime: 30_000,
  });

  // Apply client-side filters so changing them doesn't refetch
  const visible = useMemo(() => {
    return entries.filter(e => {
      if (typeFilter && e.type !== typeFilter) return false;
      if (tagFilter && !e.tags.includes(tagFilter)) return false;
      if (q) {
        const needle = q.toLowerCase();
        if (!e.title.toLowerCase().includes(needle) && !e.body.toLowerCase().includes(needle)) return false;
      }
      return true;
    });
  }, [entries, typeFilter, tagFilter, q]);

  // Group entries by month for the timeline
  const grouped = useMemo(() => {
    const groups = new Map<string, ChangelogEntry[]>();
    for (const e of visible) {
      const key = e.date.slice(0, 7); // YYYY-MM
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(e);
    }
    return Array.from(groups.entries());
  }, [visible]);

  const allTags = useMemo(() => {
    const tags = new Set<string>();
    for (const e of entries) for (const t of e.tags) tags.add(t);
    return Array.from(tags).sort();
  }, [entries]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of entries) c[e.type] = (c[e.type] ?? 0) + 1;
    return c;
  }, [entries]);

  return (
    <div className="p-6 max-w-[1100px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <ScrollText className="h-5 w-5 text-emerald-400" />
            Changelog
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            What's new, what's fixed, what's getting better. {entries.length} entr{entries.length === 1 ? 'y' : 'ies'}.
          </p>
        </div>
        <button
          onClick={() => setShowChangelog(false)}
          className="text-xs text-muted-foreground hover:text-foreground px-2 py-1"
        >
          Back to campaigns
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 mb-5">
        <div className="flex items-center gap-1 border border-border rounded-md p-0.5 bg-secondary/30">
          <button
            onClick={() => setTypeFilter(null)}
            className={cn('px-2.5 py-1 rounded text-xs', typeFilter === null ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}
          >
            All <span className="ml-1 text-muted-foreground/70">{entries.length}</span>
          </button>
          {(['feature', 'fix', 'improvement', 'research', 'breaking'] as const).map(t => {
            const s = styleFor(t);
            const count = counts[t] ?? 0;
            if (count === 0) return null;
            return (
              <button
                key={t}
                onClick={() => setTypeFilter(typeFilter === t ? null : t)}
                className={cn(
                  'px-2.5 py-1 rounded text-xs flex items-center gap-1',
                  typeFilter === t ? `${s.bg} ${s.text}` : 'text-muted-foreground hover:text-foreground'
                )}
              >
                <s.Icon className="h-3 w-3" />
                {s.label} <span className="ml-0.5 text-muted-foreground/70">{count}</span>
              </button>
            );
          })}
        </div>

        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search changelog..."
            className="w-full pl-7 pr-2 py-1.5 text-xs bg-secondary/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      </div>

      {/* Tag chips (only when there are tags) */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-6 text-[10px]">
          <span className="text-muted-foreground mr-1">Tags:</span>
          {allTags.map(tag => (
            <button
              key={tag}
              onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
              className={cn(
                'px-1.5 py-0.5 rounded border transition-colors',
                tagFilter === tag
                  ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40'
                  : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80'
              )}
            >
              {tag}
            </button>
          ))}
          {tagFilter && (
            <button onClick={() => setTagFilter(null)} className="text-muted-foreground hover:text-foreground ml-1">
              clear
            </button>
          )}
        </div>
      )}

      {/* Timeline */}
      {isLoading ? (
        <div className="text-sm text-muted-foreground py-12 text-center">Loading...</div>
      ) : visible.length === 0 ? (
        <div className="border border-dashed border-border rounded-lg py-16 text-center text-sm text-muted-foreground">
          {q || typeFilter || tagFilter ? 'No entries match these filters.' : 'No changelog entries yet.'}
        </div>
      ) : (
        <div className="relative">
          {/* Vertical timeline line */}
          <div className="absolute left-3 top-2 bottom-2 w-px bg-border" aria-hidden />

          {grouped.map(([month, items]) => (
            <div key={month} className="mb-6">
              <div className="flex items-center gap-3 mb-3 ml-8">
                <h2 className="text-sm font-semibold text-foreground">{formatMonth(month)}</h2>
                <span className="text-[10px] text-muted-foreground">{items.length} update{items.length !== 1 ? 's' : ''}</span>
              </div>
              <div className="space-y-3">
                {items.map(entry => {
                  const s = styleFor(entry.type);
                  return (
                    <div key={entry.id} className="relative pl-10">
                      {/* Timeline dot */}
                      <div className={cn(
                        'absolute left-1.5 top-3 w-3 h-3 rounded-full ring-2',
                        s.bg, s.ring
                      )} aria-hidden />

                      <div className="bg-card border border-border rounded-lg p-4">
                        <div className="flex items-start justify-between gap-3 mb-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide', s.bg, s.text)}>
                              <s.Icon className="h-2.5 w-2.5" />
                              {s.label}
                            </span>
                            <h3 className="text-sm font-semibold">{entry.title}</h3>
                          </div>
                          <span className="text-[10px] text-muted-foreground tabular-nums shrink-0 mt-0.5">
                            {formatDate(entry.date)}
                          </span>
                        </div>

                        {entry.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-2">
                            {entry.tags.map(tag => (
                              <button
                                key={tag}
                                onClick={() => setTagFilter(tag)}
                                className="text-[9px] px-1.5 py-0.5 rounded bg-secondary/60 text-muted-foreground hover:text-foreground"
                              >
                                #{tag}
                              </button>
                            ))}
                          </div>
                        )}

                        <div className="prose prose-sm prose-invert max-w-none
                          [&_p]:my-1.5 [&_p]:text-sm
                          [&_ul]:my-1.5 [&_ul]:pl-4 [&_ul]:text-sm
                          [&_li]:my-0.5
                          [&_strong]:text-foreground [&_strong]:font-semibold
                          [&_code]:text-xs [&_code]:bg-background/50 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded
                          [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mt-3 [&_h2]:mb-2
                          [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:mt-2 [&_h3]:mb-1
                        ">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {entry.body}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatMonth(yyyymm: string): string {
  const [y, m] = yyyymm.split('-').map(Number);
  if (!y || !m) return yyyymm;
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' });
}
