import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useAppStore } from '@/stores/appStore';
import {
  Brain, Pin, FileText, MessageSquare, Users, Target, BookOpen,
  ChevronDown, ChevronRight, Save, BarChart3, Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface MemoryData {
  campaign_id: string;
  chronicle: { exists: boolean; entries: number; size_kb: number; tokens: number; content: string };
  pinned_facts: { count: number; tokens: number; items: string[]; content: string };
  decisions: { total: number; tokens: number; content: string };
  role_notes: { roles: Array<{ role_id: string; role_name: string; size_kb: number; tokens: number }>; total_tokens: number };
  conversations: { count: number; messages: number; summaries: number };
  outcomes: { count: number };
  profile: { tokens: number; content: string };
  account_memory: { tokens: number; content: string };
  total_memory_tokens: number;
  context_budget: number;
  usage_percent: number;
}

async function fetchMemory(accountId: string, campaignId: string): Promise<MemoryData> {
  const res = await fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/memory-explorer`);
  if (!res.ok) throw new Error('Failed');
  return res.json();
}

export default function MemoryExplorer({ campaignId }: { campaignId: string }) {
  const accountId = useClientAccountId();

  const { data, isLoading } = useQuery({
    queryKey: ['memory-explorer', accountId, campaignId],
    queryFn: () => fetchMemory(accountId, campaignId),
    staleTime: 15_000,
    enabled: !!accountId && !!campaignId,
  });

  if (isLoading) return <div className="p-6 text-muted-foreground text-sm">Loading memory...</div>;
  if (!data) return <div className="p-6 text-muted-foreground text-sm">No memory data available.</div>;

  return (
    <div className="p-6 space-y-4 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" />
          <h2 className="text-base font-semibold">Campaign Memory</h2>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{formatTokens(data.total_memory_tokens)} tokens loaded</span>
          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full',
                data.usage_percent > 70 ? 'bg-yellow-500' : data.usage_percent > 85 ? 'bg-red-500' : 'bg-emerald-500'
              )}
              style={{ width: `${Math.min(data.usage_percent, 100)}%` }}
            />
          </div>
          <span>{data.usage_percent}% of budget</span>
        </div>
      </div>

      {/* Memory layers grid */}
      <div className="grid grid-cols-2 gap-3">
        <MemoryCard
          icon={<BookOpen className="h-4 w-4 text-blue-500" />}
          title="Chronicle"
          subtitle={data.chronicle.exists ? `${data.chronicle.entries} entries, ${data.chronicle.size_kb}KB` : 'Not started yet'}
          tokens={data.chronicle.tokens}
          status={data.chronicle.exists ? 'active' : 'empty'}
          content={data.chronicle.content}
          accountId={accountId}
          campaignId={campaignId}
          editable
          editEndpoint="chronicle"
        />

        <MemoryCard
          icon={<Pin className="h-4 w-4 text-amber-500" />}
          title="Pinned Facts"
          subtitle={`${data.pinned_facts.count} facts — always in context`}
          tokens={data.pinned_facts.tokens}
          status={data.pinned_facts.count > 0 ? 'active' : 'empty'}
          content={data.pinned_facts.content}
        />

        <MemoryCard
          icon={<FileText className="h-4 w-4 text-emerald-500" />}
          title="Decisions"
          subtitle={`${data.decisions.total} total — recent 20 detailed, older compressed`}
          tokens={data.decisions.tokens}
          status={data.decisions.total > 0 ? 'active' : 'empty'}
          content={data.decisions.content}
        />

        <MemoryCard
          icon={<Users className="h-4 w-4 text-purple-500" />}
          title="Role Notes"
          subtitle={`${data.role_notes.roles.length} roles`}
          tokens={data.role_notes.total_tokens}
          status={data.role_notes.roles.length > 0 ? 'active' : 'empty'}
        >
          <div className="space-y-1 mt-2">
            {data.role_notes.roles.map((r) => (
              <div key={r.role_id} className="flex items-center justify-between text-[10px]">
                <span>{r.role_name}</span>
                <span className="text-muted-foreground">{r.size_kb}KB ({formatTokens(r.tokens)})</span>
              </div>
            ))}
          </div>
        </MemoryCard>

        <MemoryCard
          icon={<MessageSquare className="h-4 w-4 text-cyan-500" />}
          title="Conversations"
          subtitle={`${data.conversations.count} convs, ${data.conversations.messages} msgs, ${data.conversations.summaries} summaries`}
          tokens={0}
          status="active"
          note="Agent loads: smart-selected 12 messages + all summaries (compressed by month)"
        />

        <MemoryCard
          icon={<Target className="h-4 w-4 text-rose-500" />}
          title="Outcomes"
          subtitle={`${data.outcomes.count} recommendations tracked`}
          tokens={0}
          status={data.outcomes.count > 0 ? 'active' : 'empty'}
          note="Measured after 7 days — success/failure fed back into skill evolution"
        />

        <MemoryCard
          icon={<BarChart3 className="h-4 w-4 text-indigo-500" />}
          title="Profile"
          subtitle="Campaign goals, constraints, phase"
          tokens={data.profile.tokens}
          status={data.profile.tokens > 100 ? 'active' : 'empty'}
          content={data.profile.content}
        />

        <MemoryCard
          icon={<Clock className="h-4 w-4 text-orange-500" />}
          title="Account Memory"
          subtitle="Cross-campaign insights"
          tokens={data.account_memory.tokens}
          status={data.account_memory.tokens > 10 ? 'active' : 'empty'}
          content={data.account_memory.content}
        />
      </div>

      {/* What agent sees vs misses */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="text-sm font-medium mb-2">What the Agent Sees</h3>
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div>
            <p className="text-emerald-600 font-medium mb-1">Always Loaded</p>
            <ul className="space-y-0.5 text-muted-foreground">
              <li>+ Chronicle (full history)</li>
              <li>+ Pinned facts (all)</li>
              <li>+ All role notes</li>
              <li>+ Profile & guidelines</li>
            </ul>
          </div>
          <div>
            <p className="text-amber-600 font-medium mb-1">Smart-Selected</p>
            <ul className="space-y-0.5 text-muted-foreground">
              <li>~ 12 of {data.conversations.messages} messages (by relevance)</li>
              <li>~ Recent 20 decisions (older compressed)</li>
              <li>~ Summaries (recent 5 full, older by month)</li>
            </ul>
          </div>
          <div>
            <p className="text-muted-foreground font-medium mb-1">Captured in Chronicle</p>
            <ul className="space-y-0.5 text-muted-foreground">
              <li>Old conversations → timeline entries</li>
              <li>Key metrics → milestones section</li>
              <li>Critical decisions → never-expire section</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function MemoryCard({
  icon, title, subtitle, tokens, status, content, children, note,
  editable, editEndpoint, accountId, campaignId,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  tokens: number;
  status: 'active' | 'empty';
  content?: string;
  children?: React.ReactNode;
  note?: string;
  editable?: boolean;
  editEndpoint?: string;
  accountId?: string;
  campaignId?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState('');
  const queryClient = useQueryClient();

  const handleSave = async () => {
    if (!editEndpoint || !accountId || !campaignId) return;
    await fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/${editEndpoint}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: editText }),
    });
    setEditing(false);
    queryClient.invalidateQueries({ queryKey: ['memory-explorer'] });
  };

  return (
    <div className={cn(
      'bg-card border rounded-lg p-3 transition-colors',
      status === 'active' ? 'border-border' : 'border-dashed border-border/50'
    )}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-sm font-medium flex-1">{title}</span>
        {tokens > 0 && <span className="text-[10px] text-muted-foreground">{formatTokens(tokens)}</span>}
        {(content || children) && (
          <button onClick={() => setExpanded(!expanded)} className="p-0.5">
            {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        )}
      </div>
      <p className="text-[10px] text-muted-foreground">{subtitle}</p>
      {note && <p className="text-[10px] text-muted-foreground/70 mt-0.5 italic">{note}</p>}

      {children}

      {expanded && content && (
        <div className="mt-2 border-t border-border pt-2">
          {editing ? (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                className="w-full h-48 bg-secondary/30 border border-border rounded p-2 text-[11px] font-mono resize-y focus:outline-none focus:ring-1 focus:ring-ring"
              />
              <div className="flex gap-1">
                <Button size="sm" className="h-6 text-[10px] gap-1" onClick={handleSave}><Save className="h-2.5 w-2.5" /> Save</Button>
                <Button size="sm" variant="outline" className="h-6 text-[10px]" onClick={() => setEditing(false)}>Cancel</Button>
              </div>
            </div>
          ) : (
            <div className="relative">
              <pre className="text-[10px] font-mono text-muted-foreground whitespace-pre-wrap max-h-48 overflow-y-auto">
                {content || 'Empty'}
              </pre>
              {editable && (
                <button
                  onClick={() => { setEditing(true); setEditText(content || ''); }}
                  className="absolute top-0 right-0 text-[10px] text-primary hover:underline"
                >
                  Edit
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
