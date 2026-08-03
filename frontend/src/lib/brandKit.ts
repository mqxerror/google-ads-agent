// Brand-kit client types + the one-click search-theme append helper (Epic 18,
// story 18.5 · FR5.2/FR5.3). Pure + unit-tested: the append respects the
// registry cap (≤max items), truncates to the per-theme char cap, and is
// IDEMPOTENT (a second click on the same suggestion never adds a duplicate).

export interface BrandColor {
  hex: string;
  role: string;
  frequency: number;
}

export interface BrandKitResearch {
  value_prop: string | null;
  audience: string | null;
  tone: string | null;
  claim_hints: string[];
  suggested_audiences: string[];
}

export interface BrandKitResult {
  brand_name: string | null;
  logo_url: string | null;
  logo_asset_id: string | null;
  favicon_url: string | null;
  colors: BrandColor[];
  fonts: string[];
  hero_images: string[];
  claims: string[];
  claims_dropped: { claim: string; banned_phrase: string }[];
  partial: boolean;
  missing_fields: string[];
  kit_asset_id: string;
  research_hash: string;
  research: BrandKitResearch | null;
}

/**
 * Append a suggested audience as a search theme (FR5.3). Pure + deterministic:
 *  - trims + truncates to `maxChars` (the registry per-theme char cap);
 *  - IDEMPOTENT — a theme already present (case-insensitive) is a no-op;
 *  - respects the registry `maxItems` cap — at the cap, returns unchanged.
 * Empty placeholder rows are dropped from the result (the wizard re-adds a blank
 * input row for display), so the count reflects real themes only.
 */
export function appendSearchTheme(
  themes: string[],
  theme: string,
  opts: { maxItems: number; maxChars: number },
): string[] {
  const clean = theme.trim().slice(0, opts.maxChars).trim();
  if (!clean) return themes;
  const nonEmpty = themes.filter(t => t.trim());
  if (nonEmpty.some(t => t.trim().toLowerCase() === clean.toLowerCase())) {
    return themes; // idempotent — no duplicate theme
  }
  if (nonEmpty.length >= opts.maxItems) {
    return themes; // registry cap respected
  }
  return [...nonEmpty, clean];
}

/** True when the theme is already in the list (drives the chip's "added" state). */
export function hasTheme(themes: string[], theme: string): boolean {
  const clean = theme.trim().toLowerCase();
  return themes.some(t => t.trim().toLowerCase() === clean);
}
