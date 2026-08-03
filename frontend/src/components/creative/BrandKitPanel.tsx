// BrandKitPanel (Epic 18, story 18.5 · FR5.2/FR5.3) — the research surface that
// sits BESIDE CoveragePanel so computed intelligence stops dying in a prompt.
//
// "Analyze landing page" scrapes the operator-owned URL once (POST
// /api/creative/brand-kit): brand-kit assets land in the library (pickable in the
// existing LibraryPicker/AssetLibrary — unchanged), and the rationale
// (value_prop · audience · tone · claim_hints) renders here. Suggested audiences
// become ONE-CLICK search themes (PMax), appended under the registry ≤25 cap,
// idempotently. Absent research → an HONEST empty state, never placeholders.

import { useState } from 'react';
import {
  Sparkles, Loader2, AlertCircle, Plus, Check, Palette, Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { appendSearchTheme, hasTheme, type BrandKitResult } from '@/lib/brandKit';

export interface ThemeTarget {
  themes: string[];
  maxItems: number;
  maxChars: number;
  onChange: (themes: string[]) => void;
}

export default function BrandKitPanel({
  accountId, finalUrl, campaignId, themeTarget,
}: {
  accountId: string;
  finalUrl: string;
  campaignId?: string;
  /** When provided (PMax search themes), suggested audiences become one-click. */
  themeTarget?: ThemeTarget;
}) {
  const [kit, setKit] = useState<BrandKitResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ownConfirmed, setOwnConfirmed] = useState(false);

  const analyze = async () => {
    if (!finalUrl.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/creative/brand-kit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: finalUrl.trim(),
          account_id: accountId || null,
          campaign_id: campaignId || null,
          confirm_ownership: ownConfirmed,
          include_research: true,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body?.detail?.message || body?.detail || `HTTP ${res.status}`);
      }
      setKit(body as BrandKitResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const research = kit?.research ?? null;

  return (
    <div className="border border-border rounded-md bg-secondary/20 p-3 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <Sparkles className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
          <div>
            <p className="text-xs font-medium">Brand kit &amp; research</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Scrape your landing page for brand assets + audience research. Assets land in
              your library; the research grounds the copy below.
            </p>
          </div>
        </div>
        <Button
          size="sm" variant="outline" onClick={analyze}
          disabled={loading || !finalUrl.trim()}
          className="gap-1.5 shrink-0"
          title={finalUrl.trim() ? 'Scrape the landing page' : 'Set the Final URL first'}
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          {loading ? 'Analyzing…' : kit ? 'Re-analyze' : 'Analyze landing page'}
        </Button>
      </div>

      <label className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
        <input
          type="checkbox" checked={ownConfirmed}
          onChange={e => setOwnConfirmed(e.target.checked)}
          className="h-3 w-3 accent-primary"
        />
        I own this page (required for pages outside the owned-domains allowlist)
      </label>

      {error && (
        <p className="flex items-start gap-1.5 text-[11px] text-red-500">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" /> {error}
        </p>
      )}

      {/* Kit summary — colors + brand + a note that assets landed in the library */}
      {kit && (
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            {kit.brand_name && (
              <span className="text-xs font-medium">{kit.brand_name}</span>
            )}
            {kit.colors.length > 0 && (
              <span className="flex items-center gap-1">
                <Palette className="h-3 w-3 text-muted-foreground" />
                {kit.colors.slice(0, 6).map(c => (
                  <span
                    key={c.hex} title={`${c.hex} · ${c.role}`}
                    className="h-4 w-4 rounded border border-border"
                    style={{ backgroundColor: c.hex }}
                  />
                ))}
              </span>
            )}
          </div>
          <p className="text-[10px] text-muted-foreground">
            {(kit.logo_asset_id ? 1 : 0) + kit.hero_images.length} asset
            {(kit.logo_asset_id ? 1 : 0) + kit.hero_images.length === 1 ? '' : 's'} added to
            your library — pick them from the image slots below.
          </p>
          {kit.partial && (
            <p className="flex items-start gap-1.5 text-[10px] text-amber-500">
              <Info className="h-3 w-3 shrink-0 mt-0.5" />
              Partial extraction — {kit.missing_fields.join(', ')} unavailable without a
              browser renderer (static parse only).
            </p>
          )}
        </div>
      )}

      {/* Rationale — value_prop / audience / tone / claim_hints, or empty state */}
      {kit && !research && (
        <p className="text-[11px] text-muted-foreground italic">
          No audience research was derived for this page.
        </p>
      )}
      {research && (
        <div className="space-y-1.5 border-t border-border pt-2">
          <Rationale label="Value prop" value={research.value_prop} />
          <Rationale label="Audience" value={research.audience} />
          <Rationale label="Tone" value={research.tone} />
          {research.claim_hints.length > 0 && (
            <div className="text-[11px]">
              <span className="text-muted-foreground">Claim hints: </span>
              <span>{research.claim_hints.join(' · ')}</span>
            </div>
          )}

          {/* One-click suggested audiences → search themes (FR5.3) */}
          {themeTarget && research.suggested_audiences.length > 0 && (
            <div className="pt-1">
              <p className="text-[10px] text-muted-foreground mb-1">
                Suggested audiences — click to add as a search theme
                {' '}({themeTarget.themes.filter(t => t.trim()).length}/{themeTarget.maxItems}):
              </p>
              <div className="flex flex-wrap gap-1.5">
                {research.suggested_audiences.map(sug => {
                  const truncated = sug.slice(0, themeTarget.maxChars);
                  const added = hasTheme(themeTarget.themes, truncated);
                  const atCap = themeTarget.themes.filter(t => t.trim()).length >= themeTarget.maxItems;
                  return (
                    <button
                      key={sug} type="button"
                      disabled={!added && atCap}
                      onClick={() => themeTarget.onChange(
                        appendSearchTheme(themeTarget.themes, sug, {
                          maxItems: themeTarget.maxItems, maxChars: themeTarget.maxChars,
                        }),
                      )}
                      className={cn(
                        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors',
                        added
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border hover:border-primary/50',
                        !added && atCap && 'opacity-40 cursor-not-allowed',
                      )}
                      title={added ? 'Already added' : truncated}
                    >
                      {added ? <Check className="h-2.5 w-2.5" /> : <Plus className="h-2.5 w-2.5" />}
                      <span className="max-w-[180px] truncate">{truncated}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Rationale({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="text-[11px]">
      <span className="text-muted-foreground">{label}: </span>
      <span>{value}</span>
    </div>
  );
}
