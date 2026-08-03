// CoveragePanel invariant (Epic 16, story 16.7 · FR5.1). No DOM runner in this
// harness (node env), so the "no Ad-Strength chasing" copy invariant is asserted
// as a source scan of the RENDERED strings: the panel's visible copy must never
// tell the operator to reach "Excellent", and must never reward maxing chars.
// The coverage NUMBERS are proven in copyRows.test.ts (textCoverage).

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

const SRC = readFileSync(resolve(__dirname, 'CoveragePanel.tsx'), 'utf-8');

// Strip line + block comments so we scan RENDERED copy only, not the rationale.
function strippedSource(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .split('\n').map(l => l.replace(/\/\/.*$/, '')).join('\n');
}

describe('CoveragePanel copy invariant (FR5.1)', () => {
  const code = strippedSource(SRC);

  it('never chases an "Excellent" Ad-Strength label in visible copy', () => {
    expect(code.toLowerCase()).not.toContain('excellent');
  });

  it('encourages filling slots, not maxing characters', () => {
    expect(code).toContain('fill more slots');
    expect(code).toContain('vary the angle');
    expect(code.toLowerCase()).not.toContain('max characters');
    expect(code.toLowerCase()).not.toContain('maximize characters');
  });

  it('surfaces the three coverage dimensions', () => {
    expect(code).toContain('Headlines');
    expect(code).toContain('Distinct angles');
    expect(code).toContain('Near-dupes');
  });
});

describe('CoveragePanel image-slot scope (story 17.7 · FR5.1)', () => {
  const code = strippedSource(SRC);

  it('computes image coverage from the registry-driven imageCoverage helper', () => {
    expect(SRC).toContain('imageCoverage');
    expect(SRC).toContain('totalImageCap');
    expect(SRC).toContain('imageSlots');
  });

  it('shows cross-slot images n/cap and per-aspect slot fill', () => {
    expect(code).toContain('Images');
    expect(code).toContain('img.totalFilled');
    expect(code).toContain('img.totalCap');
    expect(code).toContain('img.slots');
  });

  it('never chases an "Excellent" label in the image section either', () => {
    expect(code.toLowerCase()).not.toContain('excellent');
  });
});
