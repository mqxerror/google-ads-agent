// Creative Spec Registry — client provider (Epic 14, story 14.5).
//
// The wizards' limits are FETCHED from GET /api/creative/specs, never baked as
// client constants (FR1.2, NFR-D1). Stale-while-revalidate: the last response is
// cached in localStorage and served instantly on mount, so validation renders
// immediately and a slow endpoint never blocks render (NFR-P2). `ready` is true
// as soon as ANY response (cache or network) exists — the wizard disables submit
// ONLY when no specs have EVER been fetched.
//
// There is deliberately NO baked limit number here: before the first-ever fetch,
// the mappers return permissive sentinels (min 0 / max+chars Infinity) so nothing
// falsely shows over-limit, and the wizard's submit stays disabled via `ready`.

import { useQuery } from '@tanstack/react-query';

export interface TextFieldSpec {
  min_count: number;
  max_count: number;
  max_chars: number;
  verified: boolean;
  source: string;
}

export interface ImageSlotSpec {
  slot: string;
  max_count: number;
  required: boolean;
  verified: boolean;
  source: string;
  geometry: null | { aspect: number; min_w: number; min_h: number; label: string };
}

export interface PolicyKnobs {
  on_image_text: string;
  logo_overlay: string;
  video_gate: string;
}

export interface CampaignSpec {
  text: Record<string, TextFieldSpec>;
  images: Record<string, ImageSlotSpec>;
  logos: Record<string, ImageSlotSpec>;
  business_name_max: number;
  total_image_cap: number | null;
  search_themes: [number, number] | null;
  video: {
    max_per_orientation: number | null;
    min_seconds: number | null;
    required: boolean;
    verified: boolean;
    source: string;
  };
  final_url_max: number;
  policy: PolicyKnobs;
  short_description: TextFieldSpec | null;
}

export interface SpecsResponse {
  campaign_types: Record<string, CampaignSpec>;
  engine: { near_dup_threshold: number; batch_tile_cap: number; batch_retry_max: number };
  version: string;
}

const SPECS_URL = '/api/creative/specs';
const LS_KEY = 'creativeSpecs.v1';
export const SPECS_QUERY_KEY = ['creative-specs'] as const;

export function loadSpecsCache(): SpecsResponse | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    const raw = localStorage.getItem(LS_KEY);
    return raw ? (JSON.parse(raw) as SpecsResponse) : null;
  } catch {
    return null;
  }
}

export function saveSpecsCache(data: SpecsResponse): void {
  try {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(LS_KEY, JSON.stringify(data));
  } catch {
    /* private-mode / quota — cache is best-effort */
  }
}

export async function fetchSpecs(): Promise<SpecsResponse> {
  const res = await fetch(SPECS_URL, { headers: { 'Content-Type': 'application/json' } });
  if (!res.ok) throw new Error(`specs ${res.status}`);
  const data = (await res.json()) as SpecsResponse;
  saveSpecsCache(data);
  return data;
}

/** Resolve which specs to use + whether we have EVER fetched (pure, testable). */
export function resolveSpecs(
  queryData: SpecsResponse | undefined,
  cache: SpecsResponse | null,
): { specs: SpecsResponse | null; ready: boolean } {
  const specs = queryData ?? cache ?? null;
  return { specs, ready: specs !== null };
}

// ── wizard rule shapes (mirror the deleted local RULES objects) ───────────────

export interface FieldRule { min: number; max: number; maxChars: number }
export interface SlotRule { min: number; max: number }

export interface DemandGenRules {
  headlines: FieldRule;
  descriptions: FieldRule;
  businessNameMaxChars: number;
  logos: SlotRule;
  imageMax: number;
  ready: boolean;
}

export interface PMaxRules {
  headlines: FieldRule;
  longHeadlines: FieldRule;
  descriptions: FieldRule;
  logos: SlotRule;
  landscape: SlotRule;
  square: SlotRule;
  videos: SlotRule;
  imageMax: number;
  businessNameMaxChars: number;
  searchThemes: { maxCount: number; maxChars: number } | null;
  finalUrlMax: number;
  shortDescriptionMaxChars: number | null;   // soft (verified:false) — warn only
  ready: boolean;
}

const OPEN_FIELD: FieldRule = { min: 0, max: Infinity, maxChars: Infinity };

function fieldRule(t: TextFieldSpec | undefined): FieldRule {
  if (!t) return OPEN_FIELD;
  return { min: t.min_count, max: t.max_count, maxChars: t.max_chars };
}

function slotRule(s: ImageSlotSpec | undefined): SlotRule {
  if (!s) return { min: 0, max: Infinity };
  return { min: s.required ? 1 : 0, max: s.max_count };
}

/** Pure DG mapper — the FR1.2 proof: change a served value, the boundary moves,
 *  with ZERO wizard-code change (the wizard just reads these fields). */
export function dgRulesFromSpecs(specs: SpecsResponse | null): DemandGenRules {
  const s = specs?.campaign_types?.demand_gen;
  return {
    headlines: fieldRule(s?.text?.headlines),
    descriptions: fieldRule(s?.text?.descriptions),
    businessNameMaxChars: s?.business_name_max ?? Infinity,
    logos: slotRule(s?.logos?.logos),
    imageMax: s?.total_image_cap ?? Infinity,
    ready: specs !== null,
  };
}

export function pmaxRulesFromSpecs(specs: SpecsResponse | null): PMaxRules {
  const s = specs?.campaign_types?.pmax;
  const st = s?.search_themes ?? null;
  return {
    headlines: fieldRule(s?.text?.headlines),
    longHeadlines: fieldRule(s?.text?.long_headlines),
    descriptions: fieldRule(s?.text?.descriptions),
    logos: slotRule(s?.logos?.logos),
    landscape: slotRule(s?.images?.landscape),
    square: slotRule(s?.images?.square),
    videos: { min: 0, max: s?.video?.max_per_orientation ?? Infinity },
    imageMax: s?.total_image_cap ?? Infinity,
    businessNameMaxChars: s?.business_name_max ?? Infinity,
    searchThemes: st ? { maxCount: st[0], maxChars: st[1] } : null,
    finalUrlMax: s?.final_url_max ?? Infinity,
    shortDescriptionMaxChars: s?.short_description?.max_chars ?? null,
    ready: specs !== null,
  };
}

// ── hooks ─────────────────────────────────────────────────────────────────────

function useResolvedSpecs(): { specs: SpecsResponse | null; ready: boolean } {
  const cache = loadSpecsCache();
  const { data } = useQuery({
    queryKey: SPECS_QUERY_KEY,
    queryFn: fetchSpecs,
    staleTime: 5 * 60 * 1000,
    initialData: cache ?? undefined,
  });
  return resolveSpecs(data, cache);
}

/** Full registry response (or null before the first-ever fetch). */
export function useCreativeSpecs(): { specs: SpecsResponse | null; ready: boolean } {
  return useResolvedSpecs();
}

export function useDemandGenRules(): DemandGenRules {
  return dgRulesFromSpecs(useResolvedSpecs().specs);
}

export function usePMaxRules(): PMaxRules {
  return pmaxRulesFromSpecs(useResolvedSpecs().specs);
}
