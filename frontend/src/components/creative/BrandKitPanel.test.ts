// BrandKitPanel invariants (Epic 18, story 18.5 · FR5.2/FR5.3). Node-env harness
// (no DOM runner — mirrors CoveragePanel.test.ts), so the render contract is
// asserted as a source scan of the component: the rationale fields are rendered,
// an HONEST empty state exists (not placeholders), and the one-click theme append
// is wired through the pure appendSearchTheme helper (whose behavior is proven in
// lib/brandKit.test.ts).

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

const SRC = readFileSync(resolve(__dirname, 'BrandKitPanel.tsx'), 'utf-8');

describe('BrandKitPanel render contract (FR5.2)', () => {
  it('renders all four rationale fields from research', () => {
    // value_prop / audience / tone / claim_hints (FR5.2 AC)
    expect(SRC).toContain('research.value_prop');
    expect(SRC).toContain('research.audience');
    expect(SRC).toContain('research.tone');
    expect(SRC).toContain('research.claim_hints');
    // the labelled rows
    expect(SRC).toMatch(/label="Value prop"/);
    expect(SRC).toMatch(/label="Audience"/);
    expect(SRC).toMatch(/label="Tone"/);
  });

  it('shows an HONEST empty state when research is absent, not placeholders', () => {
    // guarded on `!research`, with real copy — no fake value_prop / lorem
    expect(SRC).toMatch(/!research/);
    expect(SRC).toMatch(/No audience research/i);
    expect(SRC.toLowerCase()).not.toContain('lorem');
  });
});

describe('BrandKitPanel one-click themes (FR5.3)', () => {
  it('wires suggested audiences through the idempotent, capped append helper', () => {
    expect(SRC).toContain('appendSearchTheme');
    expect(SRC).toContain('suggested_audiences');
    // the append is gated on a themeTarget (PMax search themes) and calls onChange
    expect(SRC).toContain('themeTarget');
    expect(SRC).toContain('themeTarget.onChange');
  });

  it('respects the registry cap in the UI (disables at max, reads maxItems/maxChars)', () => {
    expect(SRC).toContain('maxItems');
    expect(SRC).toContain('maxChars');
    expect(SRC).toMatch(/atCap/);
  });
});

describe('BrandKitPanel scrape call (FR3.5/FR5.2)', () => {
  it('requests the rationale + honors the ownership posture', () => {
    expect(SRC).toContain('/api/creative/brand-kit');
    expect(SRC).toContain('include_research: true');
    expect(SRC).toContain('confirm_ownership');
  });
});
