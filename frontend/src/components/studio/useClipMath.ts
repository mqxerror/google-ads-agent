/**
 * useClipMath — the single per-model clip arithmetic hook, shared by the NEW
 * AI Video Studio surfaces (canvas + gallery + rail). It answers three
 * questions off one model's `constraints`:
 *
 *   maxClip       — the longest legal single-clip duration for this model
 *                   (enum: max of the allowed values; int: max_duration; else null)
 *   estClips      — how many clips it takes to fill `targetSeconds` at maxClip
 *   clampDuration — snap an arbitrary per-scene duration into a legal value
 *                   (enum: nearest allowed value; int: capped at max_duration)
 *
 * StudioPanel keeps its OWN copy of this math on purpose — this hook is only
 * for the new workspace surfaces; do NOT refactor StudioPanel to use it.
 */

import { useMemo, useCallback } from 'react';
import type { StudioModelInfo } from '@/lib/api';

export function useClipMath(
  modelInfo: StudioModelInfo | undefined,
  targetSeconds: number,
): { maxClip: number | null; estClips: number; clampDuration: (d: number) => number } {
  const c = modelInfo?.constraints;

  const maxClip = useMemo<number | null>(() => {
    if (!c) return null;
    if (c.duration_type === 'enum' && c.durations && c.durations.length) {
      return Math.max(...c.durations);
    }
    if (c.duration_type === 'int' && c.max_duration) {
      return c.max_duration;
    }
    return null;
  }, [c]);

  const estClips = useMemo<number>(() => {
    if (!maxClip) return 1;
    return Math.max(1, Math.ceil(targetSeconds / maxClip));
  }, [maxClip, targetSeconds]);

  const clampDuration = useCallback(
    (d: number): number => {
      if (!c) return d;
      if (c.duration_type === 'enum' && c.durations && c.durations.length) {
        // nearest allowed value by absolute difference, seeded on durations[0]
        return c.durations.reduce(
          (best, cur) => (Math.abs(cur - d) < Math.abs(best - d) ? cur : best),
          c.durations[0],
        );
      }
      if (c.duration_type === 'int' && c.max_duration) {
        return Math.min(d, c.max_duration);
      }
      return d;
    },
    [c],
  );

  return { maxClip, estClips, clampDuration };
}
