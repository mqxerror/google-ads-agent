// SmartAspectSet invariants (Epic 17, story 17.6 · FR2.3/2.4/2.6). The vitest
// harness is node-env (no DOM runner), so the component contract is asserted as
// a source scan — the same pattern as CoveragePanel.test.ts. The numeric
// preflight math is proven in copyRows.test.ts style downstream; here we lock
// the honesty + config-driven invariants that must never regress.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

const SRC = readFileSync(resolve(__dirname, 'SmartAspectSet.tsx'), 'utf-8');

// Strip strings + comments so we scan CODE only for the bare-literal check.
function codeOnly(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .split('\n').map(l => {
      let out = '';
      let i = 0;
      while (i < l.length) {
        const c = l[i];
        if (c === '/' && l[i + 1] === '/') break;
        if (c === "'" || c === '"' || c === '`') {
          let j = i + 1;
          while (j < l.length && l[j] !== c) { if (l[j] === '\\') j++; j++; }
          i = j + 1;
          continue;
        }
        out += c;
        i++;
      }
      return out;
    }).join('\n');
}

describe('SmartAspectSet — config-driven cap (FR2.6, NFR-D1)', () => {
  it('reads the tile cap from the registry engine config, not a literal', () => {
    expect(SRC).toContain('batch_tile_cap');
    expect(SRC).toContain('useCreativeSpecs');
  });

  it('has no bare sentinel literal for the cap', () => {
    const code = codeOnly(SRC);
    // 20 is the current default cap — it must NEVER appear as a bare literal.
    expect(code).not.toMatch(/(?<![\w.])20(?![\w.])/);
  });

  it('names the cap in the over-cap rejection message', () => {
    expect(SRC).toContain('tile cap');
    expect(SRC).toContain('overCap');
  });
});

describe('SmartAspectSet — honest credit preflight (FR2.6)', () => {
  it('labels the credit estimate as an estimate', () => {
    expect(SRC.toLowerCase()).toContain('(est.)');
  });

  it('surfaces the operator balance from the Studio credits path', () => {
    expect(SRC).toContain('studioBalance');
    expect(SRC).toContain('balance');
  });

  it('estimates from the model est_credits field', () => {
    expect(SRC).toContain('est_credits');
  });
});

describe('SmartAspectSet — batch lifecycle wiring (FR2.3/2.4)', () => {
  it('creates a batch and streams the per-tile view', () => {
    expect(SRC).toContain('studioBatchRender');
    expect(SRC).toContain('batch-render');
    expect(SRC).toContain('/stream');
    expect(SRC).toContain('EventSource');
  });

  it('offers a per-tile retry affordance', () => {
    expect(SRC).toContain('studioRetryBatchTile');
    expect(SRC).toContain('Retry');
  });

  it('auto-assigns finished tiles (composite preferred over base)', () => {
    expect(SRC).toContain('onAssign');
    expect(SRC).toContain('composite_asset_id');
  });

  it('renders the advisory safe-zone flag, never blocking submit', () => {
    expect(SRC).toContain('safe_zone');
    expect(SRC.toLowerCase()).toContain('subject may be cut');
  });

  it('supports all three generation modes', () => {
    expect(SRC).toContain('with_logo');
    expect(SRC).toContain('without_logo');
    expect(SRC).toContain('asset_anchored');
  });
});
