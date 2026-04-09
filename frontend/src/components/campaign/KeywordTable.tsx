import { useState, useMemo, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useVirtualizer } from '@tanstack/react-virtual';
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
  const parentRef = useRef<HTMLDivElement>(null);

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

  const rowVirtualizer = useVirtualizer({
    count: sorted.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 20,
  });

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
      {/* Header */}
      <table className="w-full text-xs table-fixed">
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
      </table>

      {/* Virtualized body */}
      <div ref={parentRef} className="max-h-[500px] overflow-auto">
        <div style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const kw = sorted[virtualRow.index];
            return (
              <div
                key={virtualRow.key}
                className="absolute w-full flex items-center text-xs border-b border-border last:border-0 hover:bg-secondary/20"
                style={{
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <span className="px-3 py-2 flex-[2] font-medium truncate">{kw.text}</span>
                <span className="px-3 py-2 flex-1">
                  <Badge variant="secondary" className="text-[10px]">{kw.matchType}</Badge>
                </span>
                <span className="px-3 py-2 flex-[1.5] text-muted-foreground truncate">{kw.adGroupName}</span>
                <span className="px-3 py-2 flex-1">
                  <span className={cn('text-[10px]', kw.status === 'ENABLED' ? 'text-status-enabled' : 'text-status-paused')}>
                    {kw.status}
                  </span>
                </span>
                <span className="px-3 py-2 flex-[0.5] text-center">{kw.qualityScore ?? '—'}</span>
                <span className="px-3 py-2 flex-1 text-right">{formatNumber(kw.metrics.impressions)}</span>
                <span className="px-3 py-2 flex-1 text-right">{formatNumber(kw.metrics.clicks)}</span>
                <span className="px-3 py-2 flex-1 text-right">{kw.metrics.conversions}</span>
                <span className="px-3 py-2 flex-1 text-right">{kw.metrics.cpa > 0 ? formatMicros(kw.metrics.cpa * 1_000_000) : '—'}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Row count */}
      <div className="px-3 py-1.5 text-[10px] text-muted-foreground bg-secondary/20 border-t border-border">
        {sorted.length} keyword{sorted.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
