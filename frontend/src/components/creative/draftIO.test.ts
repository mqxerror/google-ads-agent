// Story 15.5 — export/import round-trip + over-limit surfacing (FR4.5).

import { describe, it, expect } from 'vitest';
import { serializeDraft, parseDraft, bundleIssues } from './draftIO';
import type { CampaignSpec } from '@/lib/creativeSpecs';

const sampleBundle = {
  name: 'Panama QIP',
  dailyBudget: '50',
  finalUrl: 'https://goldenvisas.mercan.com/panama',
  businessName: 'Mercan',
  headlines: ['Move to Panama', 'Second residency, done right'],
  longHeadlines: ['A long headline for the asset group'],
  descriptions: ['Panama investor visa, done right.', 'Another short description.'],
  logos: ['uuid-logo-1'],
  landscape: ['uuid-l1'],
  square: [],
  portrait: [],
  videoIds: [''],
  audienceSignals: ['panama residency'],
};

describe('export/import round-trip (FR4.5)', () => {
  it('round-trips deep-equal', () => {
    const json = serializeDraft('pmax', sampleBundle);
    const { bundle, campaignType } = parseDraft<typeof sampleBundle>(json);
    expect(bundle).toEqual(sampleBundle);
    expect(campaignType).toBe('pmax');
  });

  it('accepts a bare bundle object (back-compat)', () => {
    const json = JSON.stringify(sampleBundle);
    const { bundle, campaignType } = parseDraft<typeof sampleBundle>(json);
    expect(bundle).toEqual(sampleBundle);
    expect(campaignType).toBeNull();
  });

  it('throws a friendly error on bad JSON — never crashes the caller', () => {
    expect(() => parseDraft('{not json')).toThrowError(/valid JSON/i);
    expect(() => parseDraft('42')).toThrowError(/JSON object/i);
  });
});

const PMAX_SPEC: CampaignSpec = {
  text: {
    headlines: { min_count: 3, max_count: 15, max_chars: 30, verified: true, source: 't' },
    long_headlines: { min_count: 1, max_count: 5, max_chars: 90, verified: true, source: 't' },
    descriptions: { min_count: 2, max_count: 5, max_chars: 90, verified: true, source: 't' },
  },
  images: {},
  logos: {},
  business_name_max: 25,
  total_image_cap: 20,
  search_themes: [25, 80],
  video: { max_per_orientation: 15, min_seconds: 10, required: false, verified: false, source: 't' },
  final_url_max: 2048,
  policy: { on_image_text: 'forbid', logo_overlay: 'allow_warned', video_gate: 'nudge' },
  short_description: null,
};

describe('bundleIssues — over-limit import surfaces per-field errors', () => {
  it('no issues on a clean bundle', () => {
    expect(bundleIssues(sampleBundle, PMAX_SPEC)).toEqual([]);
  });

  it('flags an over-length headline', () => {
    const over = { ...sampleBundle, headlines: ['x'.repeat(31)] };
    expect(bundleIssues(over, PMAX_SPEC).join(' | ')).toContain('is 31 chars (max 30)');
  });

  it('flags too many descriptions', () => {
    const over = { ...sampleBundle, descriptions: Array.from({ length: 6 }, (_, i) => `d${i}`) };
    expect(bundleIssues(over, PMAX_SPEC).join(' | ')).toContain('too many descriptions: 6 (max 5)');
  });

  it('flags an over-length business name', () => {
    const over = { ...sampleBundle, businessName: 'z'.repeat(26) };
    expect(bundleIssues(over, PMAX_SPEC).join(' | ')).toContain('business_name is 26 chars (max 25)');
  });

  it('no spec → no issues (specs not loaded yet)', () => {
    expect(bundleIssues(sampleBundle, undefined)).toEqual([]);
  });
});
