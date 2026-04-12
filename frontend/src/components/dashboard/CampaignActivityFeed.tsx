import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Activity, ChevronDown, ChevronRight, Loader2,
  Briefcase, Target, Search, Palette, BarChart3,
  Eye, Code, Rocket, Gauge, Clock, ExternalLink,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';

const AVATAR_ICONS: Record<string, typeof Briefcase> = {
  briefcase: Briefcase,
  target: Target,
  search: Search,
  palette: Palette,
  chart: BarChart3,
  eye: Eye,
  code: Code,
  rocket: Rocket,
  gauge: Gauge,
};

const ROLE_COLORS: Record<string, string> = {
  director: 'text-gray-500',
  ppc_strategist: 'text-orange-500',
  search_term_hunter: 'text-blue-500',
  creative_director: 'text-purple-500',
  analytics_analyst: 'text-green-500',
  competitor_intel: 'text-red-500',
  gtm_specialist: 'text-cyan-500',
  growth_hacker: 'text-yellow-500',
  cro_specialist: 'text-indigo-500',
  agent: 'text-gray-400',
};

function relativeTime(ts: string): string {
  try {
    const date = new Date(ts.replace(' ', 'T'));
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / 3600000);
    if (hours < 1) return 'just now';
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return 'yesterday';
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  } catch {
    return ts;
  }
}

interface ActivityItem {
  timestamp: string;
  role: string;
  role_id: string;
  avatar: string;
  action: string;
  type: string;
}

interface CampaignSummary {
  campaign_id: string;
  campaign_name: string;
  last_activity: string;
  active_roles: string[];
  recent_activities: ActivityItem[];
  total_activities: number;
}

export default function CampaignActivityFeed() {
  const accountId = useClientAccountId();
  const { setSelectedCampaign } = useAppStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['account-activity', accountId],
    queryFn: async () => {
      const res = await fetch(`/api/accounts/${accountId}/activity`);
      return res.json() as Promise<{ campaigns: CampaignSummary[]; total_activities: number }>;
    },
    staleTime: 30_000,
    enabled: !!accountId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const campaigns = data?.campaigns || [];

  if (campaigns.length === 0) {
    return (
      <div className="text-center py-12">
        <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold mb-2">No Campaign Activity Yet</h3>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Start chatting with your campaigns using the specialist roles. Activities will appear here as the team works.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold flex items-center gap-2">
          <Activity className="h-4 w-4" />
          Recent Campaign Activity
        </h3>
        <span className="text-[10px] text-muted-foreground">
          {data?.total_activities || 0} total actions across {campaigns.length} campaigns
        </span>
      </div>

      <div className="space-y-2">
        {campaigns.map((campaign) => {
          const isExpanded = expandedId === campaign.campaign_id;
          return (
            <div
              key={campaign.campaign_id}
              className="border border-border rounded-lg overflow-hidden hover:border-primary/30 transition-colors"
            >
              {/* Campaign header */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : campaign.campaign_id)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-secondary/30 transition-colors text-left"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold truncate">{campaign.campaign_name}</h4>
                    <span className="text-[9px] text-muted-foreground flex items-center gap-0.5">
                      <Clock className="h-2.5 w-2.5" />
                      {relativeTime(campaign.last_activity)}
                    </span>
                  </div>
                  {/* Role avatars strip */}
                  <div className="flex items-center gap-1 mt-1">
                    {campaign.active_roles.slice(0, 5).map((roleId) => {
                      const Icon = AVATAR_ICONS[
                        roleId === 'ppc_strategist' ? 'target' :
                        roleId === 'search_term_hunter' ? 'search' :
                        roleId === 'creative_director' ? 'palette' :
                        roleId === 'analytics_analyst' ? 'chart' :
                        roleId === 'competitor_intel' ? 'eye' :
                        roleId === 'gtm_specialist' ? 'code' :
                        roleId === 'growth_hacker' ? 'rocket' :
                        roleId === 'cro_specialist' ? 'gauge' :
                        'briefcase'
                      ] || Briefcase;
                      return (
                        <span
                          key={roleId}
                          className={cn('p-1 rounded', ROLE_COLORS[roleId] || 'text-gray-400')}
                          title={roleId.replace(/_/g, ' ')}
                        >
                          <Icon className="h-3 w-3" />
                        </span>
                      );
                    })}
                    <span className="text-[9px] text-muted-foreground ml-1">
                      {campaign.total_activities} actions
                    </span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedCampaign(campaign.campaign_id);
                  }}
                  className="p-1.5 rounded hover:bg-primary/10 transition-colors shrink-0"
                  title="Open campaign"
                >
                  <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              </button>

              {/* Expanded activity timeline */}
              {isExpanded && (
                <div className="px-4 pb-3 pt-1 border-t border-border/50">
                  <div className="space-y-1.5 pl-2 border-l-2 border-border ml-2">
                    {campaign.recent_activities.map((act, i) => {
                      const Icon = AVATAR_ICONS[act.avatar] || Briefcase;
                      return (
                        <div key={i} className="flex items-start gap-2 pl-3 py-1 relative">
                          {/* Timeline dot */}
                          <div className={cn(
                            'absolute -left-[7px] top-2.5 h-3 w-3 rounded-full border-2 border-background',
                            i === 0 ? 'bg-primary' : 'bg-muted-foreground/30',
                          )} />
                          <Icon className={cn('h-3.5 w-3.5 mt-0.5 shrink-0', ROLE_COLORS[act.role_id] || 'text-gray-400')} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={cn('text-[10px] font-semibold', ROLE_COLORS[act.role_id] || '')}>
                                {act.role}
                              </span>
                              <span className="text-[9px] text-muted-foreground">{relativeTime(act.timestamp)}</span>
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                              {act.action.replace(/[*#]/g, '').trim()}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <button
                    onClick={() => setSelectedCampaign(campaign.campaign_id)}
                    className="mt-2 text-[10px] text-primary hover:underline ml-6"
                  >
                    View full campaign →
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
