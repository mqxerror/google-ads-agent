/**
 * ConversionGoalField — shared conversion-goal selector for the campaign wizards
 * (Demand Gen · PMax · RDA). Task #49.
 *
 * The whole feature lives here once so the three wizards stay thin (the RDA
 * wizard is a line-capped shell): each renders just
 *   <ConversionGoalField accountId value onChange />
 * on its Brief & budget step.
 *
 * WHY it exists: every wizard-created campaign otherwise inherits the account's
 * default goals (PURCHASE, app DOWNLOAD, CONTACT, SUBMIT_LEAD_FORM… all biddable
 * at once), which mixes categories and makes bidding optimise for the wrong
 * thing. This dropdown lets the operator pick ONE live conversion action up
 * front. The backend then wraps it in a custom goal, sets it CAMPAIGN-level, and
 * clears the inherited category rows in the same create flow.
 *
 * The list shows each ENABLED action with its 30-day conversion count so the
 * operator picks the LIVE one ("Canada Descent Lead — 69 conv/30d") over a
 * zombie ("[DEPRECATED]… — 0 conv/30d"). It forces a conscious choice: the
 * caller keeps Next disabled until `value` is non-empty, and the explicit
 * "Account default goals" option is labelled "not recommended".
 */

import { useState, useEffect } from 'react';
import { Target, Loader2, AlertTriangle } from 'lucide-react';

/** Sentinel the wizard stores + submits for the explicit account-default opt-out
 *  (mirrors backend ACCOUNT_DEFAULT). Kept out of the numeric-id space. */
export const ACCOUNT_DEFAULT_GOAL = 'ACCOUNT_DEFAULT';

/** Window (days) for the conversion-count column shown next to each action. */
const WINDOW_DAYS = 30;

interface ConversionActionOption {
  id: string;
  name: string;
  type: string;
  category: string;
  conversions: number;
  primary_for_goal: boolean;
}

interface Props {
  accountId: string;
  /** '' = unchosen (forces a choice) · ACCOUNT_DEFAULT · a numeric action id. */
  value: string;
  /** (id, humanLabel) — the label is stored so the Review step can show it
   *  without re-fetching. */
  onChange: (id: string, label: string) => void;
}

/** The Review-step / label text for a stored value, resolvable without the
 *  fetched list (used by wizards on their Review step). */
export function conversionGoalLabel(value: string, fallback: string): string {
  if (!value) return 'Not selected';
  if (value === ACCOUNT_DEFAULT_GOAL) return 'Account default goals (not recommended)';
  return fallback || `Conversion action #${value}`;
}

export default function ConversionGoalField({ accountId, value, onChange }: Props) {
  const [options, setOptions] = useState<ConversionActionOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accountId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`/api/accounts/${accountId}/conversion-actions?window=${WINDOW_DAYS}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: ConversionActionOption[]) => {
        if (!cancelled) setOptions(Array.isArray(data) ? data : []);
      })
      .catch(e => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [accountId]);

  const labelFor = (o: ConversionActionOption) =>
    `${o.name} — ${o.conversions} conv/${WINDOW_DAYS}d${o.primary_for_goal ? ' · primary' : ''}`;

  const handle = (id: string) => {
    if (!id) { onChange('', ''); return; }
    if (id === ACCOUNT_DEFAULT_GOAL) { onChange(ACCOUNT_DEFAULT_GOAL, ''); return; }
    const opt = options.find(o => o.id === id);
    onChange(id, opt ? opt.name : id);
  };

  const isDefault = value === ACCOUNT_DEFAULT_GOAL;

  return (
    <div className="border border-border rounded-md p-3 bg-secondary/20">
      <div className="flex items-center gap-2 mb-1.5">
        <Target className="h-3.5 w-3.5 text-primary" />
        <span className="text-xs font-semibold">Conversion goal *</span>
        {loading && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
      </div>
      <p className="text-[10px] text-muted-foreground mb-2">
        Pick the single conversion this campaign optimises for. Leaving the
        account default mixes every category (purchase, lead, contact…) and
        makes bidding chase the wrong signal.
      </p>
      <select
        value={value}
        onChange={e => handle(e.target.value)}
        disabled={loading || !!error}
        className="w-full h-9 rounded-md border border-border bg-background px-2.5 text-sm disabled:opacity-50"
      >
        <option value="" disabled>Select a conversion goal…</option>
        {options.map(o => (
          <option key={o.id} value={o.id}>{labelFor(o)}</option>
        ))}
        <option value={ACCOUNT_DEFAULT_GOAL}>
          Account default goals (not recommended — mixes categories)
        </option>
      </select>
      {error && (
        <p className="text-[10px] text-warning mt-1.5">
          Couldn&apos;t load conversion actions ({error}). You can still create
          with the account default, or retry.
        </p>
      )}
      {isDefault && !error && (
        <div className="flex items-start gap-1.5 mt-2 text-[10px] text-warning">
          <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
          <span>
            Using account-default goals — the campaign will bid on every
            biddable category at once. Prefer a single named action above.
          </span>
        </div>
      )}
    </div>
  );
}
