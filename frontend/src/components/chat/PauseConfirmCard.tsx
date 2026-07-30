import { useState } from 'react';
import { AlertTriangle, Loader2, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { mintPauseConfirmation } from '@/lib/api';
import type { PauseConfirmPayload } from '@/types';

interface PauseConfirmCardProps {
  payload: PauseConfirmPayload;
  /** Fired AFTER a grant is successfully minted — the parent re-issues the
   *  pause through the normal chat path so the chokepoint consumes the grant. */
  onConfirmed: (payload: PauseConfirmPayload) => void;
}

function money(n: number | null | undefined): string {
  if (n == null) return '—';
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function leads(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n} lead${n === 1 ? '' : 's'}`;
}

/**
 * The safety card shown when a WORKING campaign is about to be paused/removed.
 * It names the exact campaign, shows its last-7-day performance, and requires an
 * explicit click. Only this click mints the grant that authorizes the action —
 * "pause this campaign" typed into the wrong chat can never kill a converter.
 */
export default function PauseConfirmCard({ payload, onConfirmed }: PauseConfirmCardProps) {
  const [state, setState] = useState<'idle' | 'minting' | 'confirmed' | 'error'>('idle');
  const verb = payload.action === 'REMOVED' ? 'Remove' : 'Pause';

  const confirm = async () => {
    if (state === 'minting' || state === 'confirmed') return;
    setState('minting');
    try {
      await mintPauseConfirmation({
        campaign_id: payload.campaign_id,
        action: payload.action,
        customer_id: payload.customer_id,
        campaign_name: payload.campaign_name,
      });
      setState('confirmed');
      onConfirmed(payload);
    } catch {
      setState('error');
    }
  };

  return (
    <div className="mt-2 rounded-[12px] border border-warning/40 bg-warning-soft/60 p-3 text-sm">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-text">
            {verb} “{payload.campaign_name}”?
          </p>
          <p className="mt-0.5 text-[11px] font-mono text-muted-foreground">
            {payload.campaign_id}
          </p>

          <p className="mt-2 text-xs text-muted-foreground">
            {payload.lookup_ok === false ? (
              <span className="text-danger">
                Recent performance couldn’t be verified — protected by default.
              </span>
            ) : (
              <>
                This campaign is working. Last 7 days:{' '}
                <span className="font-medium text-text">{money(payload.cost)}</span>{' '}
                ·{' '}
                <span className="font-medium text-text">{leads(payload.conversions)}</span>
                {payload.cpa != null && (
                  <>
                    {' '}
                    · <span className="font-medium text-text">{money(payload.cpa)} CPA</span>
                  </>
                )}
                .
              </>
            )}
          </p>

          {state === 'confirmed' ? (
            <div className="mt-2.5 flex items-center gap-1.5 text-xs text-success">
              <Check className="h-3.5 w-3.5" />
              <span>Confirmed — {verb.toLowerCase()} authorized. Applying…</span>
            </div>
          ) : (
            <div className="mt-2.5 flex items-center gap-2">
              <button
                onClick={confirm}
                disabled={state === 'minting'}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold',
                  'bg-danger text-white transition-colors hover:opacity-90 disabled:opacity-60',
                )}
              >
                {state === 'minting' ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <AlertTriangle className="h-3.5 w-3.5" />
                )}
                Yes, {verb.toLowerCase()} it
              </button>
              {state === 'error' && (
                <span className="inline-flex items-center gap-1 text-xs text-danger">
                  <X className="h-3.5 w-3.5" /> Couldn’t confirm — try again
                </span>
              )}
              {state !== 'error' && (
                <span className="text-[11px] text-subtle">
                  Nothing changes unless you click.
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
