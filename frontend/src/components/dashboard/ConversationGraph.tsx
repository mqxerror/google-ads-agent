import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useAppStore } from '@/stores/appStore';
import { ChevronRight, ChevronDown, MessageSquare, GitBranch, Zap, Users, FolderOpen } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Decision {
  id: string;
  action: string;
  outcome: string;
  role: string;
  created_at: string;
}

interface Recommendation {
  id: string;
  action_type: string;
  action_detail: string;
  outcome: string | null;
  status: string;
  executed_at: string;
}

interface ConversationNode {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  decisions: Decision[];
  recommendations: Recommendation[];
}

interface CampaignGroup {
  campaign_id: string | null;
  campaign_name: string;
  conversations: ConversationNode[];
  decision_count: number;
}

interface GraphData {
  campaigns: CampaignGroup[];
  stats: {
    total_conversations: number;
    total_decisions: number;
    total_recommendations: number;
    roles_used: Array<{ id: string; name: string }>;
    campaigns_count: number;
  };
}

async function fetchGraph(accountId: string): Promise<GraphData> {
  const res = await fetch(`/api/accounts/${accountId}/conversation-graph`);
  if (!res.ok) throw new Error('Failed to fetch graph');
  return res.json();
}

export default function ConversationGraph() {
  const accountId = useClientAccountId();

  const { data, isLoading } = useQuery({
    queryKey: ['conversation-graph', accountId],
    queryFn: () => fetchGraph(accountId),
    staleTime: 30_000,
    enabled: !!accountId,
  });

  if (isLoading) return <div className="text-xs text-muted-foreground">Loading graph...</div>;
  if (!data || data.campaigns.length === 0) {
    return (
      <div className="border border-dashed border-border rounded-lg p-6 text-center">
        <GitBranch className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
        <p className="text-sm font-medium">No conversations yet</p>
        <p className="text-xs text-muted-foreground mt-1">Start chatting with campaigns to see the conversation map.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" /> {data.stats.total_conversations} conversations</span>
        <span className="flex items-center gap-1"><Zap className="h-3 w-3" /> {data.stats.total_decisions} decisions</span>
        <span className="flex items-center gap-1"><FolderOpen className="h-3 w-3" /> {data.stats.campaigns_count} campaigns</span>
        {data.stats.roles_used.length > 0 && (
          <span className="flex items-center gap-1"><Users className="h-3 w-3" /> {data.stats.roles_used.length} roles</span>
        )}
      </div>

      {/* Campaign tree */}
      <div className="space-y-1">
        {data.campaigns.map((camp) => (
          <CampaignNode key={camp.campaign_id ?? 'general'} campaign={camp} />
        ))}
      </div>
    </div>
  );
}

function CampaignNode({ campaign }: { campaign: CampaignGroup }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left px-2 py-1.5 rounded-md hover:bg-secondary/50 transition-colors"
      >
        {expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
        <FolderOpen className="h-3.5 w-3.5 text-primary" />
        <span className="text-sm font-medium flex-1">{campaign.campaign_name}</span>
        <span className="text-[10px] text-muted-foreground">
          {campaign.conversations.length} conv{campaign.conversations.length !== 1 ? 's' : ''}
          {campaign.decision_count > 0 && ` \u00b7 ${campaign.decision_count} decisions`}
        </span>
      </button>

      {expanded && (
        <div className="ml-5 pl-3 border-l border-border space-y-0.5">
          {campaign.conversations.map((conv) => (
            <ConversationNode key={conv.id} conversation={conv} campaignId={campaign.campaign_id} />
          ))}
        </div>
      )}
    </div>
  );
}

function ConversationNode({ conversation, campaignId }: { conversation: ConversationNode; campaignId: string | null }) {
  const [expanded, setExpanded] = useState(false);
  const { setSelectedCampaign } = useAppStore();
  const hasActions = conversation.decisions.length > 0 || conversation.recommendations.length > 0;

  const handleClick = () => {
    if (campaignId) {
      setSelectedCampaign(campaignId);
    }
  };

  const dateStr = conversation.updated_at?.slice(5, 10) || conversation.created_at?.slice(5, 10) || '';

  return (
    <div>
      <div className="flex items-center gap-1.5 group">
        {hasActions ? (
          <button onClick={() => setExpanded(!expanded)} className="p-0.5">
            {expanded ? <ChevronDown className="h-3 w-3 text-muted-foreground" /> : <ChevronRight className="h-3 w-3 text-muted-foreground" />}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <button
          onClick={handleClick}
          className="flex items-center gap-1.5 flex-1 text-left py-1 px-1 rounded hover:bg-secondary/30 transition-colors min-w-0"
        >
          <MessageSquare className="h-3 w-3 text-muted-foreground shrink-0" />
          <span className="text-xs truncate flex-1">{conversation.title || 'Untitled'}</span>
          <span className="text-[10px] text-muted-foreground shrink-0">{conversation.message_count} msgs</span>
          <span className="text-[10px] text-muted-foreground shrink-0">{dateStr}</span>
        </button>
      </div>

      {expanded && hasActions && (
        <div className="ml-8 pl-2 border-l border-border/50 space-y-0.5 py-0.5">
          {conversation.recommendations.map((rec) => (
            <div key={rec.id} className="flex items-center gap-1.5 text-[10px] py-0.5">
              <OutcomeDot outcome={rec.outcome} status={rec.status} />
              <span className="truncate flex-1">{rec.action_detail}</span>
              <span className="text-muted-foreground">{rec.executed_at?.slice(5, 10)}</span>
            </div>
          ))}
          {conversation.decisions.map((dec) => (
            <div key={dec.id} className="flex items-center gap-1.5 text-[10px] py-0.5">
              <Zap className="h-2.5 w-2.5 text-amber-500 shrink-0" />
              <span className="truncate flex-1">{dec.action}</span>
              {dec.role && <span className="text-muted-foreground">{dec.role}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function OutcomeDot({ outcome, status }: { outcome: string | null; status: string }) {
  if (status !== 'measured') {
    return <span className={cn('w-2 h-2 rounded-full shrink-0', 'bg-gray-300 animate-pulse')} title="Pending" />;
  }
  const colors: Record<string, string> = {
    improved: 'bg-emerald-500',
    degraded: 'bg-red-500',
    no_change: 'bg-yellow-500',
  };
  return <span className={cn('w-2 h-2 rounded-full shrink-0', colors[outcome || ''] || 'bg-gray-300')} title={outcome || ''} />;
}
