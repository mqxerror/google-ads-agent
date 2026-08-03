// TextWorkbench (Epic 15, story 15.6) — the ONE shared text-asset editor for
// every wizard. Extracted VERBATIM from the duplicated `TextList` (canonical copy
// DemandGenWizard.tsx:939-993) so P2 grows one component, not two, then given:
//   - paste-multiline split (FR1.11): pasting N newline-separated lines into one
//     row yields N rows; a pasted line over the field max renders the over-limit
//     state at fieldSpec.max_chars (registry-sourced), never truncated.
//   - an inline near-duplicate badge (FR1.10 client half): deterministic,
//     zero-network, computed on every change from the registry threshold.
//
// The limit props (maxChars / minItems / maxItems) come from the caller's
// useCreativeSpecs()-derived rules — no baked constant here (NFR-D1).

import { useMemo } from 'react';
import { X, Plus, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { useCreativeSpecs } from '@/lib/creativeSpecs';
import { flaggedRowIndices } from '@/lib/nearDup';
import { splitPastedLines } from '@/lib/pasteSplit';

export default function TextWorkbench({
  label, hint, items, onChange, maxChars, minItems, maxItems, placeholder,
}: {
  label: string; hint: string; items: string[]; onChange: (v: string[]) => void;
  maxChars: number; minItems: number; maxItems: number; placeholder?: string;
}) {
  const { specs } = useCreativeSpecs();
  const threshold = specs?.engine?.near_dup_threshold;

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
  const addRow = () => onChange([...items, '']);
  const removeRow = (i: number) => {
    const next = [...items];
    next.splice(i, 1);
    onChange(next.length ? next : ['']);
  };

  // Paste-split (FR1.11): a multi-line paste into row i replaces that row with one
  // row per line (respecting maxItems). Not truncated — over-limit lines show the
  // over-limit state against maxChars. A single-line paste falls through to the
  // normal onChange (which clamps typed input).
  const onPaste = (i: number, e: React.ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData('text');
    if (!text.includes('\n')) return;
    const lines = splitPastedLines(text);
    if (lines.length <= 1) return;
    e.preventDefault();
    const next = [...items];
    next.splice(i, 1, ...lines);
    onChange(next.slice(0, maxItems));
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
            <Input
              value={item}
              onChange={e => setAt(i, e.target.value.slice(0, maxChars))}
              onPaste={e => onPaste(i, e)}
              placeholder={placeholder || `${label} ${i + 1}`}
              className={cn(
                'flex-1 text-sm',
                item.length > maxChars && 'border-red-500',
                flagged.has(i) && 'border-amber-500/60',
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
            <button onClick={() => removeRow(i)} className="p-1 hover:bg-secondary rounded text-muted-foreground" aria-label="Remove">
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
