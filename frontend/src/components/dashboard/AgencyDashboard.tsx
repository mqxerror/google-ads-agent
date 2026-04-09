import { useQuery } from '@tanstack/react-query';
import { Activity, AlertTriangle, AlertCircle, CheckCircle2, Plus, TrendingUp, DollarSign, MousePointerClick } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, Tooltip } from 'recharts';
import { fetchDashboard, fetchAccountChart } from '@/lib/api';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useAppStore } from '@/stores/appStore';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import type { AccountHealth } from '@/types';

function HealthBadge({ health }: { health: AccountHealth['health'] }) {
  const config = {
    healthy: { icon: CheckCircle2, color: 'text-green-500', bg: 'bg-green-500/10' },
    warning: { icon: AlertTriangle, color: 'text-yellow-500', bg: 'bg-yellow-500/10' },
    critical: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-500/10' },
    unknown: { icon: Activity, color: 'text-muted-foreground', bg: 'bg-secondary' },
  };
  const { icon: Icon, color, bg } = config[health] || config.unknown;
  return (
    <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium', bg, color)}>
      <Icon className="h-3 w-3" />
      {health}
    </span>
  );
}

function AccountCard({ account, onClick }: { account: AccountHealth; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-card border border-border rounded-lg p-4 hover:border-primary/50 hover:bg-accent/50 transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-sm font-medium">{account.name}</h3>
          <p className="text-[10px] text-muted-foreground">{account.id}</p>
        </div>
        <HealthBadge health={account.health} />
      </div>
      <div className="grid grid-cols-3 gap-3 text-center">
        <div>
          <p className="text-lg font-semibold">{account.active_campaigns}</p>
          <p className="text-[10px] text-muted-foreground">Campaigns</p>
        </div>
        <div>
          <p className="text-lg font-semibold">${(account.total_spend_30d / 1).toFixed(0)}</p>
          <p className="text-[10px] text-muted-foreground">Spend (30d)</p>
        </div>
        <div>
          <p className="text-lg font-semibold">{account.alert_count}</p>
          <p className="text-[10px] text-muted-foreground">Alerts</p>
        </div>
      </div>
    </button>
  );
}

function SpendSparkline() {
  const clientAccountId = useClientAccountId();
  const dateFrom = new Date(Date.now() - 13 * 86400000).toISOString().split('T')[0];
  const dateTo = new Date().toISOString().split('T')[0];

  const { data: chartData = [] } = useQuery({
    queryKey: ['account-chart', clientAccountId, dateFrom, dateTo],
    queryFn: () => fetchAccountChart(clientAccountId, dateFrom, dateTo),
    staleTime: 300_000,
    enabled: !!clientAccountId,
  });

  if (chartData.length === 0) return null;

  const totalSpend = chartData.reduce((s, d) => s + d.cost, 0);
  const totalConversions = chartData.reduce((s, d) => s + d.conversions, 0);
  const totalClicks = chartData.reduce((s, d) => s + d.clicks, 0);

  return (
    <div className="bg-card border border-border rounded-lg p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">Last 14 Days — All Campaigns</h3>
        <div className="flex gap-4 text-xs">
          <span className="flex items-center gap-1 text-muted-foreground">
            <DollarSign className="h-3 w-3" />${totalSpend.toFixed(0)} spent
          </span>
          <span className="flex items-center gap-1 text-muted-foreground">
            <MousePointerClick className="h-3 w-3" />{totalClicks.toLocaleString()} clicks
          </span>
          <span className="flex items-center gap-1 text-muted-foreground">
            <TrendingUp className="h-3 w-3" />{totalConversions.toFixed(0)} conversions
          </span>
        </div>
      </div>
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData.map((d) => ({ ...d, date: d.date.slice(5) }))}>
            <defs>
              <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="date" tick={{ fontSize: 9 }} className="text-muted-foreground" />
            <Tooltip
              contentStyle={{ fontSize: '11px', borderRadius: '8px' }}
              formatter={(value: number, name: string) => {
                if (name === 'cost') return [`$${value.toFixed(2)}`, 'Cost'];
                if (name === 'conversions') return [value.toFixed(1), 'Conv'];
                return [value, name];
              }}
            />
            <Area type="monotone" dataKey="cost" stroke="#3b82f6" fill="url(#costGradient)" strokeWidth={2} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function AgencyDashboard() {
  const { switchAccount, connectedAccounts } = useAppStore();

  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    staleTime: 60_000,
  });

  const accounts = dashboard?.accounts ?? [];

  return (
    <ScrollArea className="flex-1">
      <div className="max-w-4xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-xl font-semibold">Dashboard</h2>
            <p className="text-sm text-muted-foreground">
              {accounts.length} account{accounts.length !== 1 ? 's' : ''} connected
              {dashboard && dashboard.total_alerts > 0 && (
                <span className="text-yellow-500 ml-2">
                  — {dashboard.total_alerts} alert{dashboard.total_alerts !== 1 ? 's' : ''}
                </span>
              )}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={() => window.location.assign('/setup')}
          >
            <Plus className="h-3 w-3" />
            Add Account
          </Button>
        </div>

        {/* Spend Sparkline */}
        {accounts.length > 0 && <SpendSparkline />}

        {/* Account Grid */}
        {isLoading ? (
          <div className="text-center py-16 text-muted-foreground text-sm">
            Loading accounts...
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-muted-foreground text-sm mb-4">
              No accounts connected yet.
            </p>
            <Button onClick={() => window.location.assign('/setup')}>
              <Plus className="h-4 w-4 mr-2" />
              Add Your First Account
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {accounts.map((account) => (
              <AccountCard
                key={account.id}
                account={account}
                onClick={() => switchAccount(account.id)}
              />
            ))}
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
