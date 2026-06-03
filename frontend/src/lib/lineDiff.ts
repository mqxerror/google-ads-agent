/**
 * Tiny line-level diff using LCS. Good enough for guideline files (markdown,
 * usually < 1000 lines). Returns a sequence of operations the diff viewer can
 * render as red/green/unchanged rows.
 *
 * Not optimized for very long files — LCS is O(n*m). For our use case (a few
 * hundred lines max) it's fine.
 */

export type DiffOp =
  | { type: 'unchanged'; line: string; oldNum: number; newNum: number }
  | { type: 'removed';   line: string; oldNum: number }
  | { type: 'added';     line: string; newNum: number };

export function lineDiff(oldText: string, newText: string): DiffOp[] {
  const a = oldText.split('\n');
  const b = newText.split('\n');
  const m = a.length, n = b.length;

  // LCS DP table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j]
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  // Walk the table to emit ops
  const ops: DiffOp[] = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      ops.push({ type: 'unchanged', line: a[i], oldNum: i + 1, newNum: j + 1 });
      i++; j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ type: 'removed', line: a[i], oldNum: i + 1 });
      i++;
    } else {
      ops.push({ type: 'added', line: b[j], newNum: j + 1 });
      j++;
    }
  }
  while (i < m) ops.push({ type: 'removed', line: a[i], oldNum: i + 1 }), i++;
  while (j < n) ops.push({ type: 'added', line: b[j], newNum: j + 1 }), j++;
  return ops;
}

/** Stat tuple for the header pill. */
export function diffStats(ops: DiffOp[]): { added: number; removed: number; unchanged: number } {
  let added = 0, removed = 0, unchanged = 0;
  for (const op of ops) {
    if (op.type === 'added') added++;
    else if (op.type === 'removed') removed++;
    else unchanged++;
  }
  return { added, removed, unchanged };
}
