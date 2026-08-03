// Deterministic near-duplicate detector (Epic 15, story 15.6 · FR1.10, NFR-P1).
//
// The AD-2 pinned algorithm, client side. Runs on keystroke/paste — no LLM, no
// network — so it must be cheap and reproducible (a full 15-row set < 50 ms). A
// Python twin (backend/app/services/near_dup.py, story 16.4) implements the SAME
// algorithm and is PARITY-LOCKED to the SAME golden fixture
// (backend/tests/fixtures/near_dup_cases.json): both suites assert identical flag
// sets on every case.
//
// Algorithm:
//   1. Normalize: lowercase -> strip punctuation/symbols -> collapse whitespace
//      -> drop a fixed stopword list -> light suffix fold (ing / ed / s).
//   2. Compare: token-SET Jaccard  sim = |A∩B| / |A∪B|;  ALSO flag when the
//      smaller set is fully contained in the larger (|A∩B| = min(|A|,|B|)) —
//      catches "Move to Panama" vs "Move to Panama today".
//   3. Flag a pair when sim >= threshold (from the registry — never a baked
//      constant) OR the containment rule fires.
//
// The stopword list is the canonical parity list: it also ships in the fixture,
// and the parity test asserts STOPWORDS deep-equals the fixture's list so the two
// runtimes can never drift.

/** Fixed 30-word English stopword list (parity-locked with the fixture). */
export const STOPWORDS: readonly string[] = [
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
  'in', 'is', 'it', 'of', 'on', 'or', 'that', 'the', 'this', 'to',
  'was', 'were', 'with', 'you', 'your', 'we', 'our', 'my', 'i', 'but',
];

/** Light suffix fold: 'ing' -> '', 'ed' -> '', trailing 's' -> ''. Order + the
 * length guards match the Python twin exactly. */
export function suffixFold(token: string): string {
  if (token.length > 4 && token.endsWith('ing')) return token.slice(0, -3);
  if (token.length > 3 && token.endsWith('ed')) return token.slice(0, -2);
  if (token.length > 3 && token.endsWith('s')) return token.slice(0, -1);
  return token;
}

/** Normalize one string to its token list (may be empty). */
export function normalizeTokens(text: string, stopwords: Set<string>): string[] {
  const cleaned = text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) return [];
  return cleaned
    .split(' ')
    .filter(t => t.length > 0 && !stopwords.has(t))
    .map(suffixFold);
}

function isNearDup(a: string[], b: string[], threshold: number): boolean {
  const A = new Set(a);
  const B = new Set(b);
  if (A.size === 0 || B.size === 0) return false; // don't flag empty / all-stopword rows
  let inter = 0;
  for (const t of A) if (B.has(t)) inter++;
  const union = A.size + B.size - inter;
  const jaccard = union === 0 ? 0 : inter / union;
  const contained = inter === Math.min(A.size, B.size);
  return jaccard >= threshold || contained;
}

export interface NearDupOptions {
  /** Similarity threshold — from the registry (ENGINE.near_dup_threshold). */
  threshold: number;
  /** Stopword list; defaults to STOPWORDS. Tests pass the fixture's list. */
  stopwords?: readonly string[];
}

/** Return the flagged near-duplicate pairs as [i, j] index tuples (i < j),
 * deterministic and in ascending order. Empty / whitespace rows never flag. */
export function findNearDupPairs(texts: string[], opts: NearDupOptions): Array<[number, number]> {
  const stop = new Set((opts.stopwords ?? STOPWORDS).map(s => s.toLowerCase()));
  const norm = texts.map(t => normalizeTokens(t, stop));
  const pairs: Array<[number, number]> = [];
  for (let i = 0; i < norm.length; i++) {
    for (let j = i + 1; j < norm.length; j++) {
      if (isNearDup(norm[i], norm[j], opts.threshold)) pairs.push([i, j]);
    }
  }
  return pairs;
}

/** Convenience: the set of row indices that participate in ANY near-dup pair —
 * what the workbench badges. */
export function flaggedRowIndices(texts: string[], opts: NearDupOptions): Set<number> {
  const flagged = new Set<number>();
  for (const [i, j] of findNearDupPairs(texts, opts)) {
    flagged.add(i);
    flagged.add(j);
  }
  return flagged;
}
