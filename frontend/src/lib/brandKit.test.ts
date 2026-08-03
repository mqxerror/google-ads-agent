// Story 18.5 — one-click search-theme append (FR5.3). Pure logic: idempotent,
// respects the registry ≤max cap, truncates to the per-theme char cap.

import { describe, it, expect } from 'vitest';
import { appendSearchTheme, hasTheme } from '@/lib/brandKit';

const CAP = { maxItems: 25, maxChars: 80 };

describe('appendSearchTheme (FR5.3)', () => {
  it('appends a new theme', () => {
    expect(appendSearchTheme([], 'HNW investors', CAP)).toEqual(['HNW investors']);
  });

  it('is idempotent — no duplicate on a second click', () => {
    const once = appendSearchTheme([], 'HNW investors', CAP);
    const twice = appendSearchTheme(once, 'HNW investors', CAP);
    expect(twice).toEqual(['HNW investors']);
  });

  it('idempotency is case-insensitive', () => {
    const themes = ['HNW Investors'];
    expect(appendSearchTheme(themes, 'hnw investors', CAP)).toEqual(themes);
  });

  it('respects the registry max-items cap', () => {
    const full = Array.from({ length: 25 }, (_, i) => `theme ${i}`);
    expect(appendSearchTheme(full, 'one more', CAP)).toEqual(full);   // at cap → no-op
    expect(appendSearchTheme(full, 'one more', CAP).length).toBe(25);
  });

  it('truncates to the per-theme char cap', () => {
    const long = 'x'.repeat(200);
    const out = appendSearchTheme([], long, { maxItems: 25, maxChars: 80 });
    expect(out[0].length).toBe(80);
  });

  it('drops empty placeholder rows and ignores blank input', () => {
    expect(appendSearchTheme([''], '', CAP)).toEqual(['']);           // blank input → no-op
    expect(appendSearchTheme([''], 'families', CAP)).toEqual(['families']); // placeholder dropped
  });

  it('counts only non-empty themes against the cap', () => {
    const withBlanks = ['a', '', 'b', ''];
    const out = appendSearchTheme(withBlanks, 'c', CAP);
    expect(out).toEqual(['a', 'b', 'c']);   // blanks dropped, real count = 2 < cap
  });
});

describe('hasTheme', () => {
  it('detects presence case-insensitively', () => {
    expect(hasTheme(['HNW Investors'], 'hnw investors')).toBe(true);
    expect(hasTheme(['HNW Investors'], 'families')).toBe(false);
  });
});
