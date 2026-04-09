import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import { fetchCampaignChart, type DailyMetric } from '@/lib/api';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { cn } from '@/lib/utils';

type MetricKey = 'cost' | 'clicks' | 'conversions' | 'impressions' | 'ctr' | 'cpc' | 'cpa';

interface MetricConfig {
  key: MetricKey;
  label: string;
  color: string;
  format: (v: number) => string;
}

const METRICS: MetricConfig[] = [
  { key: 'cost', label: 'Cost', color: '#3b82f6', format: (v) => `$${v.toFixed(2)}` },
  { key: 'clicks', label: 'Clicks', color: '#10b981', format: (v) => v.toLocaleString() },
  { key: 'conversions', label: 'Conv', color: '#8b5cf6', format: (v) => v.toFixed(1) },
  { key: 'impressions', label: 'Impr', color: '#6366f1', format: (v) => v.toLocaleString() },
  { key: 'ctr', label: 'CTR %', color: '#f59e0b', format: (v) => `${v.toFixed(2)}%` },
  { key: 'cpc', label: 'CPC', color: '#ef4444', format: (v) => `$${v.toFixed(2)}` },
  { key: 'cpa', label: 'CPA', color: '#ec4899', format: (v) => v > 0 ? `$${v.toFixed(2)}` : '--' },
];

const PERIOD_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '14d', days: 14 },
  { label: '30d', days: 30 },
];

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-popover border border-border rounded-lg px-3 py-2 shadow-md text-xs">
      <p className="font-medium mb-1">{label}</p>
      {payload.map((entry: any) => {
        const metric = METRICS.find((m) => m.key === entry.dataKey);
        return (
          <p key={entry.dataKey} style={{ color: entry.color }}>
            {metric?.label}: {metric?.format(entry.value) ?? entry.value}
          </p>
        );
      })}
    </div>
  );
}

interface PerformanceChartProps {
  campaignId: string;
}

export default function PerformanceChart({ campaignId }: PerformanceChartProps) {
  const accountId = useClientAccountId();
  const [period, setPeriod] = useState(30);
  const [activeMetrics, setActiveMetrics] = useState<MetricKey[]>(['cost', 'clicks', 'conversions']);

  const dateFrom = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - period + 1);
    return d.toISOString().split('T')[0];
  }, [period]);

  const dateTo = useMemo(() => new Date().toISOString().split('T')[0], []);

  const { data: chartData = [], isLoading } = useQuery({
    queryKey: ['campaign-chart', accountId, campaignId, dateFrom, dateTo],
    queryFn: () => fetchCampaignChart(accountId, campaignId, dateFrom, dateTo),
    staleTime: 120_000,
    enabled: !!accountId && !!campaignId,
  });

  // Compute period-over-period comparison (Story 3.2)
  const comparison = useMemo(() => {
    if (chartData.length === 0) return null;
    const mid = Math.floor(chartData.length / 2);
    const current = chartData.slice(mid);
    const previous = chartData.slice(0, mid);

    const sum = (arr: DailyMetric[], key: MetricKey) =>
      arr.reduce((s, d) => s + (d[key] as number), 0);
    const avg = (arr: DailyMetric[], key: MetricKey) =>
      arr.length > 0 ? sum(arr, key) / arr.length : 0;

    return METRICS.map((m) => {
      const curr = m.key === 'ctr' || m.key === 'cpc' || m.key === 'cpa'
        ? avg(current, m.key) : sum(current, m.key);
      const prev = m.key === 'ctr' || m.key === 'cpc' || m.key === 'cpa'
        ? avg(previous, m.key) : sum(previous, m.key);
      const delta = prev > 0 ? ((curr - prev) / prev) * 100 : 0;
      // For cost/cpc/cpa, lower is better (invert color)
      const invertColor = ['cost', 'cpc', 'cpa'].includes(m.key);
      return { ...m, current: curr, previous: prev, delta, invertColor };
    });
  }, [chartData]);

  // Anomaly detection (Story 3.3)
  const anomalies = useMemo(() => {
    if (chartData.length < 7) return {};
    const result: Record<string, 'up' | 'down'> = {};
    for (const m of METRICS) {
      const values = chartData.map((d) => d[m.key] as number).filter((v) => v > 0);
      if (values.length < 3) continue;
      const avg = values.reduce((s, v) => s + v, 0) / values.length;
      const latest = values[values.length - 1];
      if (avg > 0 && Math.abs((latest - avg) / avg) > 0.2) {
        result[m.key] = latest > avg ? 'up' : 'down';
      }
    }
    return result;
  }, [chartData]);

  const toggleMetric = (key: MetricKey) => {
    setActiveMetrics((prev) =>
      prev.includes(key)
        ? prev.filter((k) => k !== key)
        : [...prev, key]
    );
  };

  // Format dates for chart display
  const formattedData = useMemo(() =>
    chartData.map((d) => ({
      ...d,
      date: d.date.slice(5), // "03-24" instead of "2026-03-24"
    })),
    [chartData]
  );

  return (
    <div className="space-y-4">
      {/* Period selector + metric toggles */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.days}
              onClick={() => setPeriod(opt.days)}
              className={cn(
                'px-2.5 py-1 text-[11px] rounded-md transition-colors',
                period === opt.days
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 flex-wrap">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => toggleMetric(m.key)}
              className={cn(
                'px-2 py-0.5 text-[10px] rounded-full border transition-colors',
                activeMetrics.includes(m.key)
                  ? 'border-current font-medium'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
              style={{ color: activeMetrics.includes(m.key) ? m.color : undefined }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Comparison cards (Story 3.2) */}
      {comparison && (
        <div className="grid grid-cols-4 gap-2">
          {comparison.filter((c) => activeMetrics.includes(c.key)).slice(0, 4).map((c) => {
            const isPositive = c.invertColor ? c.delta < 0 : c.delta > 0;
            const anomaly = anomalies[c.key];
            return (
              <div
                key={c.key}
                className={cn(
                  'bg-card border rounded-lg p-3 text-center',
                  anomaly ? 'border-yellow-500/40' : 'border-border'
                )}
              >
                <p className="text-[10px] text-muted-foreground mb-1">{c.label}</p>
                <p className="text-lg font-semibold">{c.format(c.current)}</p>
                {c.delta !== 0 && (
                  <p className={cn('text-[10px] font-medium', isPositive ? 'text-green-500' : 'text-red-500')}>
                    {c.delta > 0 ? '+' : ''}{c.delta.toFixed(1)}% vs prior
                  </p>
                )}
                {anomaly && (
                  <p className="text-[9px] text-yellow-500 mt-0.5">
                    {anomaly === 'up' ? 'Above' : 'Below'} avg
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Chart */}
      {isLoading ? (
        <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
          Loading chart data...
        </div>
      ) : formattedData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
          No data for this period
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={formattedData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10 }}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                className="text-muted-foreground"
                width={50}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                iconType="line"
                wrapperStyle={{ fontSize: '11px' }}
              />
              {METRICS.filter((m) => activeMetrics.includes(m.key)).map((m) => (
                <Line
                  key={m.key}
                  type="monotone"
                  dataKey={m.key}
                  name={m.label}
                  stroke={m.color}
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
