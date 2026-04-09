import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Eye, Ban, Plus, Loader2 } from 'lucide-react';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface SearchTermEntry {
  term: string;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  ctr: number;
  cpa: number | null;
  ad_group_name: string;
  recommendation?: string;
  reason?: string;
  suggested_match_type?: string;
  suggested_negative_match_type?: string;
}

interface AnalysisResult {
  high_value: SearchTermEntry[];
  irrelevant: SearchTermEntry[];
  monitor: SearchTermEntry[];
  total_terms: number;
  date_from: string;
  date_to: string;
}

type Tab = 'irrelevant' | 'high_value' | 'monitor';

interface SearchTermManagerProps {
  campaignId: string;
}

export default function SearchTermManager({ campaignId }: SearchTermManagerProps) {
  const accountId = useClientAccountId();
  const [activeTab, setActiveTab] = useState<Tab>('irrelevant');
  const [selectedTerms, setSelectedTerms] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [days, setDays] = useState(7);
  const [appliedTerms, setAppliedTerms] = useState<Set<string>>(new Set());
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['search-terms-analysis', accountId, campaignId, days],
    queryFn: async () => {
      const res = await fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/search-terms/analysis?days=${days}`);
      if (!res.ok) throw new Error(`API error ${res.status}`);
      return res.json() as Promise<AnalysisResult>;
    },
    staleTime: 120_000,
    enabled: !!accountId && !!campaignId,
  });

  // Filter out terms that have already been applied as negatives in this session
  const terms = (data?.[activeTab] ?? []).filter((t) => !appliedTerms.has(t.term));

  const toggleTerm = (term: string) => {
    setSelectedTerms((prev) => {
      const next = new Set(prev);
      if (next.has(term)) next.delete(term);
      else next.add(term);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedTerms.size === terms.length) {
      setSelectedTerms(new Set());
    } else {
      setSelectedTerms(new Set(terms.map((t) => t.term)));
    }
  };

  const handleApplyNegatives = async () => {
    if (selectedTerms.size === 0) return;
    setApplying(true);
    try {
      const keywords = terms
        .filter((t) => selectedTerms.has(t.term))
        .map((t) => ({
          text: t.term,
          match_type: t.suggested_negative_match_type || 'EXACT',
        }));

      const res = await fetch('/api/operations/bulk-negatives', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: accountId,
          campaign_id: campaignId,
          keywords,
        }),
      });

      if (!res.ok) throw new Error('Failed to apply negatives');
      const result = await res.json();
      // Remove applied terms from the UI immediately
      setAppliedTerms((prev) => {
        const next = new Set(prev);
        selectedTerms.forEach((t) => next.add(t));
        return next;
      });
      setSelectedTerms(new Set());
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setApplying(false);
    }
  };

  const filterApplied = (list: SearchTermEntry[] | undefined) =>
    (list ?? []).filter((t) => !appliedTerms.has(t.term));

  const tabs: { key: Tab; label: string; count: number; icon: typeof Ban; color: string }[] = [
    { key: 'irrelevant', label: 'Irrelevant', count: filterApplied(data?.irrelevant).length, icon: Ban, color: 'text-red-500' },
    { key: 'high_value', label: 'High Value', count: filterApplied(data?.high_value).length, icon: CheckCircle2, color: 'text-green-500' },
    { key: 'monitor', label: 'Monitor', count: filterApplied(data?.monitor).length, icon: Eye, color: 'text-yellow-500' },
  ];

  if (isLoading) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        <Loader2 className="h-5 w-5 mx-auto mb-2 animate-spin" />
        Analyzing search terms...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        <AlertTriangle className="h-5 w-5 mx-auto mb-2 text-yellow-500" />
        Failed to load search terms. The campaign may not have enough data.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">Search Term Analysis</h3>
          <p className="text-[11px] text-muted-foreground">
            {data?.total_terms ?? 0} terms analyzed ({data?.date_from} to {data?.date_to})
          </p>
        </div>
        <div className="flex gap-1">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => { setDays(d); setSelectedTerms(new Set()); setAppliedTerms(new Set()); }}
              className={cn(
                'px-2.5 py-1 text-[11px] rounded-md transition-colors',
                days === d ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-secondary'
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2">
        {tabs.map(({ key, label, count, icon: Icon, color }) => (
          <button
            key={key}
            onClick={() => { setActiveTab(key); setSelectedTerms(new Set()); }}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors',
              activeTab === key
                ? 'bg-secondary border-border font-medium'
                : 'border-transparent text-muted-foreground hover:bg-secondary/50'
            )}
          >
            <Icon className={cn('h-3.5 w-3.5', activeTab === key ? color : '')} />
            {label}
            <span className="text-[10px] opacity-60">{count}</span>
          </button>
        ))}
      </div>

      {/* Bulk action bar */}
      {activeTab === 'irrelevant' && terms.length > 0 && (
        <div className="flex items-center gap-3 bg-secondary/30 rounded-lg px-3 py-2">
          <label className="flex items-center gap-1.5 text-xs cursor-pointer">
            <input
              type="checkbox"
              checked={selectedTerms.size === terms.length && terms.length > 0}
              onChange={selectAll}
              className="rounded"
            />
            Select all ({terms.length})
          </label>
          {selectedTerms.size > 0 && (
            <Button
              size="sm"
              variant="destructive"
              className="text-xs h-7 gap-1"
              onClick={handleApplyNegatives}
              disabled={applying}
            >
              {applying ? (
                <><Loader2 className="h-3 w-3 animate-spin" /> Applying...</>
              ) : (
                <><Ban className="h-3 w-3" /> Add {selectedTerms.size} as Negatives</>
              )}
            </Button>
          )}
        </div>
      )}

      {/* Terms table */}
      {terms.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground text-sm">
          No {activeTab.replace('_', ' ')} terms found
        </div>
      ) : (
        <div className="border border-border rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-secondary/30 border-b border-border">
                {activeTab === 'irrelevant' && <th className="w-8 px-2 py-2" />}
                <th className="text-left px-3 py-2 font-medium">Search Term</th>
                <th className="text-left px-3 py-2 font-medium">Ad Group</th>
                <th className="text-right px-3 py-2 font-medium">Impr</th>
                <th className="text-right px-3 py-2 font-medium">Clicks</th>
                <th className="text-right px-3 py-2 font-medium">Cost</th>
                <th className="text-right px-3 py-2 font-medium">Conv</th>
                <th className="text-left px-3 py-2 font-medium">
                  {activeTab === 'irrelevant' ? 'Neg. Type' : activeTab === 'high_value' ? 'Action' : 'Status'}
                </th>
              </tr>
            </thead>
            <tbody>
              {terms.map((t, i) => (
                <tr key={`${t.term}-${i}`} className="border-b border-border last:border-0 hover:bg-secondary/20">
                  {activeTab === 'irrelevant' && (
                    <td className="px-2 py-2">
                      <input
                        type="checkbox"
                        checked={selectedTerms.has(t.term)}
                        onChange={() => toggleTerm(t.term)}
                        className="rounded"
                      />
                    </td>
                  )}
                  <td className="px-3 py-2 font-medium max-w-[250px] truncate">{t.term}</td>
                  <td className="px-3 py-2 text-muted-foreground truncate max-w-[120px]">{t.ad_group_name}</td>
                  <td className="px-3 py-2 text-right">{t.impressions.toLocaleString()}</td>
                  <td className="px-3 py-2 text-right">{t.clicks}</td>
                  <td className="px-3 py-2 text-right">${t.cost.toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{t.conversions}</td>
                  <td className="px-3 py-2">
                    {activeTab === 'irrelevant' && (
                      <Badge variant="secondary" className="text-[9px] text-red-500">
                        {t.suggested_negative_match_type || 'EXACT'}
                      </Badge>
                    )}
                    {activeTab === 'high_value' && (
                      <Badge variant="secondary" className="text-[9px] text-green-500">
                        Add as {t.suggested_match_type || 'EXACT'}
                      </Badge>
                    )}
                    {activeTab === 'monitor' && (
                      <span className="text-[10px] text-muted-foreground">{t.reason}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
