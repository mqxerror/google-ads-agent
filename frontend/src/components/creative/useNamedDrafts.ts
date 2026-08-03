// Named drafts client (Epic 15, story 15.2 · FR4.1/FR4.2/D4).
//
// Thin client over the V27-backed CRUD (`/api/accounts/{id}/creative-drafts`).
// The SERVER row is the source of truth for a named draft; the wizard's
// localStorage is only a crash cache (story 15.4). Generic over the wizard's
// bundle type so PMax and Demand Gen share one hook + one <DraftManager>.
//
// Pure API functions are exported alongside the hook so the request/response
// shapes stay unit-testable without a DOM.

import { useCallback, useEffect, useState } from 'react';

export interface DraftRecord<B = Record<string, unknown>> {
  id: string;
  account_id: string;
  campaign_type: string;
  name: string;
  bundle: B;
  created_at: string;
  updated_at: string;
  /** Registry re-validation of the saved bundle — advisory, never blocks. */
  warnings: string[];
}

const base = (accountId: string) => `/api/accounts/${accountId}/creative-drafts`;

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { /* non-JSON error */ }
  if (!res.ok) {
    const detail = (body as { detail?: { message?: string } } | null)?.detail;
    throw new DraftError(detail?.message || `HTTP ${res.status}`, res.status);
  }
  return body as T;
}

export class DraftError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'DraftError';
    this.status = status;
  }
}

export async function apiListDrafts<B>(accountId: string, campaignType: string): Promise<DraftRecord<B>[]> {
  const qs = new URLSearchParams({ campaign_type: campaignType });
  const res = await fetch(`${base(accountId)}?${qs}`);
  return jsonOrThrow<DraftRecord<B>[]>(res);
}

export async function apiCreateDraft<B>(
  accountId: string, campaignType: string, name: string, bundle: B,
): Promise<DraftRecord<B>> {
  const res = await fetch(base(accountId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, campaign_type: campaignType, bundle }),
  });
  return jsonOrThrow<DraftRecord<B>>(res);
}

export async function apiUpdateDraft<B>(
  accountId: string, draftId: string, patch: { name?: string; bundle?: B },
): Promise<DraftRecord<B>> {
  const res = await fetch(`${base(accountId)}/${draftId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  return jsonOrThrow<DraftRecord<B>>(res);
}

export async function apiGetDraft<B>(accountId: string, draftId: string): Promise<DraftRecord<B>> {
  return jsonOrThrow<DraftRecord<B>>(await fetch(`${base(accountId)}/${draftId}`));
}

export async function apiDeleteDraft(accountId: string, draftId: string): Promise<void> {
  await jsonOrThrow<{ deleted: string }>(
    await fetch(`${base(accountId)}/${draftId}`, { method: 'DELETE' }),
  );
}

export interface UseNamedDrafts<B> {
  drafts: DraftRecord<B>[];
  loading: boolean;
  error: string | null;
  /** id of the draft currently loaded into the wizard (drives update-in-place). */
  activeId: string | null;
  setActiveId: (id: string | null) => void;
  refresh: () => Promise<void>;
  /** Create a new named draft, OR update the same-named existing one (upsert by
   * name) — so "Save" never surprises the operator with a 409. Returns the row. */
  save: (name: string, bundle: B) => Promise<DraftRecord<B>>;
  load: (id: string) => Promise<DraftRecord<B>>;
  rename: (id: string, name: string) => Promise<DraftRecord<B>>;
  remove: (id: string) => Promise<void>;
}

export function useNamedDrafts<B>(accountId: string | null, campaignType: string): UseNamedDrafts<B> {
  const [drafts, setDrafts] = useState<DraftRecord<B>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!accountId) return;
    setLoading(true);
    setError(null);
    try {
      setDrafts(await apiListDrafts<B>(accountId, campaignType));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [accountId, campaignType]);

  useEffect(() => { void refresh(); }, [refresh]);

  const save = useCallback(async (name: string, bundle: B): Promise<DraftRecord<B>> => {
    if (!accountId) throw new DraftError('no account selected', 0);
    const existing = drafts.find(d => d.name === name.trim());
    const row = existing
      ? await apiUpdateDraft<B>(accountId, existing.id, { bundle })
      : await apiCreateDraft<B>(accountId, campaignType, name.trim(), bundle);
    setActiveId(row.id);
    await refresh();
    return row;
  }, [accountId, campaignType, drafts, refresh]);

  const load = useCallback(async (id: string): Promise<DraftRecord<B>> => {
    if (!accountId) throw new DraftError('no account selected', 0);
    const row = await apiGetDraft<B>(accountId, id);
    setActiveId(id);
    return row;
  }, [accountId]);

  const rename = useCallback(async (id: string, name: string): Promise<DraftRecord<B>> => {
    if (!accountId) throw new DraftError('no account selected', 0);
    const row = await apiUpdateDraft<B>(accountId, id, { name });
    await refresh();
    return row;
  }, [accountId, refresh]);

  const remove = useCallback(async (id: string): Promise<void> => {
    if (!accountId) return;
    await apiDeleteDraft(accountId, id);
    setActiveId(prev => (prev === id ? null : prev));
    await refresh();
  }, [accountId, refresh]);

  return { drafts, loading, error, activeId, setActiveId, refresh, save, load, rename, remove };
}
