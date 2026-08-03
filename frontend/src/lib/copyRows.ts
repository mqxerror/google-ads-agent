// Copy-row model — pure helpers for the angle-tagged drafting contract (Epic 16,
// stories 16.2/16.3/16.4). The wizards stay FIELD-centric (string[] per tier)
// while the copy-jobs contract is ROW-centric ({text, angle, tier}); these
// functions bridge the two and own the FR1.8 "locked rows never regenerate" rule.
// Pure + framework-free so vitest can assert them directly (node env).

export interface CopyRow {
  text: string;
  angle: string | null;
  tier: string;
  locked?: boolean;
}

export interface DistributedCopy {
  headlines: string[];
  headlineAngles: (string | null)[];
  longHeadlines: string[];
  longHeadlineAngles: (string | null)[];
  descriptions: string[];
  descriptionAngles: (string | null)[];
}

// tier → which wizard field a drafted row lands in (short_description folds into
// descriptions — it is a description under a tighter cap).
const TIER_FIELD: Record<string, keyof DistributedCopy> = {
  headline: 'headlines',
  long_headline: 'longHeadlines',
  description: 'descriptions',
  short_description: 'descriptions',
};

/** Distribute drafted rows into per-field text + parallel angle arrays. Order is
 * preserved within each tier. Empty arrays for fields with no rows. */
export function distributeRows(rows: CopyRow[]): DistributedCopy {
  const out: DistributedCopy = {
    headlines: [], headlineAngles: [],
    longHeadlines: [], longHeadlineAngles: [],
    descriptions: [], descriptionAngles: [],
  };
  const angleField: Record<string, keyof DistributedCopy> = {
    headlines: 'headlineAngles', longHeadlines: 'longHeadlineAngles', descriptions: 'descriptionAngles',
  };
  for (const r of rows) {
    const field = TIER_FIELD[r.tier];
    if (!field) continue;
    (out[field] as string[]).push(r.text);
    (out[angleField[field]] as (string | null)[]).push(r.angle ?? null);
  }
  return out;
}

/** Zip a field's parallel text + angle + lock arrays back into CopyRows for a
 * rewrite/diversify job payload. Trailing/short meta arrays default safely. */
export function toRows(
  texts: string[],
  angles: (string | null)[] | undefined,
  tier: string,
  locked?: boolean[],
): CopyRow[] {
  return texts.map((text, i) => ({
    text,
    angle: angles?.[i] ?? null,
    tier,
    locked: !!locked?.[i],
  }));
}

/** The indices to regenerate = flagged rows MINUS locked rows (FR1.8: a locked
 * row is never in the regenerate set). Deterministic ascending. */
export function regenerateTargets(flagged: Iterable<number>, locked: Iterable<number>): number[] {
  const lock = new Set<number>([...locked]);
  return [...new Set([...flagged])].filter(i => !lock.has(i)).sort((a, b) => a - b);
}

/** Build the diversify job body for a field. `flagged` comes from the client
 * near-dup detector; locked rows are excluded from the regenerate targets so a
 * locked row is provably ABSENT from what the server will regenerate (FR1.8). */
export function buildDiversifyBody(
  rows: CopyRow[],
  flagged: Iterable<number>,
  dismissedDupPairs: [number, number][] = [],
): { rows: CopyRow[]; flagged_rows: number[]; locked_rows: number[]; dismissed_dup_pairs: [number, number][] } {
  const locked = rows.map((r, i) => (r.locked ? i : -1)).filter(i => i >= 0);
  return {
    rows,
    locked_rows: locked,
    flagged_rows: regenerateTargets(flagged, locked),
    dismissed_dup_pairs: dismissedDupPairs,
  };
}

// ── parallel-array alignment (TextWorkbench keeps text + angle + lock in sync) ──

/** Splice a parallel meta array to mirror an items add/remove/paste. `fill` is
 * the value new slots get (null for angle, false for lock). */
export function spliceMeta<T>(meta: T[], start: number, deleteCount: number, insertCount: number, fill: T): T[] {
  const next = [...meta];
  next.splice(start, deleteCount, ...Array.from({ length: insertCount }, () => fill));
  return next;
}

// ── Coverage (Epic 16, story 16.7 — text scope) ──────────────────────────────
// An HONEST completeness meter: filled slots, distinct angles, near-dup count.
// It encourages FILLING slots and VARYING angles — never "reach Excellent",
// never maxing characters (that Ad-Strength-chasing anti-pattern is the point of
// reframing this, PRD FR5.1 / research #5). Pure so vitest asserts the numbers.

export interface TextCoverage {
  headlinesFilled: number;
  headlinesMax: number;
  descriptionsFilled: number;
  descriptionsMax: number;
  distinctAngles: number;
  nearDupCount: number;
}

/** Compute the text-coverage numbers. `nearDupCount` is passed in (the caller
 * runs the near-dup detector with the registry threshold) so this stays a pure
 * arithmetic function. Distinct angles counts non-null headline angles. */
export interface ImageSlotCoverage {
  slot: string;
  label: string;
  filled: number;
}

export interface ImageCoverage {
  /** Total images across ALL slots (the cross-slot count — Honesty Ledger #8). */
  totalFilled: number;
  /** Cross-slot cap (spec.total_image_cap); null ⇒ per-slot only. */
  totalCap: number | null;
  /** Per-aspect slot fill (label + filled). */
  slots: ImageSlotCoverage[];
}

/** Compute image coverage: the cross-slot total (against total_image_cap) plus
 * per-aspect slot fill. Pure arithmetic over the wizard's slot arrays and the
 * registry slot specs — zero network (FR5.1 image scope). */
export function imageCoverage(
  slots: { slot: string; label: string; count: number }[],
  totalCap: number | null,
): ImageCoverage {
  return {
    totalFilled: slots.reduce((n, s) => n + Math.max(0, s.count), 0),
    totalCap,
    slots: slots.map(s => ({ slot: s.slot, label: s.label, filled: Math.max(0, s.count) })),
  };
}

export function textCoverage(
  headlines: string[],
  headlineAngles: (string | null)[],
  headlinesMax: number,
  descriptions: string[],
  descriptionsMax: number,
  nearDupCount: number,
): TextCoverage {
  const filledIdx = headlines
    .map((t, i) => (t.trim() ? i : -1))
    .filter(i => i >= 0);
  const distinctAngles = new Set(
    filledIdx.map(i => headlineAngles[i]).filter((a): a is string => !!a),
  ).size;
  return {
    headlinesFilled: filledIdx.length,
    headlinesMax,
    descriptionsFilled: descriptions.filter(t => t.trim()).length,
    descriptionsMax,
    distinctAngles,
    nearDupCount,
  };
}
