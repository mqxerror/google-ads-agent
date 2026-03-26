import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { fetchKeywords } from '@/lib/api';
import { formatNumber, formatMicros } from '@/lib/formatters';
import type { Keyword } from '@/types';

type SortKey = 'text' | 'matchType' | 'adGroupName' | 'status' | 'qualityScore' | 'impressions' | 'clicks' | 'conversions' | 'cpa';

interface KeywordTableProps {
  accountId: string;
  campaignId: string;
}

export default function KeywordTable({ accountId, campaignId }: KeywordTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('impressions');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const { data: keywords = [], isLoading } = useQuery({
    queryKey: ['keywords', accountId, campaignId],
    queryFn: () => fetchKeywords(accountId, campaignId),
  });

  const sorted = useMemo(() => {
    return [...keywords].sort((a, b) => {
      let av: string | number = 0;
      let bv: string | number = 0;
      switch (sortKey) {
        case 'text': av = a.text; bv = b.text; break;
        case 'matchType': av = a.matchType; bv = b.matchType; break;
        case 'adGroupName': av = a.adGroupName; bv = b.adGroupName; break;
        case 'status': av = a.status; bv = b.status; break;
        case 'qualityScore': av = a.qualityScore ?? 0; bv = b.qualityScore ?? 0; break;
        case 'impressions': av = a.metrics.impressions; bv = b.metrics.impressions; break;
        case 'clicks': av = a.metrics.clicks; bv = b.metrics.clicks; break;
        case 'conversions': av = a.metrics.conversions; bv = b.metrics.conversions; break;
        case 'cpa': av = a.metrics.cpa; bv = b.metrics.cpa; break;
      }
      if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv as string) : (bv as string).localeCompare(av);
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [keywords, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  if (isLoading) return <div className="text-sm text-muted-foreground p-4">Loading keywords...</div>;
  if (keywords.length === 0) return <div className="text-sm text-muted-foreground p-4">No keywords found for this campaign.</div>;

  const columns: { key: SortKey; label: string; align?: string }[] = [
    { key: 'text', label: 'Keyword' },
    { key: 'matchType', label: 'Match' },
    { key: 'adGroupName', label: 'Ad Group' },
    { key: 'status', label: 'Status' },
    { key: 'qualityScore', label: 'QS', align: 'text-center' },
    { key: 'impressions', label: 'Impr', align: 'text-right' },
    { key: 'clicks', label: 'Clicks', align: 'text-right' },
    { key: 'conversions', label: 'Conv', align: 'text-right' },
    { key: 'cpa', label: 'CPA', align: 'text-right' },
  ];

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-secondary/30 border-b border-border">
            {columns.map(col => (
              <th
                key={col.key}
                className={cn('px-3 py-2 font-medium text-muted-foreground cursor-pointer hover:text-foreground select-none', col.align)}
                onClick={() => toggleSort(col.key)}
              >
                <span className="inline-flex items-center gap-1">
                  {col.label}
                  <ArrowUpDown className={cn('h-3 w-3', sortKey === col.key ? 'text-primary' : 'opacity-30')} />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((kw: Keyword, idx: number) => (
            <tr key={`${kw.id}-${kw.matchType}-${idx}`} className="border-b border-border last:border-0 hover:bg-secondary/20">
              <td className="px-3 py-2 font-medium">{kw.text}</td>
              <td className="px-3 py-2">
                <Badge variant="secondary" className="text-[10px]">{kw.matchType}</Badge>
              </td>
              <td className="px-3 py-2 text-muted-foreground truncate max-w-[150px]">{kw.adGroupName}</td>
              <td className="px-3 py-2">
                <span className={cn('text-[10px]', kw.status === 'ENABLED' ? 'text-status-enabled' : 'text-status-paused')}>
                  {kw.status}
                </span>
              </td>
              <td className="px-3 py-2 text-center">{kw.qualityScore ?? '—'}</td>
              <td className="px-3 py-2 text-right">{formatNumber(kw.metrics.impressions)}</td>
              <td className="px-3 py-2 text-right">{formatNumber(kw.metrics.clicks)}</td>
              <td className="px-3 py-2 text-right">{kw.metrics.conversions}</td>
              <td className="px-3 py-2 text-right">{kw.metrics.cpa > 0 ? formatMicros(kw.metrics.cpa * 1_000_000) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
