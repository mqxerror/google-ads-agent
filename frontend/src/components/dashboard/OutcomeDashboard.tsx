import { useQuery } from '@tanstack/react-query';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { TrendingUp, TrendingDown, Minus, Activity, Target, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

interface OutcomeData {
  total_recommendations: number;
  measured: number;
  pending: number;
  improved: number;
  degraded: number;
  no_change: number;
  success_rate: number;
  top_actions: Array<{ type: string; count: number; success_rate: number }>;
  recent: Array<{
    id: string;
    campaign_id: string;
    action_type: string;
    action_detail: string;
    outcome: string | null;
    status: string;
    delta: { cpa_change_pct?: number; cpa_before?: number; cpa_after?: number } | null;
    executed_at: string;
    measured_at: string | null;
  }>;
}

async function fetchOutcomes(accountId: string): Promise<OutcomeData> {
  const res = await fetch(`/api/accounts/${accountId}/outcomes`);
  if (!res.ok) throw new Error('Failed to fetch outcomes');
  return res.json();
}

export default function OutcomeDashboard() {
  const accountId = useClientAccountId();

  const { data, isLoading } = useQuery({
    queryKey: ['outcomes', accountId],
    queryFn: () => fetchOutcomes(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  if (isLoading) return <div className="text-xs text-muted-foreground">Loading outcomes...</div>;
  if (!data || data.total_recommendations === 0) {
    return (
      <div className="border border-dashed border-border rounded-lg p-6 text-center">
        <Activity className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
        <p className="text-sm font-medium">No recommendations tracked yet</p>
        <p className="text-xs text-muted-foreground mt-1">
          When the agent makes changes (add keywords, adjust budgets, etc.), outcomes will be tracked here automatically.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Target className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">Agent Performance</h3>
        <span className="text-xs text-muted-foreground ml-auto">{data.total_recommendations} total actions</span>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Success Rate"
          value={`${data.success_rate}%`}
          detail={`${data.improved}/${data.measured} improved`}
          color={data.success_rate >= 70 ? 'text-emerald-600' : data.success_rate >= 50 ? 'text-yellow-600' : 'text-red-600'}
        />
        <StatCard label="Improved" value={String(data.improved)} icon={<TrendingUp className="h-3.5 w-3.5 text-emerald-500" />} />
        <StatCard label="Degraded" value={String(data.degraded)} icon={<TrendingDown className="h-3.5 w-3.5 text-red-500" />} />
        <StatCard label="Pending" value={String(data.pending)} icon={<Minus className="h-3.5 w-3.5 text-muted-foreground" />} detail="awaiting measurement" />
      </div>

      {/* Action type breakdown */}
      {data.top_actions.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">By Action Type</p>
          {data.top_actions.map((a) => (
            <div key={a.type} className="flex items-center gap-2 text-xs">
              <Zap className="h-3 w-3 text-muted-foreground shrink-0" />
              <span className="flex-1 truncate">{formatActionType(a.type)}</span>
              <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full', a.success_rate >= 70 ? 'bg-emerald-500' : a.success_rate >= 50 ? 'bg-yellow-500' : 'bg-red-500')}
                  style={{ width: `${a.success_rate}%` }}
                />
              </div>
              <span className="w-8 text-right tabular-nums">{a.success_rate}%</span>
              <span className="text-muted-foreground w-6 text-right">({a.count})</span>
            </div>
          ))}
        </div>
      )}

      {/* Recent outcomes */}
      {data.recent.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Recent Actions</p>
          <div className="space-y-1">
            {data.recent.slice(0, 8).map((r) => (
              <div key={r.id} className="flex items-center gap-2 text-xs py-1">
                <OutcomeBadge outcome={r.outcome} status={r.status} />
                <span className="flex-1 truncate">{r.action_detail}</span>
                {r.delta?.cpa_change_pct != null && (
                  <span className={cn(
                    'tabular-nums text-[10px] font-medium',
                    r.delta.cpa_change_pct < 0 ? 'text-emerald-600' : 'text-red-600'
                  )}>
                    CPA {r.delta.cpa_change_pct > 0 ? '+' : ''}{r.delta.cpa_change_pct.toFixed(1)}%
                  </span>
                )}
                <span className="text-muted-foreground text-[10px]">
                  {r.executed_at?.slice(5, 10)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, detail, icon, color }: {
  label: string; value: string; detail?: string; icon?: React.ReactNode; color?: string;
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-3">
      <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] mb-1">
        {icon}
        {label}
      </div>
      <div className={cn('text-lg font-semibold', color)}>{value}</div>
      {detail && <div className="text-[10px] text-muted-foreground">{detail}</div>}
    </div>
  );
}

function OutcomeBadge({ outcome, status }: { outcome: string | null; status: string }) {
  if (status !== 'measured') {
    return <span className="w-2 h-2 rounded-full bg-gray-300 shrink-0" title="Pending measurement" />;
  }
  const colors = {
    improved: 'bg-emerald-500',
    degraded: 'bg-red-500',
    no_change: 'bg-yellow-500',
  };
  return <span className={cn('w-2 h-2 rounded-full shrink-0', colors[outcome as keyof typeof colors] || 'bg-gray-300')} title={outcome || 'unknown'} />;
}

function formatActionType(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
