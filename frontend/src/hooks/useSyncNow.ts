/**
 * useSyncNow — the shared "Sync now" mutation behind every FreshnessChip
 * (Dashboard v2.1, Epic A / A3).
 *
 * POSTs the manual metrics sync (`POST /api/accounts/{id}/sync`), then
 * invalidates every home read that carries a freshness envelope so all three
 * chips refresh together and flip fresh:
 *   ['metrics-overview']      — KpiCards
 *   ['campaigns']             — CampaignsRanked table (+ Sidebar consumers)
 *   ['campaigns-freshness']   — CampaignsRanked chip
 *   ['fix-actions'] / ['account-report-meta'] — FixListStrip
 *
 * `isSyncing` drives the chip's syncing look + disables the control while in
 * flight, so pressing Sync now can't double-fire.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { syncAccountNow } from '@/lib/api';

export function useSyncNow(accountId: string) {
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => syncAccountNow(accountId),
    onSettled: () => {
      // Invalidate by key PREFIX (predicate) so every windowed variant
      // (e.g. ['metrics-overview', id, 7] and ['campaigns', id, from, to])
      // refreshes, not just the base key.
      for (const key of [
        'metrics-overview',
        'campaigns',
        'campaigns-freshness',
        'fix-actions',
        'account-report-meta',
      ]) {
        qc.invalidateQueries({
          predicate: (q) => q.queryKey[0] === key && q.queryKey[1] === accountId,
        });
      }
    },
  });

  return {
    syncNow: () => {
      if (!accountId || mutation.isPending) return;
      mutation.mutate();
    },
    isSyncing: mutation.isPending,
  };
}
