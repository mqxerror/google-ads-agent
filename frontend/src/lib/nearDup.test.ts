// Story 15.6 — near-dup detector: parity fixture + perf + zero-network (FR1.10,
// NFR-P1). This suite reads the SAME golden fixture the Python twin (story 16.4)
// reads; both must produce identical flag sets on every case (fence F5). The
// stopword list is asserted equal to the fixture's so the two runtimes cannot
// drift.

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect, vi } from 'vitest';
import { findNearDupPairs, STOPWORDS } from './nearDup';

interface Fixture {
  threshold: number;
  stopwords: string[];
  cases: { name: string; texts: string[]; expected_pairs: [number, number][] }[];
}

// SAME path the pytest parity test loads (symlink-free, single source).
const FIXTURE_PATH = resolve(__dirname, '../../../backend/tests/fixtures/near_dup_cases.json');
const fixture = JSON.parse(readFileSync(FIXTURE_PATH, 'utf-8')) as Fixture;

describe('near-dup parity fixture (fence F5)', () => {
  it('the runtime stopword list equals the fixture list (no drift)', () => {
    expect([...STOPWORDS]).toEqual(fixture.stopwords);
  });

  for (const c of fixture.cases) {
    it(`case "${c.name}" flags exactly the expected pairs`, () => {
      const pairs = findNearDupPairs(c.texts, {
        threshold: fixture.threshold,
        stopwords: fixture.stopwords,
      });
      expect(pairs).toEqual(c.expected_pairs);
    });
  }

  it('two-known-near-dupes case flags exactly those 2 rows, stable on repeat', () => {
    const c = fixture.cases.find(x => x.name === 'fifteen-rows-two-dupes')!;
    const a = findNearDupPairs(c.texts, { threshold: fixture.threshold, stopwords: fixture.stopwords });
    const b = findNearDupPairs(c.texts, { threshold: fixture.threshold, stopwords: fixture.stopwords });
    expect(a).toEqual([[3, 11]]);
    expect(a).toEqual(b); // deterministic on repeat runs
  });
});

describe('NFR-P1 — interactive speed, zero network', () => {
  it('a 15-row set completes < 50 ms with zero fetch calls', () => {
    const fetchSpy = vi.fn();
    (globalThis as unknown as { fetch: unknown }).fetch = fetchSpy;
    const rows = Array.from({ length: 15 }, (_, i) => `Distinct headline number ${i} about residency`);
    const t0 = performance.now();
    findNearDupPairs(rows, { threshold: 0.65, stopwords: fixture.stopwords });
    const elapsed = performance.now() - t0;
    expect(elapsed).toBeLessThan(50);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
