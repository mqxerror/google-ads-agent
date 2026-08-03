// Story 15.6 — paste-multiline split (FR1.11).

import { describe, it, expect } from 'vitest';
import { splitPastedLines } from './pasteSplit';

describe('splitPastedLines', () => {
  it('pasting 3 newline-separated lines yields 3 rows', () => {
    expect(splitPastedLines('Move to Panama\nRetire in Greece\nInvest abroad'))
      .toEqual(['Move to Panama', 'Retire in Greece', 'Invest abroad']);
  });

  it('trims each line and drops empties/blank lines', () => {
    expect(splitPastedLines('  one  \n\n  two \n   \nthree')).toEqual(['one', 'two', 'three']);
  });

  it('handles CRLF newlines', () => {
    expect(splitPastedLines('a\r\nb')).toEqual(['a', 'b']);
  });

  it('does NOT truncate — a 45-char line stays 45 (over-limit at 40, not 30)', () => {
    const long = 'x'.repeat(45);
    const [line] = splitPastedLines(long);
    expect(line.length).toBe(45); // renders over-limit against fieldSpec.max_chars (40)
  });

  it('single line with no newline returns that one line', () => {
    expect(splitPastedLines('just one')).toEqual(['just one']);
  });
});
