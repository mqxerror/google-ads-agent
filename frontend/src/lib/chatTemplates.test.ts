// Shape + invariant guard for the chat template library. Templates are pure
// data consumed by ChatInput's picker (category tabs come from
// TEMPLATE_CATEGORIES, the {campaign} placeholder is filled only when
// needsCampaign is set). This test makes a malformed template fail CI instead
// of silently rendering a broken picker row or an unfilled placeholder.

import { describe, it, expect } from 'vitest';
import templates, { TEMPLATE_CATEGORIES, type ChatTemplate } from './chatTemplates';

const CATEGORY_IDS = new Set(TEMPLATE_CATEGORIES.map((c) => c.id));
const VALID_MODELS = new Set(['fable', 'sonnet', 'opus', 'haiku']);

describe('chat template library', () => {
  it('every template has the required shape', () => {
    for (const t of templates as ChatTemplate[]) {
      expect(t.id, 'id missing').toBeTruthy();
      expect(t.label, `label missing on ${t.id}`).toBeTruthy();
      expect(t.icon, `icon missing on ${t.id}`).toBeTruthy();
      expect(t.description, `description missing on ${t.id}`).toBeTruthy();
      expect(t.prompt, `prompt missing on ${t.id}`).toBeTruthy();
    }
  });

  it('ids are unique', () => {
    const ids = templates.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('every category maps to a real picker tab', () => {
    for (const t of templates) {
      expect(CATEGORY_IDS.has(t.category), `${t.id} has orphan category ${t.category}`).toBe(true);
    }
  });

  it('suggestedModel, when set, is a known model', () => {
    for (const t of templates) {
      if (t.suggestedModel) {
        expect(VALID_MODELS.has(t.suggestedModel), `${t.id} bad model ${t.suggestedModel}`).toBe(true);
      }
    }
  });

  it('needsCampaign and the {campaign} placeholder agree in both directions', () => {
    for (const t of templates) {
      const hasPlaceholder = t.prompt.includes('{campaign}');
      if (t.needsCampaign) {
        expect(hasPlaceholder, `${t.id} needsCampaign but prompt lacks {campaign}`).toBe(true);
      } else {
        expect(hasPlaceholder, `${t.id} has {campaign} but no needsCampaign flag`).toBe(false);
      }
    }
  });

  it('the 2026-08 trends pack is present (8 new templates)', () => {
    const ids = new Set(templates.map((t) => t.id));
    for (const id of [
      'ai-max-readiness',
      'measurement-pipeline-health',
      'deprecation-calendar-check',
      'value-based-bidding-gate',
      'match-type-mix-review',
      'ai-overviews-exposure',
      'benchmark-reality-check',
      'business-agent-leads-watch',
    ]) {
      expect(ids.has(id), `missing new template ${id}`).toBe(true);
    }
  });

  it('the Ad Strength reframe replaced the old label-chasing template', () => {
    const ids = new Set(templates.map((t) => t.id));
    expect(ids.has('asset-diversity-review')).toBe(true);
    expect(ids.has('ad-strength-optimizer')).toBe(false);
    const asset = templates.find((t) => t.id === 'asset-diversity-review')!;
    // The reframe must actively warn against chasing the Ad Strength label.
    expect(asset.prompt).toContain('Ad Strength');
    expect(asset.prompt.toLowerCase()).toContain('not a kpi');
  });

  it('Review Google Recommendations carries the standing auto-apply guard', () => {
    const rec = templates.find((t) => t.id === 'google-recommendations')!;
    expect(rec.prompt).toContain('Auto-apply');
    expect(rec.prompt).toContain('2026-07-25');
  });
});
