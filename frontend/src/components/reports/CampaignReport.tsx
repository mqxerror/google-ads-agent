import { useQuery } from '@tanstack/react-query';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { FileText, Download, Printer, BarChart3, Users, Pin, Clock, Target } from 'lucide-react';
import { Button } from '@/components/ui/button';
import AgentAvatar from '@/components/chat/AgentAvatar';
import { getAgentProfile } from '@/lib/agentProfiles';

interface ReportData {
  campaign_id: string;
  campaign_name: string;
  generated_at: string;
  summary: {
    total_impressions: number;
    total_clicks: number;
    total_cost: number;
    total_conversions: number;
    avg_ctr: number;
    avg_cpa: number;
    days_of_data: number;
    decision_count: number;
    conversation_count: number;
  };
  daily_metrics: Array<{
    date: string;
    impressions: number;
    clicks: number;
    cost_micros: number;
    conversions: number;
    ctr: number;
  }>;
  role_findings: Array<{
    role_id: string;
    role_name: string;
    content: string;
    size: number;
  }>;
  pinned_facts: string[];
  chronicle: string;
  profile: string;
}

async function fetchReport(accountId: string, campaignId: string): Promise<ReportData> {
  const res = await fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/report`);
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}

export default function CampaignReport({ campaignId }: { campaignId: string }) {
  const accountId = useClientAccountId();

  const { data: report, isLoading } = useQuery({
    queryKey: ['campaign-report', accountId, campaignId],
    queryFn: () => fetchReport(accountId, campaignId),
    staleTime: 60_000,
    enabled: !!accountId && !!campaignId,
  });

  if (isLoading) return <div className="p-6 text-muted-foreground">Generating report...</div>;
  if (!report) return <div className="p-6 text-muted-foreground">No report data available.</div>;

  const s = report.summary;

  const handleDownloadHtml = () => {
    window.open(`/api/accounts/${accountId}/campaigns/${campaignId}/report/html`, '_blank');
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="max-w-4xl mx-auto p-6 print:p-4">
      {/* Action buttons (hidden on print) */}
      <div className="flex gap-2 mb-6 print:hidden">
        <Button variant="outline" size="sm" className="gap-1.5" onClick={handleDownloadHtml}>
          <Download className="h-3.5 w-3.5" />
          Download HTML
        </Button>
        <Button variant="outline" size="sm" className="gap-1.5" onClick={handlePrint}>
          <Printer className="h-3.5 w-3.5" />
          Print / Save PDF
        </Button>
      </div>

      {/* Report Header */}
      <div className="border-b-2 border-primary pb-4 mb-6">
        <h1 className="text-2xl font-bold">{report.campaign_name}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Campaign Report · Generated {report.generated_at} · {s.days_of_data} days of data
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        <MetricCard icon={<BarChart3 />} label="Impressions" value={s.total_impressions.toLocaleString()} sub={`${s.days_of_data} days`} />
        <MetricCard icon={<Target />} label="Clicks" value={s.total_clicks.toLocaleString()} sub={`CTR: ${s.avg_ctr}%`} />
        <MetricCard label="Total Cost" value={`$${s.total_cost.toLocaleString()}`} />
        <MetricCard label="Conversions" value={String(s.total_conversions)} sub={`CPA: $${s.avg_cpa.toFixed(2)}`} />
        <MetricCard icon={<FileText />} label="Decisions" value={String(s.decision_count)} />
        <MetricCard icon={<Users />} label="Conversations" value={String(s.conversation_count)} />
      </div>

      {/* Daily Performance Table */}
      {report.daily_metrics.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold border-b border-border pb-2 mb-4">Daily Performance</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-secondary/50">
                  <th className="text-left p-2 font-medium">Date</th>
                  <th className="text-right p-2 font-medium">Impressions</th>
                  <th className="text-right p-2 font-medium">Clicks</th>
                  <th className="text-right p-2 font-medium">CTR</th>
                  <th className="text-right p-2 font-medium">Cost</th>
                  <th className="text-right p-2 font-medium">Conv</th>
                </tr>
              </thead>
              <tbody>
                {report.daily_metrics.slice(0, 14).map((m) => (
                  <tr key={m.date} className="border-b border-border/30 hover:bg-secondary/20">
                    <td className="p-2">{m.date}</td>
                    <td className="p-2 text-right tabular-nums">{m.impressions.toLocaleString()}</td>
                    <td className="p-2 text-right tabular-nums">{m.clicks.toLocaleString()}</td>
                    <td className="p-2 text-right tabular-nums">{m.ctr?.toFixed(1)}%</td>
                    <td className="p-2 text-right tabular-nums">${(m.cost_micros / 1_000_000).toFixed(2)}</td>
                    <td className="p-2 text-right tabular-nums">{m.conversions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Role Findings */}
      {report.role_findings.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold border-b border-border pb-2 mb-4">Role Findings</h2>
          <div className="space-y-4">
            {report.role_findings.map((rf) => {
              const profile = getAgentProfile(rf.role_id);
              return (
                <div key={rf.role_id} className="bg-card border border-border rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <AgentAvatar roleId={rf.role_id} size="sm" />
                    <div>
                      <span className="text-sm font-semibold" style={{ color: profile.color }}>{profile.name}</span>
                      <span className="text-xs text-muted-foreground ml-2">{rf.role_name}</span>
                    </div>
                  </div>
                  <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-sans max-h-60 overflow-y-auto">
                    {rf.content.slice(0, 3000)}
                  </pre>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Pinned Facts */}
      {report.pinned_facts.length > 0 && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold border-b border-border pb-2 mb-4">
            <Pin className="inline h-4 w-4 mr-1" /> Pinned Facts
          </h2>
          <ul className="space-y-2">
            {report.pinned_facts.map((f, i) => (
              <li key={i} className="text-sm bg-amber-500/5 border-l-3 border-amber-500 pl-3 py-2 rounded-r-lg">
                {f}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Chronicle */}
      {report.chronicle && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold border-b border-border pb-2 mb-4">
            <Clock className="inline h-4 w-4 mr-1" /> Campaign Chronicle
          </h2>
          <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-sans bg-card border border-border rounded-xl p-4 max-h-96 overflow-y-auto">
            {report.chronicle}
          </pre>
        </section>
      )}

      {/* Footer */}
      <div className="mt-12 pt-4 border-t border-border text-center text-[10px] text-muted-foreground">
        Generated by Google Ads Agent · {report.generated_at}
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value, sub }: { icon?: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] mb-1">
        {icon && <span className="h-3.5 w-3.5">{icon}</span>}
        {label}
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}
