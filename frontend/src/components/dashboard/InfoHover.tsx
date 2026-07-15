/**
 * InfoHover — the shared "explain this number" primitive (Dashboard v2.1,
 * Clarity Pass / Epic B). A tiny, keyboard-focusable info glyph that, on hover
 * or focus, reveals a small card explaining what a figure means, which window
 * it covers, and any caveats (e.g. conversion-lag restatement).
 *
 * It exists so every metric on the home page can quietly answer "what is this?"
 * without cluttering the surface — metadata, not chrome. DESIGN.md tokens only,
 * no new colours or fonts. Wraps the app's existing Radix tooltip (mounted
 * once via <TooltipProvider> at the App root), so it inherits accessible
 * open/close + focus semantics for free.
 *
 * Usage:
 *   <InfoHover title="Spend">
 *     What you paid, Jul 5–Jul 11 vs Jun 28–Jul 4. ENABLED campaigns only.
 *   </InfoHover>
 */

import { Info } from 'lucide-react';
import { Tooltip as TooltipPrimitive } from 'radix-ui';
import { cn } from '@/lib/utils';

interface InfoHoverProps {
  /** Optional bold heading shown at the top of the hover card. */
  title?: string;
  /** The explanatory content (plain text or small nodes). */
  children: React.ReactNode;
  /** Accessible label for the trigger; defaults to a sensible generic. */
  label?: string;
  /** Extra classes on the trigger (e.g. spacing next to a label). */
  className?: string;
}

export default function InfoHover({ title, children, label, className }: InfoHoverProps) {
  // Built on the raw Radix primitives (not the app's ui/tooltip wrapper) so the
  // hover card can wear the calm surface language DESIGN.md asks for. The wrapper
  // inverts to a dark `bg-foreground` chip with a dark arrow — too heavy for this
  // light app and for a multi-line explainer. The <TooltipProvider> at the App
  // root still supplies the shared accessible open/close + focus semantics.
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger
        type="button"
        aria-label={label ?? (title ? `About ${title}` : 'More information')}
        className={cn(
          'inline-flex items-center justify-center rounded-full text-subtle transition-colors',
          'hover:text-muted-foreground focus-visible:text-muted-foreground focus-visible:outline-none',
          'focus-visible:ring-1 focus-visible:ring-accent',
          className,
        )}
      >
        <Info className="h-3 w-3" aria-hidden />
      </TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side="top"
          align="start"
          sideOffset={4}
          className={cn(
            'z-50 max-w-[248px] origin-(--radix-tooltip-content-transform-origin) rounded-lg',
            'border border-border bg-card px-3 py-2 text-left text-[11px] leading-relaxed text-muted-foreground',
            'shadow-[var(--shadow-elevated)] animate-in fade-in-0 zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
          )}
        >
          {title && (
            <span className="mb-0.5 block text-[11px] font-semibold text-foreground">{title}</span>
          )}
          <span className="block">{children}</span>
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
