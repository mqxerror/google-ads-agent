// Copy-row model tests (Epic 16, stories 16.2/16.3/16.4/16.7). Pure logic that
// bridges the field-centric wizards and the row-centric copy-jobs contract —
// including the FR1.8 "locked rows never enter the regenerate payload" rule and
// the FR5.1 coverage numbers.

import { describe, it, expect } from 'vitest';
import {
  distributeRows, toRows, regenerateTargets, buildDiversifyBody, spliceMeta,
  textCoverage, type CopyRow,
} from './copyRows';

describe('distributeRows — rows → per-field text + angle arrays (FR1.7)', () => {
  it('groups by tier, preserves order, folds short_description into descriptions', () => {
    const rows: CopyRow[] = [
      { text: 'H1', angle: 'benefit', tier: 'headline' },
      { text: 'LH1', angle: 'feature', tier: 'long_headline' },
      { text: 'H2', angle: 'urgency', tier: 'headline' },
      { text: 'D1', angle: 'benefit', tier: 'description' },
      { text: 'SD1', angle: 'specificity', tier: 'short_description' },
    ];
    const d = distributeRows(rows);
    expect(d.headlines).toEqual(['H1', 'H2']);
    expect(d.headlineAngles).toEqual(['benefit', 'urgency']);
    expect(d.longHeadlines).toEqual(['LH1']);
    expect(d.descriptions).toEqual(['D1', 'SD1']);
    expect(d.descriptionAngles).toEqual(['benefit', 'specificity']);
  });
});

describe('toRows — field arrays → CopyRows', () => {
  it('zips text + angle + lock with safe defaults', () => {
    const rows = toRows(['a', 'b'], ['benefit', null], 'headline', [false, true]);
    expect(rows).toEqual([
      { text: 'a', angle: 'benefit', tier: 'headline', locked: false },
      { text: 'b', angle: null, tier: 'headline', locked: true },
    ]);
  });
  it('defaults missing meta safely', () => {
    expect(toRows(['a'], undefined, 'description')).toEqual([
      { text: 'a', angle: null, tier: 'description', locked: false },
    ]);
  });
});

describe('regenerateTargets / buildDiversifyBody — locked rows never regenerate (FR1.8)', () => {
  it('regenerateTargets excludes locked, ascending + unique', () => {
    expect(regenerateTargets([3, 1, 1, 4], [4])).toEqual([1, 3]);
  });

  it('buildDiversifyBody: no locked index appears in flagged_rows', () => {
    const rows: CopyRow[] = [
      { text: 'dup a', angle: 'benefit', tier: 'headline', locked: false },
      { text: 'dup a', angle: 'benefit', tier: 'headline', locked: true },  // LOCKED
      { text: 'distinct', angle: 'feature', tier: 'headline' },
    ];
    const body = buildDiversifyBody(rows, new Set([0, 1]));
    expect(body.locked_rows).toEqual([1]);
    expect(body.flagged_rows).toEqual([0]);           // 1 is locked → excluded
    expect(body.flagged_rows).not.toContain(1);       // FR1.8 assertion
    expect(body.rows).toBe(rows);
  });

  it('passes dismissed dup pairs through (R1 escape hatch)', () => {
    const body = buildDiversifyBody([], new Set(), [[0, 1]]);
    expect(body.dismissed_dup_pairs).toEqual([[0, 1]]);
  });
});

describe('spliceMeta — parallel-array alignment', () => {
  it('adds a null slot on append', () => {
    expect(spliceMeta<(string | null)>(['a'], 1, 0, 1, null)).toEqual(['a', null]);
  });
  it('paste-split replaces 1 with N', () => {
    expect(spliceMeta<boolean>([false, false], 0, 1, 3, false)).toEqual([false, false, false, false]);
  });
  it('remove splices out', () => {
    expect(spliceMeta<string | null>(['a', 'b', 'c'], 1, 1, 0, null)).toEqual(['a', 'c']);
  });
});

describe('textCoverage — honest completeness numbers (FR5.1)', () => {
  it('counts filled slots, distinct angles, near-dupes', () => {
    const cov = textCoverage(
      ['Buy Panama', 'Move to Greece', ''],       // 2 filled
      ['benefit', 'benefit', null],               // 1 distinct angle among filled
      15,
      ['A desc', 'B desc'],
      5,
      1,                                          // nearDupCount passed in
    );
    expect(cov.headlinesFilled).toBe(2);
    expect(cov.headlinesMax).toBe(15);
    expect(cov.descriptionsFilled).toBe(2);
    expect(cov.distinctAngles).toBe(1);
    expect(cov.nearDupCount).toBe(1);
  });

  it('distinct angles ignores empty rows and nulls', () => {
    const cov = textCoverage(
      ['a', 'b', 'c'], ['benefit', 'urgency', null], 15, [], 5, 0,
    );
    expect(cov.distinctAngles).toBe(2);
  });
});
