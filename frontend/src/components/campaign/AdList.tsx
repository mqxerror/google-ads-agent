import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { fetchAds } from '@/lib/api';
import { formatNumber, formatMicros, formatPercent } from '@/lib/formatters';

interface AdListProps {
  accountId: string;
  campaignId: string;
}

export default function AdList({ accountId, campaignId }: AdListProps) {
  const { data: ads = [], isLoading } = useQuery({
    queryKey: ['ads', accountId, campaignId],
    queryFn: () => fetchAds(accountId, campaignId),
  });

  if (isLoading) return <div className="text-sm text-muted-foreground p-4">Loading ads...</div>;
  if (ads.length === 0) return <div className="text-sm text-muted-foreground p-4">No ads found for this campaign.</div>;

  return (
    <div className="space-y-4">
      {ads.map((ad) => {
        const statusColor =
          ad.status === 'ENABLED'
            ? 'bg-status-enabled/20 text-status-enabled'
            : ad.status === 'PAUSED'
              ? 'bg-status-paused/20 text-status-paused'
              : 'bg-status-removed/20 text-status-removed';

        return (
          <div key={ad.id} className="bg-card border border-border rounded-lg p-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <span className="text-xs text-muted-foreground">Ad Group: {ad.adGroupName}</span>
                <Badge variant="secondary" className={cn('ml-2 text-[10px]', statusColor)}>
                  {ad.status}
                </Badge>
              </div>
              <span className="text-xs text-muted-foreground">ID: {ad.id}</span>
            </div>

            {/* Headlines */}
            <div className="mb-2">
              <p className="text-xs text-muted-foreground mb-1">Headlines:</p>
              <div className="flex flex-wrap gap-1">
                {ad.headlines.map((h, i) => (
                  <span key={i} className="text-sm text-primary">{h}{i < ad.headlines.length - 1 ? ' | ' : ''}</span>
                ))}
              </div>
            </div>

            {/* Descriptions */}
            <div className="mb-3">
              <p className="text-xs text-muted-foreground mb-1">Descriptions:</p>
              {ad.descriptions.map((d, i) => (
                <p key={i} className="text-sm text-foreground/80">{d}</p>
              ))}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-5 gap-3 pt-3 border-t border-border">
              <div><span className="text-xs text-muted-foreground">Impr</span><p className="text-sm font-medium">{formatNumber(ad.metrics.impressions)}</p></div>
              <div><span className="text-xs text-muted-foreground">Clicks</span><p className="text-sm font-medium">{formatNumber(ad.metrics.clicks)}</p></div>
              <div><span className="text-xs text-muted-foreground">CTR</span><p className="text-sm font-medium">{formatPercent(ad.metrics.ctr)}</p></div>
              <div><span className="text-xs text-muted-foreground">Cost</span><p className="text-sm font-medium">{formatMicros(ad.metrics.costMicros)}</p></div>
              <div><span className="text-xs text-muted-foreground">Conv</span><p className="text-sm font-medium">{ad.metrics.conversions}</p></div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
