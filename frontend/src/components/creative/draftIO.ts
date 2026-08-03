// Draft export / import (Epic 15, story 15.5 · FR4.5).
//
// A draft doubles as a TEMPLATE: export the wizard bundle to a JSON file, import
// it into a (possibly fresh) wizard to reproduce the state — the Panama bundle
// becomes the Greece bundle in one import. Pure + framework-free so the round-trip
// and the client-side over-limit surfacing are unit-testable without a DOM.

import type { CampaignSpec, SpecsResponse } from '@/lib/creativeSpecs';

export interface DraftFile<B = unknown> {
  format: 'unified-creative-draft';
  version: number;
  campaign_type: string;
  exported_at: string;
  bundle: B;
}

/** Serialize a wizard bundle to the interchange JSON (pretty-printed). */
export function serializeDraft<B>(campaignType: string, bundle: B): string {
  const file: DraftFile<B> = {
    format: 'unified-creative-draft',
    version: 1,
    campaign_type: campaignType,
    exported_at: new Date().toISOString(),
    bundle,
  };
  return JSON.stringify(file, null, 2);
}

/** Parse an imported file. Accepts either the wrapped {format, bundle} shape or
 * a bare bundle object (back-compat). Throws a friendly Error on bad JSON — the
 * caller shows it, never crashes (FR4.5). */
export function parseDraft<B>(text: string): { campaignType: string | null; bundle: B } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error('Not valid JSON — pick a draft file exported from this wizard.');
  }
  if (parsed === null || typeof parsed !== 'object') {
    throw new Error('Draft file must be a JSON object.');
  }
  const obj = parsed as Record<string, unknown>;
  if ('bundle' in obj && obj.bundle && typeof obj.bundle === 'object') {
    return {
      campaignType: typeof obj.campaign_type === 'string' ? obj.campaign_type : null,
      bundle: obj.bundle as B,
    };
  }
  // Bare bundle object.
  return { campaignType: null, bundle: parsed as B };
}

/** Lightweight client-side re-validation of an imported bundle against the
 * fetched registry (useCreativeSpecs). Mirrors the fields the server's
 * validate_draft_bundle checks; ADVISORY — an over-limit import surfaces these,
 * never blocks (the server re-validates on save). No baked limit here — every
 * number comes from the passed spec. */
export function bundleIssues(
  bundle: Record<string, unknown> | null | undefined,
  spec: CampaignSpec | undefined,
): string[] {
  if (!spec || !bundle) return [];
  const issues: string[] = [];
  const asList = (v: unknown): string[] =>
    Array.isArray(v) ? v.filter((s): s is string => typeof s === 'string' && s.trim() !== '') : [];

  const textMap: Record<string, unknown> = {
    headlines: bundle.headlines,
    long_headlines: bundle.longHeadlines ?? bundle.long_headlines,
    descriptions: bundle.descriptions,
  };
  for (const [name, fs] of Object.entries(spec.text)) {
    const items = asList(textMap[name]);
    items.forEach((t, i) => {
      if (t.length > fs.max_chars) issues.push(`${name}[${i}] is ${t.length} chars (max ${fs.max_chars})`);
    });
    if (items.length > fs.max_count) issues.push(`too many ${name}: ${items.length} (max ${fs.max_count})`);
  }
  const bn = bundle.business_name ?? bundle.businessName;
  if (typeof bn === 'string' && bn.length > spec.business_name_max) {
    issues.push(`business_name is ${bn.length} chars (max ${spec.business_name_max})`);
  }
  return issues;
}

/** Resolve one campaign type's spec out of the full specs response. */
export function specFor(specs: SpecsResponse | null, campaignType: string): CampaignSpec | undefined {
  return specs?.campaign_types?.[campaignType];
}
