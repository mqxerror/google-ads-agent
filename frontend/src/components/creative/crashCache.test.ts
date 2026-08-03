// Story 15.4 — crash-cache helpers pinned.
//
// The Google-ref stripping (isLocalAssetRef) MUST behave exactly as the inline
// wizard rehydrate did (FR4.4 "behavior unchanged"), and the restore-banner
// predicate is unit-tested here so the local-vs-server decision has no DOM
// dependency.

import { beforeEach, describe, it, expect } from 'vitest';
import {
  isLocalAssetRef,
  shouldOfferRestore,
  touchCacheTs,
  readCacheTs,
  writeServerRef,
  readServerRef,
  clearCacheMeta,
} from './crashCache';

// Minimal localStorage stub for the round-trip helpers (node env has none).
class LS {
  private m = new Map<string, string>();
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, v); }
  removeItem(k: string) { this.m.delete(k); }
  clear() { this.m.clear(); }
}

describe('isLocalAssetRef — Google-ref stripping (behavior pinned, FR4.4)', () => {
  it('keeps local library UUIDs', () => {
    expect(isLocalAssetRef('a1b2c3d4-uuid')).toBe(true);
    expect(isLocalAssetRef('gen-9f8e7d')).toBe(true);
  });
  it('drops bare numeric asset ids', () => {
    expect(isLocalAssetRef('123456789')).toBe(false);
  });
  it('drops Google resource names (contain a slash)', () => {
    expect(isLocalAssetRef('customers/123/assets/456')).toBe(false);
  });
  it('drops empty', () => {
    expect(isLocalAssetRef('')).toBe(false);
  });
});

describe('shouldOfferRestore', () => {
  const server = '2026-08-03T10:00:00Z';
  const older = Date.parse(server) - 5000;
  const newer = Date.parse(server) + 5000;

  it('offers when local is newer AND bundles differ', () => {
    expect(shouldOfferRestore(newer, server, true)).toBe(true);
  });
  it('does not offer when bundles are identical', () => {
    expect(shouldOfferRestore(newer, server, false)).toBe(false);
  });
  it('does not offer when local is older or equal', () => {
    expect(shouldOfferRestore(older, server, true)).toBe(false);
    expect(shouldOfferRestore(Date.parse(server), server, true)).toBe(false);
  });
  it('does not offer without a local ts or server timestamp', () => {
    expect(shouldOfferRestore(null, server, true)).toBe(false);
    expect(shouldOfferRestore(newer, null, true)).toBe(false);
    expect(shouldOfferRestore(newer, 'not-a-date', true)).toBe(false);
  });
});

describe('cache ts + server ref round-trip', () => {
  beforeEach(() => {
    (globalThis as unknown as { localStorage: LS }).localStorage = new LS();
  });

  it('touch/read the crash-cache timestamp', () => {
    touchCacheTs('k', 1234);
    expect(readCacheTs('k')).toBe(1234);
  });

  it('writeServerRef resets the ts to the server updated_at so a fresh load never flags', () => {
    const updatedAt = '2026-08-03T10:00:00Z';
    writeServerRef('k', { id: 'd1', updatedAt, name: 'panama' });
    const ref = readServerRef('k');
    expect(ref?.id).toBe('d1');
    // ts now equals the server time → not "newer local"
    expect(readCacheTs('k')).toBe(Date.parse(updatedAt));
    expect(shouldOfferRestore(readCacheTs('k'), updatedAt, true)).toBe(false);
  });

  it('a later keystroke makes local newer → banner would offer', () => {
    const updatedAt = '2026-08-03T10:00:00Z';
    writeServerRef('k', { id: 'd1', updatedAt });
    touchCacheTs('k', Date.parse(updatedAt) + 1000); // edited after saving
    expect(shouldOfferRestore(readCacheTs('k'), updatedAt, true)).toBe(true);
  });

  it('clearCacheMeta removes the ts + server ref', () => {
    writeServerRef('k', { id: 'd1', updatedAt: '2026-08-03T10:00:00Z' });
    clearCacheMeta('k');
    expect(readCacheTs('k')).toBeNull();
    expect(readServerRef('k')).toBeNull();
  });
});
