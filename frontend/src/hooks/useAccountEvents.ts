/**
 * useAccountEvents — the frontend half of the push channel (Dashboard v2.1,
 * Epic C / C1). Opens ONE EventSource on `/api/accounts/{id}/events` while an
 * accountId is set and invalidates the affected React-Query caches when the
 * backend pushes an event, so the home refreshes without a poll or a reload.
 *
 * The backend (workflows.py account_events_stream) emits JSON `data:` lines:
 *   {"type":"connected"}                                      on open — ignored
 *   {"type":"sync_completed","domain":"metrics",
 *    "data_through_date":"2026-07-11"}                         after a sync
 *   {"type":"external_change","count":3}                       roster diff
 * plus `: keepalive` comment lines (~25s) which EventSource never surfaces.
 *
 * Invalidation map (by key PREFIX + accountId, matching useSyncNow so every
 * windowed variant refreshes):
 *   sync_completed  → metrics-overview · campaigns · campaigns-freshness ·
 *                     fix-actions · account-report-meta
 *   external_change → external-changes · account-activity · campaigns
 *
 * Reconnect: EventSource auto-reconnects on transport drop — we do NOT hand-roll
 * a retry loop. We only close on unmount / accountId change so a stale socket
 * can't outlive the account it belongs to.
 */

import { useEffect } from 'react';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';

/** Invalidate every windowed variant of `key` scoped to this account. */
function invalidateForAccount(qc: QueryClient, accountId: string, keys: string[]) {
  for (const key of keys) {
    qc.invalidateQueries({
      predicate: (q) => q.queryKey[0] === key && q.queryKey[1] === accountId,
    });
  }
}

const SYNC_KEYS = [
  'metrics-overview',
  'campaigns',
  'campaigns-freshness',
  'fix-actions',
  'account-report-meta',
];
const EXTERNAL_CHANGE_KEYS = ['external-changes', 'account-activity', 'campaigns'];

export function useAccountEvents(accountId: string | null | undefined): void {
  const qc = useQueryClient();

  useEffect(() => {
    if (!accountId) return;

    const es = new EventSource(`/api/accounts/${encodeURIComponent(accountId)}/events`);

    es.onmessage = (evt) => {
      // Defensive parse — a malformed frame must never throw out of the handler.
      let payload: { type?: string } | null = null;
      try {
        payload = JSON.parse(evt.data);
      } catch {
        return;
      }
      if (!payload || typeof payload.type !== 'string') return;

      switch (payload.type) {
        case 'sync_completed':
          invalidateForAccount(qc, accountId, SYNC_KEYS);
          break;
        case 'external_change':
          invalidateForAccount(qc, accountId, EXTERNAL_CHANGE_KEYS);
          break;
        // 'connected' + any unknown/future event type: no-op (keepalive comment
        // lines never reach onmessage at all).
        default:
          break;
      }
    };

    // EventSource retries transport drops on its own; swallow the error so it
    // stays quiet and lets the browser reconnect.
    es.onerror = () => {};

    return () => es.close();
  }, [accountId, qc]);
}
