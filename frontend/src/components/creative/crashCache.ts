// Crash-cache helpers (Epic 15, story 15.4 · FR4.4).
//
// The wizards' per-keystroke localStorage write-through is DEMOTED to a crash
// cache: the SERVER row (named drafts, story 15.2) is the source of truth. This
// module holds the pure, unit-testable pieces so behavior is pinned:
//
//  - isLocalAssetRef  — the Google-ref stripping rehydrate applies (was inline
//    in each wizard); a Google resource name / bare numeric id bypasses the
//    server-side aspect crop on resubmit, so it is dropped from the cache.
//  - crash-cache timestamp read/write/clear (a `.ts` sidecar key).
//  - a small "server ref" marker (which named draft the local cache descends
//    from) so we can tell a stale cache from genuinely-newer local edits.
//  - shouldOfferRestore — the restore-banner predicate.

/** A LOCAL library id (upload / generate / library UUID) — NOT a Google
 * resource name (`customers/.../assets/...`, contains '/') and NOT a bare
 * numeric asset id. Only local refs survive a rehydrate; Google refs bypass the
 * server's aspect crop on resubmit (the live ASPECT_RATIO_NOT_ALLOWED), so they
 * are stripped. Pinned by a test — behavior must not change (FR4.4). */
export function isLocalAssetRef(ref: string): boolean {
  return !!ref && !/^\d+$/.test(ref) && !ref.includes('/');
}

const tsKey = (key: string) => `${key}.ts`;
const refKey = (key: string) => `${key}.serverRef`;

export interface ServerRef {
  id: string;
  /** ISO updated_at of the server draft the local cache descends from. */
  updatedAt: string;
  name?: string;
}

function lsGet(k: string): string | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(k);
  } catch { return null; }
}
function lsSet(k: string, v: string): void {
  try { if (typeof localStorage !== 'undefined') localStorage.setItem(k, v); } catch { /* quota */ }
}
function lsDel(k: string): void {
  try { if (typeof localStorage !== 'undefined') localStorage.removeItem(k); } catch { /* noop */ }
}

/** Stamp the crash cache with "now" (called on every keystroke write-through). */
export function touchCacheTs(key: string, now: number = Date.now()): void {
  lsSet(tsKey(key), String(now));
}

export function readCacheTs(key: string): number | null {
  const raw = lsGet(tsKey(key));
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

/** Clear the crash cache AND its sidecar metadata (choosing "server" discards
 * the local cache). The bundle key itself is cleared by the caller's own
 * STORAGE_KEY remove; this clears the ts + server ref. */
export function clearCacheMeta(key: string): void {
  lsDel(tsKey(key));
  lsDel(refKey(key));
}

export function readServerRef(key: string): ServerRef | null {
  const raw = lsGet(refKey(key));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ServerRef;
    return parsed && parsed.id && parsed.updatedAt ? parsed : null;
  } catch { return null; }
}

/** Record which named draft the local cache now descends from (on load/save) and
 * reset the crash-cache timestamp to match it, so a fresh load is never flagged
 * as "newer local edits". */
export function writeServerRef(key: string, ref: ServerRef): void {
  lsSet(refKey(key), JSON.stringify(ref));
  const serverMs = Date.parse(ref.updatedAt);
  touchCacheTs(key, Number.isNaN(serverMs) ? Date.now() : serverMs);
}

/** Restore-banner predicate: offer local-vs-server when the crash cache is
 * NEWER than the server draft it descends from AND the two actually differ.
 * `differs` is the caller's deep-inequality of local bundle vs server bundle. */
export function shouldOfferRestore(
  localTs: number | null,
  serverUpdatedAt: string | null | undefined,
  differs: boolean,
): boolean {
  if (!differs || localTs == null || !serverUpdatedAt) return false;
  const serverMs = Date.parse(serverUpdatedAt);
  if (Number.isNaN(serverMs)) return false;
  return localTs > serverMs;
}
