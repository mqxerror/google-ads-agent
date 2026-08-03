// Copy-Workbench angle taxonomy — frontend single source (Epic 16, story 16.2).
//
// The authoritative angle LIST is served by the backend registry
// (/api/creative/specs → taxonomy.angles, AD-2) and read via useAngles(); this
// module holds only PRESENTATIONAL metadata (short label + chip colour) keyed by
// angle. No component hardcodes the angle list (the string analogue of NFR-D1) —
// they import from here, and here reads the served taxonomy.

import { useCreativeSpecs } from '@/lib/creativeSpecs';

export interface AngleMeta {
  label: string;
  /** Tailwind classes for the chip (light + dark aware via tokens). */
  className: string;
}

// Presentational only — label + colour per angle. The ORDER/LIST of angles is
// NOT authoritative here (that comes from the served taxonomy); this is the
// display palette. Keys mirror creative_specs.ANGLES.
export const ANGLE_META: Record<string, AngleMeta> = {
  promotional:  { label: 'Promo',    className: 'bg-rose-500/15 text-rose-600 dark:text-rose-300' },
  feature:      { label: 'Feature',  className: 'bg-sky-500/15 text-sky-600 dark:text-sky-300' },
  benefit:      { label: 'Benefit',  className: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300' },
  urgency:      { label: 'Urgency',  className: 'bg-amber-500/15 text-amber-600 dark:text-amber-300' },
  social_proof: { label: 'Social',   className: 'bg-violet-500/15 text-violet-600 dark:text-violet-300' },
  aspiration:   { label: 'Aspire',   className: 'bg-fuchsia-500/15 text-fuchsia-600 dark:text-fuchsia-300' },
  specificity:  { label: 'Specific', className: 'bg-teal-500/15 text-teal-600 dark:text-teal-300' },
};

/** Display metadata for an angle (falls back to a neutral chip for unknowns). */
export function angleMeta(angle: string | null | undefined): AngleMeta {
  if (angle && ANGLE_META[angle]) return ANGLE_META[angle];
  return { label: angle || '—', className: 'bg-secondary text-muted-foreground' };
}

/** The authoritative ordered angle list — from the served taxonomy, falling back
 * to the presentational keys before the first specs fetch. */
export function useAngles(): string[] {
  const { specs } = useCreativeSpecs();
  return specs?.taxonomy?.angles ?? Object.keys(ANGLE_META);
}
