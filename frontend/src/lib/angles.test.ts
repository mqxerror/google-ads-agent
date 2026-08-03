// Angle taxonomy presentational metadata (Epic 16, story 16.2). The
// authoritative angle LIST comes from the served registry (taxonomy.angles); this
// module only provides display metadata. Assert the palette covers the backend
// taxonomy so no drafted angle renders without a chip style.

import { describe, it, expect } from 'vitest';
import { ANGLE_META, angleMeta } from './angles';

// Mirror of creative_specs.ANGLES (the served taxonomy). If the backend adds an
// angle, this list + ANGLE_META must grow — the test makes the gap visible.
const BACKEND_ANGLES = [
  'promotional', 'feature', 'benefit', 'urgency', 'social_proof', 'aspiration', 'specificity',
];

describe('angle presentational metadata', () => {
  it('covers every backend angle with a label + className', () => {
    for (const a of BACKEND_ANGLES) {
      expect(ANGLE_META[a], `missing ANGLE_META for ${a}`).toBeTruthy();
      expect(ANGLE_META[a].label).toBeTruthy();
      expect(ANGLE_META[a].className).toBeTruthy();
    }
  });

  it('angleMeta falls back to a neutral chip for null/unknown', () => {
    expect(angleMeta(null).label).toBe('—');
    expect(angleMeta('made_up').label).toBe('made_up');
    expect(angleMeta('benefit')).toBe(ANGLE_META.benefit);
  });
});
