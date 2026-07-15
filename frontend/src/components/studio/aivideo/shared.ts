/**
 * Shared helpers for the AI Video Studio surfaces — kept tiny and dependency
 * free so the rail, gallery, canvas and dock can all import them without
 * pulling React state in.
 */

import { useCallback, useEffect, useRef } from 'react';
import type { StudioModelInfo } from '@/lib/api';

/**
 * useDebouncedCallback — fire `fn` at most once per `delay` ms of quiet. The
 * pending timer is cleared on unmount so no stray persist fires after teardown.
 */
export function useDebouncedCallback<A extends unknown[]>(
  fn: (...args: A) => void,
  delay: number,
): (...args: A) => void {
  const timer = useRef<number | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
    },
    [],
  );

  return useCallback(
    (...args: A) => {
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => fnRef.current(...args), delay);
    },
    [delay],
  );
}

/** Tier sort order (TIER_ORDER is not exported from ModelPicker — local copy). */
export const TIER_ORDER: Record<string, number> = { 'Best quality': 0, Fast: 1, Budget: 2 };

/** Fallback provenance from the model id when `model.origin` is absent. */
export function originFallback(id: string): string | null {
  if (/^(kling|seedance|minimax|hailuo|wan)/.test(id)) return 'Chinese';
  if (/^(veo|grok)/.test(id)) return 'American';
  if (/soul/.test(id)) return 'Soul';
  return null;
}

/** The origin line to show under a model chip: real value first, then fallback. */
export function originLine(m: StudioModelInfo): string | null {
  return m.origin ?? originFallback(m.id);
}

/** Whether a model can carry a Brand Avatar (Soul). */
export function isSoulCapable(m: StudioModelInfo | undefined): boolean {
  if (!m) return false;
  return m.id === 'soul_cast' || m.id === 'text2image_soul_v2' || !!m.constraints?.supports_soul;
}

/** Human clip-window label, e.g. "Clips: 4 / 6 / 8s (enum)" or "up to 10s". */
export function clipWindowLabel(m: StudioModelInfo): string {
  const c = m.constraints;
  if (c?.duration_type === 'enum' && c.durations?.length) {
    return `Clips: ${c.durations.join(' / ')}s (enum)`;
  }
  if (c?.duration_type === 'int' && c.max_duration) {
    return `up to ${c.max_duration}s`;
  }
  return 'clip length fixed by model';
}
