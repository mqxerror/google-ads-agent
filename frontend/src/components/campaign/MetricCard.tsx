import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';

interface MetricCardProps {
  label: string;
  value: string;
  trend?: number; // percentage
  icon?: ReactNode;
}

export default function MetricCard({ label, value, trend, icon }: MetricCardProps) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center gap-2 text-muted-foreground text-xs mb-1.5">
        {icon}
        {label}
      </div>
      <div className="text-xl font-semibold">{value}</div>
      {trend !== undefined && (
        <div
          className={cn(
            'text-xs mt-1',
            trend >= 0 ? 'text-status-enabled' : 'text-destructive'
          )}
        >
          {trend >= 0 ? '+' : ''}
          {trend.toFixed(1)}%
        </div>
      )}
    </div>
  );
}
