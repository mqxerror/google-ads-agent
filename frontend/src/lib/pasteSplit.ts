// Paste-multiline split (Epic 15, story 15.6 · FR1.11).
//
// Pasting newline-separated text into one TextWorkbench row splits it into one
// row per line. Lines are trimmed and empties dropped, but NOT truncated: a
// pasted line longer than the field's max renders the over-limit state, where the
// boundary is the FieldSpec's max_chars (e.g. 40 for DG headlines, not the old
// 30) — proving the limit is sourced from the registry, not a stale constant.

export function splitPastedLines(text: string): string[] {
  return text
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line.length > 0);
}
