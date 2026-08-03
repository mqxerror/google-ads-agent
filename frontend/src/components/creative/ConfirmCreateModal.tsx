// ConfirmCreateModal (Epic 16, story 16.5) — extracted 1:1 from DemandGenWizard's
// confirm-before-create modal so BOTH wizards gate the create the same way
// (FR1.12 · demo step 6). Reassures the operator the campaign starts PAUSED.

import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ConfirmCreateModal({
  open, onCancel, onConfirm, campaignType, campaignName, dailyBudget, icon,
}: {
  open: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  /** e.g. "Performance Max" / "Demand Gen" — names the campaign type in the copy. */
  campaignType: string;
  campaignName: string;
  dailyBudget: string;
  /** Optional leading icon element (the wizard's own type glyph). */
  icon?: React.ReactNode;
}) {
  if (!open) return null;
  const budget = parseFloat(dailyBudget || '0').toFixed(2);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-md border border-border rounded-lg bg-card p-6 shadow-lg">
        <h3 className="text-base font-semibold flex items-center gap-2 mb-2">
          {icon}
          Create this {campaignType} campaign?
        </h3>
        <p className="text-sm text-muted-foreground mb-4">
          <strong className="text-foreground">“{campaignName}”</strong> will be created in Google Ads at
          {' '}<strong className="text-foreground">${budget}/day</strong>.
          It will start <strong className="text-foreground">PAUSED</strong> — no spend until you enable it in the Google Ads UI.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>Cancel</Button>
          <Button size="sm" onClick={onConfirm} className="gap-1.5">
            <Sparkles className="h-3.5 w-3.5" /> Yes, create (PAUSED)
          </Button>
        </div>
      </div>
    </div>
  );
}
