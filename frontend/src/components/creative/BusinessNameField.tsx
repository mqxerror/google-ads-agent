// BusinessNameField (Epic 16, story 16.5) — extracted 1:1 from DemandGenWizard's
// StepBrief so BOTH wizards get the live business-name counter from ONE component
// (FR1.12). The char cap comes from the caller (useCreativeSpecs-derived rules) —
// no baked constant here (NFR-D1).

import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';

export default function BusinessNameField({
  value, onChange, max, placeholder = 'Mercan',
}: {
  value: string;
  onChange: (v: string) => void;
  max: number;
  placeholder?: string;
}) {
  const over = value.length > max;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs font-medium">Business name *</label>
        <span className={cn('text-[10px] tabular-nums', over ? 'text-red-500' : 'text-muted-foreground')}>
          {value.length}/{Number.isFinite(max) ? max : '—'}
        </span>
      </div>
      <Input
        value={value}
        onChange={e => onChange(Number.isFinite(max) ? e.target.value.slice(0, max) : e.target.value)}
        placeholder={placeholder}
        className={cn(over && 'border-red-500')}
      />
      <p className="text-[10px] text-muted-foreground mt-1">
        Shown on the ad; keep it short and brand-faithful{Number.isFinite(max) ? ` (≤${max} chars)` : ''}.
      </p>
    </div>
  );
}
