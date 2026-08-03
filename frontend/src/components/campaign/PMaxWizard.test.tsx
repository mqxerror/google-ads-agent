// Story 14.6 — PMax client gap-closure mirrors (FR1.4) + soft warnings (FR1.3)
// + the FR1.6/D3 "no on-image-text knob renders in P1–P4" structural assertion.
//
// The FR1.4 mirrors are tested through the pure `validatePMax` the wizard uses as
// its client gate (each server rejection has a matching client rejection). The
// FR1.6 assertion is a source-tree scan (no on-image-text control exists in
// either wizard) — the harness for full DOM component tests lands with the
// Epic-16 workbench; the mirror logic + no-knob invariant are the P1 contract.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';
import { validatePMax, isMalformedUrl, type PMaxValidationInput } from '@/lib/pmaxClientValidation';
import type { PMaxRules } from '@/lib/creativeSpecs';

const RULES: PMaxRules = {
  headlines: { min: 3, max: 15, maxChars: 30 },
  longHeadlines: { min: 1, max: 5, maxChars: 90 },
  descriptions: { min: 2, max: 5, maxChars: 90 },
  logos: { min: 1, max: 5 },
  landscape: { min: 1, max: 20 },
  square: { min: 1, max: 20 },
  videos: { min: 0, max: Infinity },
  imageMax: 20,
  businessNameMaxChars: 25,
  searchThemes: { maxCount: 25, maxChars: 80 },
  finalUrlMax: 2048,
  shortDescriptionMaxChars: 60,
  ready: true,
};

function validInput(over: Partial<PMaxValidationInput> = {}): PMaxValidationInput {
  return {
    businessName: 'Mercan',
    finalUrl: 'https://example.com/landing',
    headlines: ['Head one', 'Head two', 'Head three'],
    longHeadlines: ['A long headline for the asset group'],
    descriptions: ['A short punchy description.', 'Another short description here.'],
    logos: ['logo-1'],
    landscape: ['l1'],
    square: ['s1'],
    portrait: [],
    audienceSignals: [],
    ...over,
  };
}

const errs = (over: Partial<PMaxValidationInput>) => validatePMax(validInput(over), RULES).errors.join(' | ');
const warns = (over: Partial<PMaxValidationInput>) => validatePMax(validInput(over), RULES).warnings.join(' | ');

describe('FR1.4 — each server rejection is mirrored client-side', () => {
  it('valid bundle has no errors', () => {
    expect(validatePMax(validInput(), RULES).errors).toEqual([]);
  });

  it('16 headlines → over max_count', () => {
    expect(errs({ headlines: Array.from({ length: 16 }, (_, i) => `H${i}`) }))
      .toContain('too many headlines: 16 (max 15)');
  });

  it('26-char business name rejected; 25 ok', () => {
    expect(errs({ businessName: 'z'.repeat(26) })).toContain('business name is 26 chars (max 25)');
    expect(validatePMax(validInput({ businessName: 'z'.repeat(25) }), RULES).errors).toEqual([]);
  });

  it('21st image across ratios rejected (cross-slot sum, honesty #8)', () => {
    expect(errs({
      landscape: Array.from({ length: 7 }, (_, i) => `l${i}`),
      square: Array.from({ length: 7 }, (_, i) => `s${i}`),
      portrait: Array.from({ length: 7 }, (_, i) => `p${i}`),
    })).toContain('too many images: 21 across ratios (max 20 per asset group)');
  });

  it('20 images across ratios is allowed', () => {
    const v = validatePMax(validInput({
      landscape: Array.from({ length: 7 }, (_, i) => `l${i}`),
      square: Array.from({ length: 7 }, (_, i) => `s${i}`),
      portrait: Array.from({ length: 6 }, (_, i) => `p${i}`),
    }), RULES);
    expect(v.errors.some(e => e.includes('too many images'))).toBe(false);
  });

  it('26th search theme rejected; 25 ok', () => {
    expect(errs({ audienceSignals: Array.from({ length: 26 }, (_, i) => `theme ${i}`) }))
      .toContain('too many search themes: 26 (max 25)');
    expect(validatePMax(validInput({ audienceSignals: Array.from({ length: 25 }, (_, i) => `t${i}`) }), RULES)
      .errors.some(e => e.includes('too many search themes'))).toBe(false);
  });

  it('81-char search theme rejected; 80 ok', () => {
    expect(errs({ audienceSignals: ['t'.repeat(81)] })).toContain('search theme is 81 chars (max 80)');
    expect(validatePMax(validInput({ audienceSignals: ['t'.repeat(80)] }), RULES)
      .errors.some(e => e.includes('search theme is'))).toBe(false);
  });

  it('malformed final URL rejected', () => {
    expect(errs({ finalUrl: 'not a url' })).toContain('malformed final URL');
    expect(isMalformedUrl('https://example.com')).toBe(false);
    expect(isMalformedUrl('ftp://example.com')).toBe(true);
  });
});

describe('FR1.3 — soft rules warn, never block', () => {
  it('zero ≤60 descriptions → warning, not an error', () => {
    const long = ['x'.repeat(85), 'y'.repeat(85)];
    expect(warns({ descriptions: long })).toContain('short description');
    expect(validatePMax(validInput({ descriptions: long }), RULES).errors
      .some(e => e.includes('short description'))).toBe(false);
  });

  it('a short description present → no warning', () => {
    expect(validatePMax(validInput(), RULES).warnings.some(w => w.includes('short description'))).toBe(false);
  });
});

describe('readiness — no false flags before specs load', () => {
  it('not-ready rules produce no errors even on an over-limit bundle', () => {
    const notReady: PMaxRules = { ...RULES, ready: false };
    expect(validatePMax(validInput({ businessName: 'z'.repeat(99) }), notReady).errors).toEqual([]);
  });
});

describe('FR1.6 / D3 — no on-image-text knob renders in P1–P4', () => {
  const read = (rel: string) => readFileSync(resolve(__dirname, rel), 'utf-8');

  it('neither wizard exposes an on-image-text policy control', () => {
    for (const f of ['PMaxWizard.tsx', 'DemandGenWizard.tsx']) {
      const src = read(f).toLowerCase();
      // the registry knob must never surface as a UI control before Display (P5)
      expect(src).not.toContain('on_image_text');
      expect(src).not.toContain('onimagetext');
      expect(src).not.toContain('on-image-text');
      expect(src).not.toContain('allow_warned');
    }
  });
});
