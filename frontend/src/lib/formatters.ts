import type { Account } from '@/types';

export function formatMicros(micros: number): string {
  return `$${(micros / 1_000_000).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US');
}

export function formatPercent(n: number): string {
  return `${n.toFixed(2)}%`;
}

const BIDDING_STRATEGY_NAMES: Record<string, string> = {
  TARGET_SPEND: 'Maximize Clicks',
  MAXIMIZE_CONVERSIONS: 'Maximize Conversions',
  MAXIMIZE_CONVERSION_VALUE: 'Maximize Conversion Value',
  TARGET_CPA: 'Target CPA',
  TARGET_ROAS: 'Target ROAS',
  TARGET_IMPRESSION_SHARE: 'Target Impression Share',
  MANUAL_CPC: 'Manual CPC',
  MANUAL_CPM: 'Manual CPM',
  MANUAL_CPV: 'Manual CPV',
  ENHANCED_CPC: 'Enhanced CPC',
  COMMISSION: 'Commission',
  PERCENT_CPC: 'Percent CPC',
};

export function formatBiddingStrategy(apiValue: string): string {
  // Unknown/empty strategy → a quiet dash, never the channel type dressed as a
  // strategy (Dashboard v2.1 B2). Also treats the API's UNSPECIFIED/UNKNOWN
  // enum sentinels as "no strategy".
  if (!apiValue || apiValue === 'UNSPECIFIED' || apiValue === 'UNKNOWN') return '—';
  return BIDDING_STRATEGY_NAMES[apiValue] || apiValue.replace(/_/g, ' ');
}

export function flattenAccounts(accounts: Account[]): Account[] {
  const result: Account[] = [];
  function walk(accs: Account[]) {
    for (const a of accs) {
      result.push(a);
      if (a.children) walk(a.children);
    }
  }
  walk(accounts);
  return result;
}
