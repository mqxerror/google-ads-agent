// Story 14.6 — PMax client validation mirror.
//
// Mirrors every FR1.4 server rejection in `pmax_orchestrator._validate_bundle`
// so the operator sees an over-limit state inline, never learns of a limit from
// a 422. All limits come from the fetched registry (`PMaxRules`) — no baked
// constant (NFR-D1). Soft (verified:false) rules surface as WARNINGS, never
// blockers (FR1.3), matching the server's warnings channel.
//
// Pure + framework-free so it is directly unit-testable (PMaxWizard.test.tsx).

import type { PMaxRules } from './creativeSpecs';

export interface PMaxValidationInput {
  businessName: string;
  finalUrl: string;
  headlines: string[];
  longHeadlines: string[];
  descriptions: string[];
  logos: string[];
  landscape: string[];
  square: string[];
  portrait: string[];
  audienceSignals: string[];
}

export interface ClientValidation {
  errors: string[];
  warnings: string[];
}

const URL_RE = /^https?:\/\/[^\s/]+\.[^\s]+$/i;

/** Mirror of the server's `is_malformed_url`. */
export function isMalformedUrl(url: string): boolean {
  return !URL_RE.test((url || '').trim());
}

function checkField(
  name: string,
  items: string[],
  rule: { min: number; max: number; maxChars: number },
  errors: string[],
): void {
  const nonEmpty = items.filter(s => s.trim());
  if (nonEmpty.length > rule.max) errors.push(`too many ${name}: ${nonEmpty.length} (max ${rule.max})`);
  if (nonEmpty.length < rule.min) errors.push(`need ≥${rule.min} ${name} (got ${nonEmpty.length})`);
  nonEmpty.forEach((s, i) => {
    if (s.length > rule.maxChars) errors.push(`${name}[${i}] is ${s.length} chars (max ${rule.maxChars})`);
  });
}

export function validatePMax(input: PMaxValidationInput, rules: PMaxRules): ClientValidation {
  const errors: string[] = [];
  const warnings: string[] = [];
  if (!rules.ready) return { errors, warnings };  // no specs yet → don't false-flag

  // business name (FR1.4 gap closure — was unchecked client-side)
  if (input.businessName.length > rules.businessNameMaxChars) {
    errors.push(`business name is ${input.businessName.length} chars (max ${rules.businessNameMaxChars})`);
  }

  // final URL format (FR1.4)
  if (input.finalUrl.trim() && isMalformedUrl(input.finalUrl)) {
    errors.push('malformed final URL — must start with http(s):// and a domain');
  }

  // text fields: min AND max counts + char caps (max_count closes the FR1.4 gap)
  checkField('headlines', input.headlines, rules.headlines, errors);
  checkField('long headlines', input.longHeadlines, rules.longHeadlines, errors);
  checkField('descriptions', input.descriptions, rules.descriptions, errors);

  // soft (FR1.3): ≥1 short (≤N-char) description — WARNING, never a blocker
  if (rules.shortDescriptionMaxChars != null) {
    const descs = input.descriptions.filter(s => s.trim());
    if (descs.length > 0 && !descs.some(s => s.length <= rules.shortDescriptionMaxChars!)) {
      warnings.push(`add ≥1 description ≤${rules.shortDescriptionMaxChars} chars (a short description) for best results`);
    }
  }

  // images summed ACROSS ratio groups (honesty #8 cross-slot meter)
  const totalImages = input.landscape.length + input.square.length + input.portrait.length;
  if (totalImages > rules.imageMax) {
    errors.push(`too many images: ${totalImages} across ratios (max ${rules.imageMax} per asset group)`);
  }
  if (input.logos.length > rules.logos.max) {
    errors.push(`too many logos: ${input.logos.length} (max ${rules.logos.max})`);
  }

  // search themes: ≤maxCount × ≤maxChars (FR1.4)
  if (rules.searchThemes) {
    const themes = input.audienceSignals.map(s => s.trim()).filter(Boolean);
    if (themes.length > rules.searchThemes.maxCount) {
      errors.push(`too many search themes: ${themes.length} (max ${rules.searchThemes.maxCount})`);
    }
    themes.forEach(t => {
      if (t.length > rules.searchThemes!.maxChars) {
        errors.push(`search theme is ${t.length} chars (max ${rules.searchThemes!.maxChars})`);
      }
    });
  }

  return { errors, warnings };
}

/** Cross-slot image total (honesty #8) — exported for the StepImages meter. */
export function totalImagesAcrossRatios(input: Pick<PMaxValidationInput, 'landscape' | 'square' | 'portrait'>): number {
  return input.landscape.length + input.square.length + input.portrait.length;
}
