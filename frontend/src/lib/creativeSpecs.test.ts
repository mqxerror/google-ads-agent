// Story 14.5 — the client Creative Spec provider (FR1.2, NFR-P2, NFR-D1).
//
// Tests the PURE core (mappers + resolver + cache) so no React render / jsdom is
// needed. The FR1.2 proof: serving a changed spec value moves the UI over-limit
// boundary with ZERO wizard-code change — the wizard only reads the mapper output.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  dgRulesFromSpecs,
  pmaxRulesFromSpecs,
  rdaRulesFromSpecs,
  resolveSpecs,
  loadSpecsCache,
  saveSpecsCache,
  type SpecsResponse,
} from './creativeSpecs';

function specsWith(dgHeadlineMaxChars: number): SpecsResponse {
  const tf = (min: number, max: number, chars: number) => ({
    min_count: min, max_count: max, max_chars: chars, verified: true, source: 't',
  });
  const slot = (s: string, max: number, req: boolean) => ({
    slot: s, max_count: max, required: req, verified: true, source: 't', geometry: null,
  });
  const base = {
    business_name_max: 25,
    total_image_cap: 20,
    search_themes: null as [number, number] | null,
    video: { max_per_orientation: null, min_seconds: 5, required: false, verified: true, source: 't' },
    final_url_max: 2048,
    policy: { on_image_text: 'forbid', logo_overlay: 'forbid', video_gate: 'nudge' },
    short_description: null,
  };
  return {
    campaign_types: {
      demand_gen: {
        ...base,
        text: { headlines: tf(1, 5, dgHeadlineMaxChars), descriptions: tf(1, 5, 90) },
        images: { landscape: slot('landscape', 20, true), square: slot('square', 20, true) },
        logos: { logos: slot('logos', 5, true) },
      },
      pmax: {
        ...base,
        search_themes: [25, 80],
        text: {
          headlines: tf(3, 15, 30),
          long_headlines: tf(1, 5, 90),
          descriptions: tf(2, 5, 90),
        },
        images: {
          landscape: slot('landscape', 20, true),
          square: slot('square', 20, true),
          portrait: slot('portrait', 20, false),
        },
        logos: { logos: slot('logos', 5, true) },
      },
      rda: {
        ...base,
        total_image_cap: 15,
        text: {
          headlines: tf(1, 5, 30),
          long_headlines: tf(1, 1, 90),   // exactly one
          descriptions: tf(1, 5, 90),
        },
        images: {
          landscape: slot('landscape', 15, true),
          square: slot('square', 15, true),
        },
        logos: {
          logos: slot('logos', 5, true),
          landscape_logo: slot('landscape_logo', 5, false),
        },
      },
    },
    engine: { near_dup_threshold: 0.65, batch_tile_cap: 20, batch_retry_max: 2 },
    version: 'test',
  };
}

describe('FR1.2 — served spec value drives the client boundary', () => {
  it('DG headline over-limit boundary follows the served max_chars (40)', () => {
    const rules = dgRulesFromSpecs(specsWith(40));
    expect(rules.headlines.maxChars).toBe(40);
  });

  it('serving max_chars:35 moves the boundary with zero wizard-code change', () => {
    const rules = dgRulesFromSpecs(specsWith(35));
    expect(rules.headlines.maxChars).toBe(35);
    // a 36-char headline is over-limit under the served spec, a 35 is not
    const over = (len: number) => len > rules.headlines.maxChars;
    expect(over(36)).toBe(true);
    expect(over(35)).toBe(false);
  });
});

describe('mappers cover the wizard rule shapes', () => {
  it('DG maps counts, business name, logo + image caps', () => {
    const r = dgRulesFromSpecs(specsWith(40));
    expect(r).toMatchObject({
      headlines: { min: 1, max: 5, maxChars: 40 },
      descriptions: { min: 1, max: 5, maxChars: 90 },
      businessNameMaxChars: 25,
      logos: { min: 1, max: 5 },
      imageMax: 20,
      ready: true,
    });
  });

  it('PMax maps headlines/longHeadlines/descriptions + required image slots', () => {
    const r = pmaxRulesFromSpecs(specsWith(40));
    expect(r.headlines).toEqual({ min: 3, max: 15, maxChars: 30 });
    expect(r.longHeadlines).toEqual({ min: 1, max: 5, maxChars: 90 });
    expect(r.descriptions).toEqual({ min: 2, max: 5, maxChars: 90 });
    expect(r.landscape.min).toBe(1);
    expect(r.square.min).toBe(1);
    expect(r.imageMax).toBe(20);
    expect(r.ready).toBe(true);
  });

  it('RDA maps the exactly-1 long headline + required marketing slots + optional 4:1 logo', () => {
    const r = rdaRulesFromSpecs(specsWith(40));
    expect(r.headlines).toEqual({ min: 1, max: 5, maxChars: 30 });
    expect(r.longHeadlines).toEqual({ min: 1, max: 1, maxChars: 90 }); // exactly one
    expect(r.descriptions).toEqual({ min: 1, max: 5, maxChars: 90 });
    expect(r.landscape.min).toBe(1);   // required
    expect(r.square.min).toBe(1);      // required
    expect(r.logos.min).toBe(1);       // required 1:1 logo
    expect(r.landscapeLogo.min).toBe(0); // 4:1 optional
    expect(r.imageMax).toBe(15);       // combined cap
    expect(r.ready).toBe(true);
  });

  it('RDA null specs → not ready, permissive (no false over-limit)', () => {
    const r = rdaRulesFromSpecs(null);
    expect(r.ready).toBe(false);
    expect(r.longHeadlines.max).toBe(Infinity);
    expect(r.logos.min).toBe(0);
  });
});

describe('NFR-P2 / readiness — permissive before the first-ever fetch', () => {
  it('null specs → not ready, no false over-limit (Infinity caps, 0 mins)', () => {
    const r = dgRulesFromSpecs(null);
    expect(r.ready).toBe(false);
    expect(r.headlines.maxChars).toBe(Infinity); // nothing shows over-limit
    expect(r.headlines.min).toBe(0);
    // a 500-char headline is NOT flagged over-limit before specs load
    expect(500 > r.headlines.maxChars).toBe(false);
  });

  it('resolveSpecs prefers query data, falls back to cache, else null', () => {
    const cache = specsWith(40);
    const fresh = specsWith(35);
    expect(resolveSpecs(undefined, null)).toEqual({ specs: null, ready: false });
    // renders immediately from cache while the endpoint is still pending (slow)
    expect(resolveSpecs(undefined, cache)).toEqual({ specs: cache, ready: true });
    // fresh network data wins over the cached copy
    expect(resolveSpecs(fresh, cache).specs).toBe(fresh);
  });
});

describe('localStorage cache round-trips (stale-while-revalidate)', () => {
  beforeEach(() => {
    const store: Record<string, string> = {};
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => (k in store ? store[k] : null),
      setItem: (k: string, v: string) => { store[k] = v; },
      removeItem: (k: string) => { delete store[k]; },
      clear: () => { for (const k of Object.keys(store)) delete store[k]; },
    });
  });

  it('saveSpecsCache then loadSpecsCache returns the same payload', () => {
    const specs = specsWith(40);
    expect(loadSpecsCache()).toBeNull();
    saveSpecsCache(specs);
    expect(loadSpecsCache()).toEqual(specs);
  });
});
