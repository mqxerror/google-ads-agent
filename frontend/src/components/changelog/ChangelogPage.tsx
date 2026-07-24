import { useMemo, useState, type ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  History, User, Bot, CalendarClock, Globe, Undo2, RotateCcw,
  ShieldCheck, ChevronDown, ChevronRight, Loader2, AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { fetchCampaigns } from '@/lib/api';

// ── Types (mirror app/services/change_log.build_feed) ────────────────────────
interface ChangeEntry {
  id: number | string;
  ts: string | null;
  source: 'app' | 'external' | 'revert';
  actor_type: string;               // app-user | chat-specialist | scheduler-plan | api | external | revert
  actor_detail: string | null;
  account_id: string | null;
  campaign_id: string | null;
  resource: string | null;
  action: string | null;
  field: string | null;
  summary: string | null;
  before_value: string | null;
  after_value: string | null;
  revertible: boolean;
  revert_reason: string | null;
  reverts: number | null;
  reverted_by: number | null;
  reverted_at: string | null;
  batch_id: string | null;
  batch_count: number;
  members?: number[];
}
interface Feed { entries: ChangeEntry[]; history_begins: string | null }

// ── Actor presentation ───────────────────────────────────────────────────────
const ACTORS: Record<string, { label: string; Icon: typeof User; tone: string }> = {
  'app-user':        { label: 'You',       Icon: User,          tone: 'bg-primary/10 text-primary' },
  'chat-specialist': { label: 'Team',      Icon: Bot,           tone: 'bg-secondary text-foreground' },
  'scheduler-plan':  { label: 'Scheduler', Icon: CalendarClock, tone: 'bg-secondary text-muted-foreground' },
  'external':        { label: 'Outside app', Icon: Globe,       tone: 'bg-muted text-muted-foreground' },
  'revert':          { label: 'Revert',    Icon: Undo2,         tone: 'bg-muted text-muted-foreground' },
  'api':             { label: 'API',       Icon: Bot,           tone: 'bg-secondary text-muted-foreground' },
};
function actorOf(t: string) { return ACTORS[t] ?? ACTORS['api']; }

// The actor-filter chip set, in display order.
const ACTOR_FILTERS: { key: string; label: string }[] = [
  { key: 'app-user', label: 'You' },
  { key: 'chat-specialist', label: 'Team' },
  { key: 'scheduler-plan', label: 'Scheduler' },
  { key: 'external', label: 'Outside app' },
];

function fmtTime(iso: string | null): string {
  if (!iso) return '';
  // sqlite datetime('now') is UTC "YYYY-MM-DD HH:MM:SS"
  const d = new Date(iso.replace(' ', 'T') + 'Z');
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}
function fmtDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso.replace(' ', 'T') + 'Z');
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
}

async function fetchFeed(accountId: string, campaignId: string | null, actor: string | null): Promise<Feed> {
  const p = new URLSearchParams();
  if (accountId) p.set('account_id', accountId);
  if (campaignId) p.set('campaign_id', campaignId);
  if (actor) p.set('actor', actor);
  const r = await fetch(`/api/changelog/changes?${p.toString()}`);
  if (!r.ok) return { entries: [], history_begins: null };
  return r.json();
}

export default function ChangelogPage() {
  const { selectedAccountId, setShowChangelog } = useAppStore();
  const qc = useQueryClient();
  const [campaignFilter, setCampaignFilter] = useState<string | null>(null);
  const [actorFilter, setActorFilter] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<ChangeEntry | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [banner, setBanner] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  const accountId = selectedAccountId || '';

  const { data: feed, isLoading } = useQuery({
    queryKey: ['change-feed', accountId, campaignFilter, actorFilter],
    queryFn: () => fetchFeed(accountId, campaignFilter, actorFilter),
    enabled: !!accountId,
    staleTime: 15_000,
  });

  const { data: campaigns = [] } = useQuery({
    queryKey: ['campaigns', accountId],
    queryFn: () => fetchCampaigns(accountId),
    enabled: !!accountId,
    staleTime: 60_000,
  });
  const campaignName = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of campaigns) m.set(String(c.id), c.name);
    return m;
  }, [campaigns]);

  // Campaign chips: only campaigns that actually appear in the feed.
  const campaignChips = useMemo(() => {
    const ids = new Set<string>();
    for (const e of feed?.entries ?? []) if (e.campaign_id) ids.add(String(e.campaign_id));
    return Array.from(ids).map((id) => ({ id, name: campaignName.get(id) || `Campaign ${id}` }));
  }, [feed, campaignName]);

  const revert = useMutation({
    mutationFn: async (id: number | string) => {
      const r = await fetch(`/api/changelog/${id}/revert`, { method: 'POST' });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || `Revert failed (${r.status})`);
      return body as { summary: string; verified: boolean; reverted_ids: number[] };
    },
    onSuccess: (res) => {
      setConfirming(null);
      setBanner({
        kind: 'ok',
        text: res.verified
          ? `${res.summary}. Verified live.`
          : `${res.summary}. Applied (live verification pending).`,
      });
      qc.invalidateQueries({ queryKey: ['change-feed'] });
    },
    onError: (e: Error) => {
      setConfirming(null);
      setBanner({ kind: 'err', text: e.message });
    },
  });

  const entries = feed?.entries ?? [];

  return (
    <div className="p-6 max-w-[1080px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2 text-foreground">
            <History className="h-5 w-5 text-primary" />
            Changelog
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Every account change, who made it, and a one click undo.
          </p>
        </div>
        <button
          onClick={() => setShowChangelog(false)}
          className="text-xs text-muted-foreground hover:text-foreground px-2 py-1"
        >
          Back to campaigns
        </button>
      </div>

      {/* Trust line */}
      <div className="flex items-center gap-2 rounded-lg border border-border bg-primary/5 px-3 py-2 mb-5">
        <ShieldCheck className="h-4 w-4 text-primary shrink-0" />
        <span className="text-xs text-foreground">
          Every write is reviewed. Every write is reversible.
        </span>
      </div>

      {/* Banner (revert result) */}
      {banner && (
        <div
          className={cn(
            'flex items-center justify-between gap-2 rounded-md border px-3 py-2 mb-4 text-xs',
            banner.kind === 'ok'
              ? 'border-border bg-secondary text-foreground'
              : 'border-destructive/40 bg-destructive/10 text-destructive',
          )}
        >
          <span className="flex items-center gap-2">
            {banner.kind === 'err' && <AlertCircle className="h-3.5 w-3.5" />}
            {banner.text}
          </span>
          <button onClick={() => setBanner(null)} className="text-muted-foreground hover:text-foreground">
            Dismiss
          </button>
        </div>
      )}

      {!accountId ? (
        <div className="border border-dashed border-border rounded-lg py-16 text-center text-sm text-muted-foreground">
          Select an account to see its change history.
        </div>
      ) : (
        <>
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mb-4">
            {/* Actor filter */}
            <div className="flex items-center gap-1 flex-wrap">
              <span className="text-[11px] uppercase tracking-wide text-muted-foreground mr-1">Who</span>
              <Chip active={actorFilter === null} onClick={() => setActorFilter(null)}>All</Chip>
              {ACTOR_FILTERS.map((a) => (
                <Chip key={a.key} active={actorFilter === a.key} onClick={() => setActorFilter(actorFilter === a.key ? null : a.key)}>
                  {a.label}
                </Chip>
              ))}
            </div>
            {/* Campaign filter */}
            {campaignChips.length > 0 && (
              <div className="flex items-center gap-1 flex-wrap">
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground mr-1">Campaign</span>
                <Chip active={campaignFilter === null} onClick={() => setCampaignFilter(null)}>All</Chip>
                {campaignChips.map((c) => (
                  <Chip key={c.id} active={campaignFilter === c.id} onClick={() => setCampaignFilter(campaignFilter === c.id ? null : c.id)}>
                    {c.name}
                  </Chip>
                ))}
              </div>
            )}
          </div>

          {/* Feed */}
          {isLoading ? (
            <div className="text-sm text-muted-foreground py-12 text-center">Loading changes...</div>
          ) : entries.length === 0 ? (
            <div className="border border-dashed border-border rounded-lg py-16 text-center text-sm text-muted-foreground">
              No changes recorded yet. New writes will appear here as they happen.
            </div>
          ) : (
            <div className="border border-border rounded-lg overflow-hidden bg-card">
              {/* Column header */}
              <div className="grid grid-cols-[110px_120px_1fr_92px] gap-3 px-4 py-2 border-b border-border bg-secondary text-[11px] uppercase tracking-wide text-muted-foreground">
                <span>When</span>
                <span>Who</span>
                <span>Change</span>
                <span className="text-right">Undo</span>
              </div>
              <ul>
                {entries.map((e) => {
                  const key = String(e.id);
                  const isExpanded = expanded.has(key);
                  const a = actorOf(e.actor_type);
                  const camp = e.campaign_id ? (campaignName.get(String(e.campaign_id)) || `Campaign ${e.campaign_id}`) : null;
                  return (
                    <li key={key} className={cn(
                      'grid grid-cols-[110px_120px_1fr_92px] gap-3 px-4 py-3 border-b border-border last:border-b-0 items-start',
                      e.reverted_at && 'opacity-60',
                    )}>
                      {/* When */}
                      <span className="text-xs text-muted-foreground tabular-nums pt-0.5">{fmtTime(e.ts)}</span>

                      {/* Who */}
                      <span className="min-w-0">
                        <span className={cn('inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium', a.tone)}>
                          <a.Icon className="h-3 w-3" />
                          {a.label}
                        </span>
                        {e.actor_detail && (
                          <span className="block truncate text-[10px] text-muted-foreground mt-0.5" title={e.actor_detail}>
                            {e.actor_detail}
                          </span>
                        )}
                      </span>

                      {/* Change */}
                      <span className="min-w-0">
                        <span className="text-sm text-foreground">{e.summary}</span>
                        {camp && <span className="text-[11px] text-muted-foreground"> · {camp}</span>}
                        {e.batch_count > 1 && (e.members?.length ?? 0) > 0 && (
                          <button
                            onClick={() => {
                              setExpanded((s) => {
                                const n = new Set(s);
                                n.has(key) ? n.delete(key) : n.add(key);
                                return n;
                              });
                            }}
                            className="ml-2 inline-flex items-center gap-0.5 text-[11px] text-primary hover:underline"
                          >
                            {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                            {e.batch_count} items
                          </button>
                        )}
                        {e.reverted_at && (
                          <span className="block text-[11px] text-muted-foreground mt-0.5">
                            Reverted {fmtTime(e.reverted_at)}
                          </span>
                        )}
                        {isExpanded && (
                          <span className="block text-[11px] text-muted-foreground mt-1">
                            This batch of {e.batch_count} changes reverts together.
                          </span>
                        )}
                      </span>

                      {/* Undo */}
                      <span className="text-right">
                        {e.reverted_at ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                            <Undo2 className="h-3 w-3" /> Reverted
                          </span>
                        ) : e.revertible && e.source === 'app' ? (
                          <button
                            onClick={() => setConfirming(e)}
                            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-foreground hover:bg-secondary transition-colors"
                          >
                            <RotateCcw className="h-3 w-3" /> Revert
                          </button>
                        ) : (
                          <span
                            className="text-[10px] text-muted-foreground cursor-help"
                            title={e.revert_reason || 'Not reversible'}
                          >
                            {e.actor_type === 'revert' ? 'undo of a change' : 'not reversible'}
                          </span>
                        )}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {/* Honest history-start note */}
          {feed?.history_begins && (
            <p className="text-[11px] text-muted-foreground text-center mt-4">
              History begins {fmtDate(feed.history_begins)}. Changes made before then are not recorded here.
            </p>
          )}
        </>
      )}

      {/* Confirm dialog */}
      {confirming && (
        <ConfirmRevert
          entry={confirming}
          busy={revert.isPending}
          onCancel={() => setConfirming(null)}
          onConfirm={() => revert.mutate(confirming.id)}
        />
      )}
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'px-2 py-0.5 rounded text-xs border transition-colors',
        active
          ? 'bg-primary/10 text-primary border-primary/30'
          : 'border-border text-muted-foreground hover:text-foreground hover:border-border',
      )}
    >
      {children}
    </button>
  );
}

function restoreDetail(e: ChangeEntry): string {
  const parse = (v: string | null): string | null => {
    if (v == null) return null;
    try {
      const j = JSON.parse(v);
      if (Array.isArray(j)) return j.join(', ');
      return String(j);
    } catch {
      return v;
    }
  };
  if (e.action === 'add') return `Remove what was added (${e.summary}).`;
  const before = parse(e.before_value);
  if (before != null) return `Restore the previous value: ${before}.`;
  return 'Restore the previous state.';
}

function ConfirmRevert({
  entry, busy, onCancel, onConfirm,
}: { entry: ChangeEntry; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/20 p-4" onClick={onCancel}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-lg"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
          <RotateCcw className="h-4 w-4 text-primary" />
          Revert this change?
        </h2>
        <p className="text-sm text-muted-foreground mt-2">{entry.summary}</p>
        <div className="mt-3 rounded-md border border-border bg-secondary px-3 py-2 text-xs text-foreground">
          {restoreDetail(entry)}
          {entry.batch_count > 1 && (
            <span className="block mt-1 text-muted-foreground">
              This reverts all {entry.batch_count} changes in the batch.
            </span>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground mt-2">
          The revert runs the inverse operation live and is itself recorded in this log.
        </p>
        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onCancel}
            disabled={busy}
            className="px-3 py-1.5 rounded-md text-sm text-foreground border border-border hover:bg-secondary disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="px-3 py-1.5 rounded-md text-sm bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {busy ? 'Reverting...' : 'Revert it'}
          </button>
        </div>
      </div>
    </div>
  );
}
