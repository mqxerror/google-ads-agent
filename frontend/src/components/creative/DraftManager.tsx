// DraftManager — save / load / rename / delete named drafts on the review step
// (Epic 15, story 15.2 · FR4.1/FR4.2). The server row is the source of truth;
// a second draft never destroys the first. Export / import (story 15.5) is
// layered on later in this same component.

import { useEffect, useState } from 'react';
import {
  Save, FolderOpen, Trash2, Pencil, Check, X, Loader2, AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useNamedDrafts, type DraftRecord } from './useNamedDrafts';
import { writeServerRef } from './crashCache';

interface DraftManagerProps<B> {
  accountId: string | null;
  campaignType: string;
  /** Current wizard bundle — what "Save" persists. */
  bundle: B;
  /** Replace the wizard's whole bundle with a loaded draft's bundle. */
  onLoad: (bundle: B) => void;
  /** The wizard's crash-cache localStorage key (story 15.4). When given, a
   * save/load records the server ref so the restore banner can tell a stale
   * cache from genuinely-newer local edits. */
  storageKey?: string;
}

export default function DraftManager<B extends object>({
  accountId, campaignType, bundle, onLoad, storageKey,
}: DraftManagerProps<B>) {
  const dm = useNamedDrafts<B>(accountId, campaignType);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Keep the name field in step with the currently loaded draft.
  useEffect(() => {
    const active = dm.drafts.find(d => d.id === dm.activeId);
    if (active) setName(active.name);
  }, [dm.activeId, dm.drafts]);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 3000);
    return () => clearTimeout(t);
  }, [flash]);

  const doSave = async () => {
    if (!name.trim()) { setFlash({ kind: 'err', msg: 'Name the draft first.' }); return; }
    setBusy('save');
    try {
      const existed = dm.drafts.some(d => d.name === name.trim());
      const row = await dm.save(name.trim(), bundle);
      if (storageKey) writeServerRef(storageKey, { id: row.id, updatedAt: row.updated_at, name: row.name });
      setFlash({ kind: 'ok', msg: existed ? `Updated “${name.trim()}”.` : `Saved “${name.trim()}”.` });
    } catch (e) {
      setFlash({ kind: 'err', msg: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(null); }
  };

  const doLoad = async (d: DraftRecord<B>) => {
    setBusy(d.id);
    try {
      const row = await dm.load(d.id);
      onLoad(row.bundle);
      if (storageKey) writeServerRef(storageKey, { id: row.id, updatedAt: row.updated_at, name: row.name });
      setName(row.name);
      setFlash({ kind: 'ok', msg: `Loaded “${row.name}”.` });
    } catch (e) {
      setFlash({ kind: 'err', msg: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(null); }
  };

  const doRename = async (id: string) => {
    if (!editName.trim()) { setEditingId(null); return; }
    setBusy(id);
    try {
      await dm.rename(id, editName.trim());
      setEditingId(null);
    } catch (e) {
      setFlash({ kind: 'err', msg: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(null); }
  };

  const doDelete = async (id: string) => {
    setBusy(id);
    try {
      await dm.remove(id);
      setConfirmDelete(null);
    } catch (e) {
      setFlash({ kind: 'err', msg: e instanceof Error ? e.message : String(e) });
    } finally { setBusy(null); }
  };

  return (
    <div className="border border-border rounded-lg bg-secondary/20 p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FolderOpen className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Named drafts</h3>
        <span className="text-[10px] text-muted-foreground">saved on the server · survive a restart</span>
      </div>

      {/* Save row */}
      <div className="flex items-center gap-2">
        <Input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. panama-q3-v1"
          className="flex-1 text-sm"
          onKeyDown={e => { if (e.key === 'Enter') void doSave(); }}
        />
        <Button size="sm" onClick={doSave} disabled={busy === 'save' || !accountId} className="gap-1.5 shrink-0">
          {busy === 'save' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
          Save draft
        </Button>
      </div>

      {flash && (
        <p className={cn('text-[11px] flex items-center gap-1.5',
          flash.kind === 'ok' ? 'text-green-600 dark:text-green-400' : 'text-red-500')}>
          {flash.kind === 'ok' ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}{flash.msg}
        </p>
      )}

      {/* List */}
      {dm.loading ? (
        <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
          <Loader2 className="h-3 w-3 animate-spin" /> Loading drafts…
        </p>
      ) : dm.drafts.length === 0 ? (
        <p className="text-[11px] text-muted-foreground italic">No saved drafts yet — name this bundle and click Save.</p>
      ) : (
        <ul className="space-y-1">
          {dm.drafts.map(d => (
            <li key={d.id}
              className={cn('flex items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                d.id === dm.activeId ? 'bg-primary/10 border border-primary/30' : 'hover:bg-secondary/50')}>
              {editingId === d.id ? (
                <>
                  <Input
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    className="flex-1 h-7 text-sm"
                    autoFocus
                    onKeyDown={e => { if (e.key === 'Enter') void doRename(d.id); if (e.key === 'Escape') setEditingId(null); }}
                  />
                  <button onClick={() => doRename(d.id)} className="p-1 hover:bg-secondary rounded text-green-600" aria-label="Confirm rename">
                    <Check className="h-3.5 w-3.5" />
                  </button>
                  <button onClick={() => setEditingId(null)} className="p-1 hover:bg-secondary rounded text-muted-foreground" aria-label="Cancel rename">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </>
              ) : (
                <>
                  <span className="flex-1 truncate font-medium">{d.name}</span>
                  {d.warnings.length > 0 && (
                    <span title={d.warnings.join('\n')}
                      className="text-[10px] text-amber-500 flex items-center gap-0.5 shrink-0">
                      <AlertTriangle className="h-3 w-3" />{d.warnings.length}
                    </span>
                  )}
                  <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">
                    {d.updated_at?.slice(0, 10)}
                  </span>
                  <button onClick={() => doLoad(d)} disabled={busy === d.id}
                    className="p-1 hover:bg-secondary rounded text-primary" aria-label="Load draft" title="Load into wizard">
                    {busy === d.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderOpen className="h-3.5 w-3.5" />}
                  </button>
                  <button onClick={() => { setEditingId(d.id); setEditName(d.name); }}
                    className="p-1 hover:bg-secondary rounded text-muted-foreground" aria-label="Rename draft" title="Rename">
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  {confirmDelete === d.id ? (
                    <button onClick={() => doDelete(d.id)}
                      className="text-[10px] text-red-500 px-1.5 py-0.5 rounded border border-red-500/40 hover:bg-red-500/10 shrink-0">
                      Confirm
                    </button>
                  ) : (
                    <button onClick={() => setConfirmDelete(d.id)}
                      className="p-1 hover:bg-secondary rounded text-muted-foreground hover:text-red-500" aria-label="Delete draft" title="Delete">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {dm.error && <p className="text-[11px] text-red-500">{dm.error}</p>}
    </div>
  );
}
