// TextWorkbench (Epic 15 story 15.6, extended Epic 16 stories 16.2/16.3) — the ONE
// shared text-asset editor for every wizard. Extracted VERBATIM from the
// duplicated `TextList` (DemandGenWizard.tsx:939-993), then given:
//   - paste-multiline split (FR1.11): pasting N lines into one row yields N rows,
//     over-limit lines show the over-limit state at fieldSpec.max_chars.
//   - an inline near-duplicate badge (FR1.10 client half): deterministic, zero-
//     network, from the registry threshold.
//   - OPTIONAL angle chips + per-row lock + per-row AI rewrite (Epic 16): when the
//     caller passes parallel `angles`/`locked` arrays, each row wears an AngleChip
//     dropdown (pick a target angle → rewrite that row toward it, FR1.8/1.9) and a
//     lock toggle (a locked row is excluded from Diversify's regenerate set, FR1.8).
//
// Backward-compatible: callers that don't pass angle/lock props (e.g. the PMax
// video-id list) get exactly the old editor. Limit props come from the caller's
// useCreativeSpecs()-derived rules — no baked constant here (NFR-D1).

import { useMemo, useState } from 'react';
import { X, Plus, Copy, Lock, Unlock, Wand2, ChevronDown, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { useCreativeSpecs } from '@/lib/creativeSpecs';
import { flaggedRowIndices } from '@/lib/nearDup';
import { splitPastedLines } from '@/lib/pasteSplit';
import { spliceMeta } from '@/lib/copyRows';
import { angleMeta } from '@/lib/angles';

export default function TextWorkbench({
  label, hint, items, onChange, maxChars, minItems, maxItems, placeholder,
  angles, locked, onMetaChange, onRewriteRow, rewritingRow, angleOptions,
}: {
  label: string; hint: string; items: string[]; onChange: (v: string[]) => void;
  maxChars: number; minItems: number; maxItems: number; placeholder?: string;
  // ── Epic 16 optional angle/lock/rewrite layer (parallel to `items`) ──
  angles?: (string | null)[];
  locked?: boolean[];
  /** Called with the RE-ALIGNED meta arrays whenever rows or locks change, so the
   * caller keeps text + angle + lock in lockstep. Present ⇒ angle UI renders. */
  onMetaChange?: (angles: (string | null)[], locked: boolean[]) => void;
  /** Rewrite row `i` toward `targetAngle` (FR1.9). Present ⇒ rewrite UI renders. */
  onRewriteRow?: (index: number, targetAngle: string) => void;
  /** Index currently being rewritten (spinner on that row), or null. */
  rewritingRow?: number | null;
  /** The angle menu (from useAngles()); required for the rewrite dropdown. */
  angleOptions?: string[];
}) {
  const { specs } = useCreativeSpecs();
  const threshold = specs?.engine?.near_dup_threshold;
  const [openMenu, setOpenMenu] = useState<number | null>(null);

  const showAngles = !!onMetaChange && Array.isArray(angles);
  const ang = angles ?? [];
  const lock = locked ?? [];

  // Deterministic near-dup detection over the current rows — no LLM, no network,
  // recomputed only when rows (or the registry threshold) change (NFR-P1).
  const flagged = useMemo(() => {
    if (threshold == null) return new Set<number>();
    return flaggedRowIndices(items, { threshold });
  }, [items, threshold]);

  const setAt = (i: number, val: string) => {
    const next = [...items];
    next[i] = val;
    onChange(next);
  };
  const addRow = () => {
    onChange([...items, '']);
    if (showAngles) onMetaChange!(spliceMeta(ang, items.length, 0, 1, null),
                                  spliceMeta(lock, items.length, 0, 1, false));
  };
  const removeRow = (i: number) => {
    const next = [...items];
    next.splice(i, 1);
    const cleared = next.length ? next : [''];
    onChange(cleared);
    if (showAngles) {
      const a = spliceMeta(ang, i, 1, next.length ? 0 : 1, null);
      const l = spliceMeta(lock, i, 1, next.length ? 0 : 1, false);
      onMetaChange!(a, l);
    }
  };
  const toggleLock = (i: number) => {
    if (!showAngles) return;
    const l = [...lock];
    l[i] = !l[i];
    onMetaChange!(ang, l);
  };

  // Paste-split (FR1.11): a multi-line paste into row i replaces that row with one
  // row per line (respecting maxItems). Over-limit lines show the over-limit state.
  const onPaste = (i: number, e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData('text');
    if (!text.includes('\n')) return;
    const lines = splitPastedLines(text);
    if (lines.length <= 1) return;
    e.preventDefault();
    const next = [...items];
    next.splice(i, 1, ...lines);
    const capped = next.slice(0, maxItems);
    onChange(capped);
    if (showAngles) {
      const insertN = Math.min(lines.length, maxItems - i);
      onMetaChange!(spliceMeta(ang, i, 1, insertN, null),
                    spliceMeta(lock, i, 1, insertN, false));
    }
  };

  const filled = items.filter(s => s.trim()).length;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs font-medium">{label}</label>
        <span className={cn('text-[10px]', filled < minItems ? 'text-amber-500' : 'text-muted-foreground')}>
          {filled}/{minItems} min · {hint}
        </span>
      </div>
      {flagged.size > 0 && (
        <p className="text-[10px] text-amber-500 mb-1.5 flex items-center gap-1">
          <Copy className="h-3 w-3" />
          {flagged.size} near-duplicate {flagged.size === 1 ? 'row' : 'rows'} — vary the angle for better coverage
        </p>
      )}
      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            {showAngles && (
              <AngleControl
                angle={ang[i] ?? null}
                open={openMenu === i}
                busy={rewritingRow === i}
                canRewrite={!!onRewriteRow}
                options={angleOptions ?? []}
                onToggle={() => setOpenMenu(openMenu === i ? null : i)}
                onPick={(a) => { setOpenMenu(null); onRewriteRow?.(i, a); }}
              />
            )}
            <Input
              value={item}
              onChange={e => setAt(i, e.target.value.slice(0, maxChars))}
              onPaste={e => onPaste(i, e)}
              placeholder={placeholder || `${label} ${i + 1}`}
              className={cn(
                'flex-1 text-sm',
                item.length > maxChars && 'border-red-500',
                flagged.has(i) && 'border-amber-500/60',
                showAngles && lock[i] && 'opacity-70',
              )}
            />
            {flagged.has(i) && (
              <span
                title="Near-duplicate of another row — vary the angle"
                className="text-[10px] text-amber-500 flex items-center gap-0.5 shrink-0"
              >
                <Copy className="h-3 w-3" /> dup
              </span>
            )}
            <span className={cn(
              'text-[10px] tabular-nums w-12 text-right',
              item.length > maxChars * 0.9 ? 'text-amber-500' : 'text-muted-foreground',
            )}>
              {item.length}/{maxChars}
            </span>
            {showAngles && (
              <button
                onClick={() => toggleLock(i)}
                className={cn('p-1 rounded shrink-0', lock[i] ? 'text-primary' : 'text-muted-foreground hover:bg-secondary')}
                aria-label={lock[i] ? 'Unlock row (allow regenerate)' : 'Lock row (keep during Diversify)'}
                title={lock[i] ? 'Locked — kept during Diversify' : 'Lock to keep this row during Diversify'}
              >
                {lock[i] ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
              </button>
            )}
            <button onClick={() => removeRow(i)} className="p-1 hover:bg-secondary rounded text-muted-foreground shrink-0" aria-label="Remove">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        {items.length < maxItems && (
          <button onClick={addRow} className="text-xs text-primary hover:underline flex items-center gap-1">
            <Plus className="h-3 w-3" /> Add another
          </button>
        )}
      </div>
    </div>
  );
}

/** Per-row angle chip that doubles as the rewrite/regenerate-by-angle control
 * (FR1.8/1.9): shows the row's current angle; clicking opens a menu of target
 * angles; picking one rewrites the row toward it. */
function AngleControl({
  angle, open, busy, canRewrite, options, onToggle, onPick,
}: {
  angle: string | null; open: boolean; busy: boolean; canRewrite: boolean;
  options: string[]; onToggle: () => void; onPick: (angle: string) => void;
}) {
  const meta = angleMeta(angle);
  return (
    <div className="relative shrink-0">
      <button
        type="button"
        onClick={canRewrite ? onToggle : undefined}
        disabled={busy}
        title={canRewrite ? 'Rewrite this row toward a chosen angle' : (angle || 'angle')}
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium w-[68px] justify-center',
          meta.className, canRewrite && 'cursor-pointer hover:brightness-110',
        )}
      >
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : (
          <>
            <span className="truncate">{meta.label}</span>
            {canRewrite && <ChevronDown className="h-2.5 w-2.5 shrink-0" />}
          </>
        )}
      </button>
      {open && canRewrite && (
        <div className="absolute z-20 mt-1 left-0 w-36 rounded-md border border-border bg-card shadow-lg p-1">
          <p className="text-[9px] text-muted-foreground px-1.5 py-1 flex items-center gap-1">
            <Wand2 className="h-2.5 w-2.5" /> Rewrite toward…
          </p>
          {options.map(opt => (
            <button
              key={opt}
              type="button"
              onClick={() => onPick(opt)}
              className={cn(
                'w-full text-left text-[11px] rounded px-1.5 py-1 hover:bg-secondary flex items-center gap-1.5',
                opt === angle && 'font-semibold',
              )}
            >
              <span className={cn('inline-block h-2 w-2 rounded-full', angleMeta(opt).className)} />
              {angleMeta(opt).label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
