import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '@/stores/appStore';
import { fetchAccounts } from '@/lib/api';

/**
 * Resolves the correct client account ID for API calls.
 * MCC/manager accounts can't query metrics — we need the client account ID.
 *
 * Strategy: if selectedAccountId is already a client, use it directly.
 * Otherwise, find the best client under the MCC — prefer the largest named account.
 */
export function useClientAccountId(): string {
  const { selectedAccountId, connectedAccounts } = useAppStore();
  const mccId = selectedAccountId || connectedAccounts[0]?.id || '';

  const { data: hierarchy } = useQuery({
    queryKey: ['accounts-hierarchy', mccId],
    queryFn: fetchAccounts,
    staleTime: 300_000,
    enabled: !!mccId,
  });

  return useMemo(() => {
    if (!hierarchy || hierarchy.length === 0) return mccId;

    // If the selected account is already a client, use it directly
    const selected = hierarchy.find((a) => a.id === mccId);
    if (selected?.level === 'client') return mccId;

    // Find the best client account under this MCC
    const clients = hierarchy.filter((a) => a.level === 'client' && a.is_active);

    if (clients.length === 0) return mccId;
    if (clients.length === 1) return clients[0].id;

    // Heuristic: prefer accounts with real names (not "Account XXXXX")
    // as they're more likely to be active managed accounts
    const namedClients = clients.filter((c) => !c.name.startsWith('Account '));
    if (namedClients.length === 1) return namedClients[0].id;

    // If multiple named clients, prefer the one with "Main" or "Mercan" in name,
    // or just the first named client
    const mainClient = namedClients.find((c) =>
      c.name.toLowerCase().includes('main') ||
      c.name.toLowerCase().includes('mercan')
    );
    if (mainClient) return mainClient.id;

    return namedClients[0]?.id || clients[0].id;
  }, [hierarchy, mccId]);
}
