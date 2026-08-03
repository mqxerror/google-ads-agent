// PolicyHintCard (Epic 16, story 16.5) — extracted 1:1 from DemandGenWizard's
// PolicyHint so BOTH wizards surface the same compliance reminder from ONE
// component (FR1.12). Not enforced client-side (the account's own policy differs)
// — just the policy traps that get ads disapproved.

import { ShieldAlert } from 'lucide-react';

export default function PolicyHintCard() {
  return (
    <div className="border border-amber-500/30 bg-amber-500/5 rounded-md p-3 text-[11px] leading-relaxed">
      <div className="flex items-start gap-2">
        <ShieldAlert className="h-3.5 w-3.5 text-amber-500 mt-0.5 shrink-0" />
        <p className="text-muted-foreground">
          <b className="text-foreground">Policy hints:</b> no prices or discounts in the copy · no citizenship / guaranteed-approval
          {' '}promises · avoid the symbols <span className="font-mono">~ | +</span> (Google flags them as gimmicky punctuation).
        </p>
      </div>
    </div>
  );
}
