/**
 * TypePreview (D3, plan §7.2) — a static styled preview of the Headline /
 * Subhead / CTA type hierarchy, mirroring the mercan-hero Hyperframes
 * template's core type stack. It is a PREVIEW OF HIERARCHY, not a
 * pixel-perfect GSAP simulation (hence the honest "type preview" label).
 *
 * Font-stack + scale rules mirrored ONCE from
 * backend/hyperframes/video-projects/mercan-hero/index.html:
 *   - Inter, weight 900, uppercase, letter-spacing -0.01em for the headline
 *   - gold accent #c9a84c (brand rule + underline + brand mark)
 *   - dark navy → black radial+linear gradient canvas, gold radial glow
 *   - brand mark: weight 800, letter-spacing 0.18em, gold
 *   - tagline/subhead: weight 600, letter-spacing 0.22em, muted light
 *
 * The template canvas itself is intentionally dark (it's a rendered video
 * frame, not app chrome) — the DESIGN.md light-mode law governs the APP
 * surface around it, and this panel is explicitly labelled as a preview of
 * the video output. This is the one place a dark surface is legitimate: it
 * is a fidelity preview of the actual render, wrapped in a token-clean
 * app-surface frame. Type scales down responsively to fit the preview box.
 */

import { cn } from '@/lib/utils';

// mercan-hero template palette (the render output, not app chrome)
const GOLD = '#c9a84c';

export function TypePreview({
  headline, subhead, cta, statValue, statLabel, aspect,
}: {
  headline: string;
  subhead: string;
  cta: string;
  statValue?: string;
  statLabel?: string;
  aspect?: '16:9' | '9:16' | '1:1';
}) {
  const ratioClass =
    aspect === '9:16' ? 'aspect-[9/16] max-w-[240px] mx-auto'
    : aspect === '1:1' ? 'aspect-square'
    : 'aspect-video';

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="label-section">Type preview</span>
        <span className="text-[10px] text-muted-foreground font-mono">approximate hierarchy, not the render</span>
      </div>
      <div
        className={cn(
          'relative w-full rounded-lg overflow-hidden border border-border',
          'shadow-[var(--shadow-resting)] flex items-center justify-center',
          ratioClass,
        )}
        style={{
          // Cinematic dark navy → black with gold radial glow upper-right
          // (mirrors mercan-hero #root background).
          background:
            'radial-gradient(ellipse 60% 60% at 78% 25%, rgba(201,168,76,0.18), transparent 70%),' +
            'linear-gradient(180deg, #013160 0%, #0a1628 70%, #050b13 100%)',
          fontFamily: "'Inter', -apple-system, sans-serif",
        }}
      >
        {/* Brand mark top-left (weight 800, letter-spacing 0.18em, gold) */}
        <div
          className="absolute top-3 left-4 text-[9px] font-extrabold uppercase"
          style={{ color: GOLD, letterSpacing: '0.18em' }}
        >
          {subhead ? '' : null}
        </div>

        {/* Centered headline block */}
        <div className="px-5 text-center w-full" style={{ transform: 'translateY(-6%)' }}>
          <div
            className="uppercase leading-[1.06]"
            style={{
              color: '#ffffff',
              fontWeight: 900,
              letterSpacing: '-0.01em',
              // Scale roughly with the box (clamp keeps it readable in the panel).
              fontSize: 'clamp(16px, 4.5vw, 34px)',
              textShadow: '0 2px 12px rgba(0,0,0,0.45)',
            }}
          >
            {headline || 'Your Headline Here'}
          </div>

          {/* Gold underline (centered, draws from 0 in the real render) */}
          <div className="mx-auto mt-3" style={{ width: 64, height: 3, background: GOLD }} />

          {/* Tagline / subhead (weight 600, letter-spacing 0.22em, muted light) */}
          {subhead && (
            <div
              className="mt-3 uppercase"
              style={{ color: '#d8d8d8', fontWeight: 600, letterSpacing: '0.18em', fontSize: 'clamp(9px, 1.6vw, 13px)' }}
            >
              {subhead}
            </div>
          )}

          {/* Stat line (secondary emphasis) */}
          {(statValue || statLabel) && (
            <div className="mt-3 flex items-baseline justify-center gap-2">
              {statValue && (
                <span style={{ color: GOLD, fontWeight: 800, fontSize: 'clamp(14px, 3vw, 24px)' }}>{statValue}</span>
              )}
              {statLabel && (
                <span className="uppercase" style={{ color: '#b8c2cc', fontWeight: 600, letterSpacing: '0.12em', fontSize: 'clamp(8px, 1.3vw, 11px)' }}>{statLabel}</span>
              )}
            </div>
          )}

          {/* CTA chip */}
          {cta && (
            <div className="mt-4 inline-flex">
              <span
                className="px-3 py-1.5 rounded-md uppercase"
                style={{ background: GOLD, color: '#0a1628', fontWeight: 700, letterSpacing: '0.06em', fontSize: 'clamp(9px, 1.5vw, 12px)' }}
              >
                {cta}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
