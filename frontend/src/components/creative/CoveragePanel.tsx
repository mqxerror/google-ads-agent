// CoveragePanel (Epic 16, story 16.7 — text scope · FR5.1) — an HONEST
// completeness meter beside the copy fields. It reframes Ad Strength as
// completeness: filled slots · distinct angles · near-duplicate count. It NEVER
// chases a top Ad-Strength label and never rewards maxing characters — it
// encourages filling slots and varying angles (research #5, PRD FR5.1).
//
// Pure client computation over the bundle + specs + the near-dup detector
// (registry threshold) — zero network. Image-slot coverage is added in P3 (17.7).

import { CheckCircle2, Circle, Copy, Palette } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCreativeSpecs } from '@/lib/creativeSpecs';
import { flaggedRowIndices } from '@/lib/nearDup';
import { textCoverage } from '@/lib/copyRows';

export default function CoveragePanel({
  headlines, headlineAngles, headlinesMax, descriptions, descriptionsMax,
}: {
  headlines: string[];
  headlineAngles: (string | null)[];
  headlinesMax: number;
  descriptions: string[];
  descriptionsMax: number;
}) {
  const { specs } = useCreativeSpecs();
  const threshold = specs?.engine?.near_dup_threshold;
  const nearDupCount = threshold == null
    ? 0
    : flaggedRowIndices(headlines.filter(s => s.trim()), { threshold }).size;

  const cov = textCoverage(
    headlines, headlineAngles, headlinesMax, descriptions, descriptionsMax, nearDupCount,
  );

  return (
    <div className="border border-border rounded-md bg-secondary/20 p-3">
      <p className="text-[11px] font-medium mb-2 text-muted-foreground">Coverage</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <Metric
          icon={cov.headlinesFilled >= 1 ? CheckCircle2 : Circle}
          label="Headlines"
          value={`${cov.headlinesFilled}/${Number.isFinite(cov.headlinesMax) ? cov.headlinesMax : '—'}`}
          hint="fill more slots"
        />
        <Metric
          icon={cov.descriptionsFilled >= 1 ? CheckCircle2 : Circle}
          label="Descriptions"
          value={`${cov.descriptionsFilled}/${Number.isFinite(cov.descriptionsMax) ? cov.descriptionsMax : '—'}`}
          hint="fill more slots"
        />
        <Metric
          icon={Palette}
          label="Distinct angles"
          value={String(cov.distinctAngles)}
          hint="vary the angle"
        />
        <Metric
          icon={Copy}
          label="Near-dupes"
          value={String(cov.nearDupCount)}
          hint={cov.nearDupCount ? 'Diversify to fix' : 'none'}
          tone={cov.nearDupCount ? 'warn' : 'ok'}
        />
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value, hint, tone = 'ok' }: {
  icon: typeof Circle; label: string; value: string; hint: string; tone?: 'ok' | 'warn';
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className={cn('flex items-center gap-1', tone === 'warn' ? 'text-amber-500' : 'text-foreground')}>
        <Icon className="h-3 w-3 shrink-0" />
        <span className="tabular-nums font-medium">{value}</span>
      </div>
      <span className="text-[10px] text-muted-foreground">{label}</span>
      <span className="text-[9px] text-muted-foreground/70">{hint}</span>
    </div>
  );
}
