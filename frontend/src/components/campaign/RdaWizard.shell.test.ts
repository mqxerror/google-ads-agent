// RdaWizard shell-gate (story 19.3 · FR6.3) — the machine check that the Display
// builder is a THIN SHELL, not a third copy of the creative machinery.
//
// FR6.3 makes the shell the ACCEPTANCE TEST of the core. This audit reads the
// RdaWizard source and asserts:
//   1. line count < 647 (half of DemandGenWizard's 1,294)
//   2. no bare creative-limit LITERAL (the registry-drift sentinel set — the shell
//      reads every limit from useRdaRules(), never a baked number)
//   3. no fetch to a GENERATION endpoint (copy drafting + image generation live in
//      the imported shared hooks/components, never in the shell)
//   4. no resurrected wizard RULES constant (tombstoned in Epics 14–15)
//   5. import-only: every shared piece arrives by import
//
// Mirrors the backend spec-drift guard's stripping so a limit inside a string or
// comment (e.g. a hint template) never false-flags.

import { readFileSync } from 'node:fs';
import { describe, it, expect } from 'vitest';

const SRC = readFileSync(new URL('./RdaWizard.tsx', import.meta.url), 'utf-8');
const LINES = SRC.split('\n').length;

// The shell-gate line cap (FR6.3 / architecture §AD-6): under half of the
// DemandGenWizard (1,294 lines). Kept as the test's own constant, NOT a creative
// limit, so it is exempt from the sentinel scan (this file is the audit, not an
// enforcement file under the registry).
const SHELL_LINE_CAP = 647;

// The registry-drift sentinel set (same as the backend guard). A bare one of
// these in the shell would be a baked creative limit.
const SENTINELS = new Set([15, 20, 25, 30, 40, 60, 80, 90, 128, 2048]);

/** Blank C-style block comments whole-file (preserve newlines). */
function stripBlockComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '));
}

/** Per-line: blank balanced string/template literals + // line comments. Per-line
 *  state (mirrors the backend guard) so a JSX apostrophe can't desync the scan. */
function stripLine(line: string): string {
  const out: string[] = [];
  let i = 0;
  const n = line.length;
  while (i < n) {
    const c = line[i];
    if (c === '/' && i + 1 < n && line[i + 1] === '/') break;
    if (c === "'" || c === '"' || c === '`') {
      let j = i + 1;
      while (j < n) {
        if (line[j] === '\\') { j += 2; continue; }
        if (line[j] === c) break;
        j++;
      }
      if (j < n) { out.push(' '.repeat(j - i + 1)); i = j + 1; continue; }
      out.push(c); i++; continue;
    }
    out.push(c); i++;
  }
  return out.join('');
}

function sentinelHits(src: string): number[] {
  const stripped = stripBlockComments(src)
    .split('\n')
    .map(stripLine)
    .join('\n');
  const hits: number[] = [];
  const re = /(?<![\w.])(\d+)(?![\w.])/g;
  for (const m of stripped.matchAll(re)) {
    const v = Number(m[1]);
    if (SENTINELS.has(v)) hits.push(v);
  }
  return hits;
}

describe('RdaWizard shell-gate (FR6.3)', () => {
  it(`is under the ${SHELL_LINE_CAP}-line shell cap (actual: ${LINES})`, () => {
    // eslint-disable-next-line no-console
    console.log(`RdaWizard.tsx line count: ${LINES} (cap ${SHELL_LINE_CAP})`);
    expect(LINES).toBeLessThan(SHELL_LINE_CAP);
  });

  it('bakes NO creative-limit literal — all limits come from useRdaRules()', () => {
    expect(sentinelHits(SRC)).toEqual([]);
  });

  it('sentinel scanner is real (self-test: catches a bare limit, ignores strings)', () => {
    expect(sentinelHits('const max = 30;')).toEqual([30]);
    expect(sentinelHits('const s = "30 chars";')).toEqual([]);
    expect(sentinelHits('const x = 31;')).toEqual([]);
  });

  it('does NOT fetch a generation endpoint (drafting/generation is imported)', () => {
    for (const pat of [
      'copy-jobs', 'batch-render', 'studioBatchRender', 'studioGetBatch',
      '/api/studio', '/studio/',
    ]) {
      expect(SRC.includes(pat), `shell must not reference ${pat}`).toBe(false);
    }
    // It DOES own the create call (that is not generation).
    expect(SRC.includes('/campaigns/rda')).toBe(true);
  });

  it('resurrects no wizard RULES constant (tombstoned in Epics 14–15)', () => {
    expect(/\bconst\s+RULES\b/.test(SRC)).toBe(false);
  });

  it('composes entirely from imported shared pieces (import-only)', () => {
    for (const imp of [
      'useRdaRules', 'TextWorkbench', 'CoveragePanel', 'SmartAspectSet',
      'DraftManager', 'BrandKitPanel', 'ConfirmCreateModal', 'useDraftJob',
      'ReferencePhotosPicker', 'BusinessNameField', 'PolicyHintCard',
    ]) {
      expect(SRC.includes(imp), `shell must import ${imp}`).toBe(true);
    }
  });
});
