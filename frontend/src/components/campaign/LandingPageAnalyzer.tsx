import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Gauge, Zap, Search, Eye, Type, Shield, MousePointer,
  Link2, Activity, Smartphone, Users, Target,
  AlertTriangle, Lightbulb, FlaskConical, Sparkles,
  RefreshCw, ExternalLink, Trash2, Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchLandingPageAnalysis, clearLandingPageAnalysis } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';

interface LandingPageAnalyzerProps {
  campaign: { id: string; name: string };
  accountId: string;
}

const CATEGORY_ICONS: Record<string, typeof Zap> = {
  performance: Zap,
  dom_elements: Search,
  visual: Eye,
  copy: Type,
  trust_signals: Shield,
  conversion_elements: MousePointer,
  ad_alignment: Link2,
  tracking: Activity,
  mobile_ux: Smartphone,
  competitor: Users,
};

const CATEGORY_LABELS: Record<string, string> = {
  performance: 'Performance',
  dom_elements: 'DOM Elements',
  visual: 'Visual Design',
  copy: 'Copy Quality',
  trust_signals: 'Trust Signals',
  conversion_elements: 'Conversion Elements',
  ad_alignment: 'Ad Alignment',
  tracking: 'Conversion Tracking',
  mobile_ux: 'Mobile UX',
  competitor: 'Competitor Comparison',
};

function getScoreColor(score: number): string {
  if (score >= 90) return 'text-green-500';
  if (score >= 75) return 'text-emerald-500';
  if (score >= 60) return 'text-yellow-500';
  if (score >= 40) return 'text-orange-500';
  return 'text-red-500';
}

function getScoreBg(score: number): string {
  if (score >= 90) return 'bg-green-500/10 border-green-500/30';
  if (score >= 75) return 'bg-emerald-500/10 border-emerald-500/30';
  if (score >= 60) return 'bg-yellow-500/10 border-yellow-500/30';
  if (score >= 40) return 'bg-orange-500/10 border-orange-500/30';
  return 'bg-red-500/10 border-red-500/30';
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-700 dark:text-red-300 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-700 dark:text-orange-300 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-300 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-700 dark:text-blue-300 border-blue-500/30',
};

export default function LandingPageAnalyzer({ campaign, accountId }: LandingPageAnalyzerProps) {
  const queryClient = useQueryClient();
  const [showRawMd, setShowRawMd] = useState(false);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['landing-page-analysis', accountId, campaign.id],
    queryFn: () => fetchLandingPageAnalysis(accountId, campaign.id),
    refetchInterval: 5000, // Poll every 5s in case agent is running
    staleTime: 0,
  });

  const triggerCROAudit = () => {
    // Send a chat message to trigger CRO analysis
    const event = new CustomEvent('chat:send', {
      detail: {
        text: `As the CRO Specialist, run a comprehensive 12-point CRO audit for "${campaign.name}".

WORKFLOW:
1. Find the landing page URL from the campaign's ads (final_urls)
2. Run the FULL 12-step analysis using Chrome MCP browser tools
3. Score against industry benchmarks
4. Generate 5-8 A/B test ideas
5. Calculate CRO Score (0-100)
6. Analyze ad strength and suggest improvements

CRITICAL: Output structured data wrapped in <!-- STRUCTURED_DATA_START --> and <!-- STRUCTURED_DATA_END --> markers.
Save the full analysis to campaign memory.`,
        roleId: 'cro_specialist',
      },
    });
    window.dispatchEvent(event);
  };

  const handleClear = async () => {
    if (!confirm('Delete the current CRO analysis?')) return;
    await clearLandingPageAnalysis(accountId, campaign.id);
    queryClient.invalidateQueries({ queryKey: ['landing-page-analysis', accountId, campaign.id] });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Empty state — no analysis yet
  if (!data?.has_data) {
    return (
      <div className="py-12 text-center">
        <div className="max-w-md mx-auto">
          <Gauge className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No CRO Analysis Yet</h3>
          <p className="text-sm text-muted-foreground mb-6">
            Run a comprehensive landing page audit using the CRO Specialist.
            The agent will analyze performance, copy, trust signals, conversion elements,
            and competitor pages to give you a CRO score and prioritized recommendations.
          </p>
          <Button onClick={triggerCROAudit} size="lg" className="gap-2">
            <Sparkles className="h-4 w-4" />
            Run Full CRO Audit
          </Button>
          <p className="text-xs text-muted-foreground mt-4">
            Analysis takes 3-5 minutes and uses Chrome browser automation.
          </p>
        </div>
      </div>
    );
  }

  const { analysis, raw_markdown } = data;

  // Has data but no parsed JSON — show raw markdown
  if (!analysis) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Gauge className="h-5 w-5" />
            CRO Analysis (Raw)
          </h3>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={triggerCROAudit}>
              <RefreshCw className="h-3 w-3 mr-1" /> Re-run
            </Button>
            <Button variant="outline" size="sm" onClick={handleClear}>
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </div>
        <div className="bg-secondary/30 border border-border rounded-md p-4 max-h-[600px] overflow-y-auto">
          <pre className="text-xs whitespace-pre-wrap font-mono">{raw_markdown}</pre>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Gauge className="h-5 w-5" />
            Landing Page Analysis
          </h2>
          {analysis.url && (
            <a
              href={analysis.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground hover:text-primary inline-flex items-center gap-1 mt-1"
            >
              {analysis.url}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {analysis.analyzed_at && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Last analyzed: {new Date(analysis.analyzed_at).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowRawMd(!showRawMd)}>
            {showRawMd ? 'Hide' : 'Show'} Raw
          </Button>
          <Button variant="outline" size="sm" onClick={triggerCROAudit}>
            <RefreshCw className="h-3 w-3 mr-1" /> Re-run
          </Button>
          <Button variant="outline" size="sm" onClick={handleClear}>
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* CRO Score Card */}
      <div className={cn('border rounded-lg p-6', getScoreBg(analysis.cro_score))}>
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className={cn('text-6xl font-bold', getScoreColor(analysis.cro_score))}>
              {analysis.cro_score}
            </div>
            <div className="text-xs text-muted-foreground mt-1">CRO SCORE</div>
            {analysis.grade && (
              <Badge className={cn('mt-2 text-lg', getScoreColor(analysis.cro_score))}>
                {analysis.grade}
              </Badge>
            )}
          </div>
          <div className="flex-1">
            <h3 className="font-semibold mb-2">Executive Summary</h3>
            <p className="text-sm text-muted-foreground">{analysis.executive_summary}</p>
          </div>
        </div>
      </div>

      {/* Category Breakdown Grid */}
      {analysis.categories && Object.keys(analysis.categories).length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">
            Category Breakdown
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(analysis.categories).map(([key, cat]) => {
              const Icon = CATEGORY_ICONS[key] || Gauge;
              return (
                <div
                  key={key}
                  className={cn('border rounded-md p-3', getScoreBg(cat.score))}
                >
                  <div className="flex items-center justify-between mb-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className={cn('text-lg font-bold', getScoreColor(cat.score))}>
                      {cat.score}
                    </span>
                  </div>
                  <div className="text-xs font-medium">{CATEGORY_LABELS[key] || key}</div>
                  {cat.findings && cat.findings.length > 0 && (
                    <ul className="text-[10px] text-muted-foreground mt-2 space-y-0.5">
                      {cat.findings.slice(0, 2).map((f, i) => (
                        <li key={i} className="truncate">• {f}</li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Critical Issues */}
      {analysis.critical_issues && analysis.critical_issues.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-500" />
            Critical Issues
          </h3>
          <div className="space-y-2">
            {analysis.critical_issues.map((issue, i) => (
              <div key={i} className="border border-red-500/30 bg-red-500/5 rounded-md p-3">
                <div className="font-medium text-sm">{issue.title}</div>
                <p className="text-xs text-muted-foreground mt-1">{issue.fix}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {analysis.recommendations && analysis.recommendations.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-yellow-500" />
            Recommendations ({analysis.recommendations.length})
          </h3>
          <div className="space-y-2">
            {analysis.recommendations.map((rec, i) => (
              <div key={i} className="border border-border rounded-md p-3 hover:bg-secondary/30 transition-colors">
                <div className="flex items-start gap-3">
                  <Badge className={cn('text-[10px] uppercase border', PRIORITY_COLORS[rec.priority] || PRIORITY_COLORS.medium)}>
                    {rec.priority}
                  </Badge>
                  <div className="flex-1">
                    <div className="font-medium text-sm">{rec.title}</div>
                    <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                      <span>{rec.category}</span>
                      {rec.expected_impact && <span>Impact: {rec.expected_impact}</span>}
                      {rec.effort && <span>Effort: {rec.effort}</span>}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* A/B Test Ideas */}
      {analysis.ab_test_ideas && analysis.ab_test_ideas.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-purple-500" />
            A/B Test Ideas ({analysis.ab_test_ideas.length})
          </h3>
          <div className="space-y-2">
            {analysis.ab_test_ideas.map((idea, i) => (
              <div key={i} className="border border-purple-500/30 bg-purple-500/5 rounded-md p-3">
                <div className="text-sm">{idea.hypothesis}</div>
                <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                  <span>Impact: {idea.expected_impact}</span>
                  <span>Effort: {idea.effort}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Competitor Insights */}
      {analysis.competitor_insights && analysis.competitor_insights.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Users className="h-4 w-4 text-blue-500" />
            Competitor Insights
          </h3>
          <div className="grid gap-3 md:grid-cols-2">
            {analysis.competitor_insights.map((comp, i) => (
              <div key={i} className="border border-border rounded-md p-3">
                <div className="font-medium text-sm mb-2">{comp.competitor}</div>
                {comp.strengths && comp.strengths.length > 0 && (
                  <div className="mb-2">
                    <div className="text-[10px] uppercase text-green-500 font-semibold">Strengths</div>
                    <ul className="text-xs text-muted-foreground mt-1 space-y-0.5">
                      {comp.strengths.map((s, j) => <li key={j}>• {s}</li>)}
                    </ul>
                  </div>
                )}
                {comp.ideas_to_steal && comp.ideas_to_steal.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase text-blue-500 font-semibold">Steal These</div>
                    <ul className="text-xs text-muted-foreground mt-1 space-y-0.5">
                      {comp.ideas_to_steal.map((s, j) => <li key={j}>• {s}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Ad Strength Analysis */}
      {analysis.ad_strength_analysis && (
        <div>
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-amber-500" />
            Ad Strength Analysis
          </h3>
          <div className="border border-border rounded-md p-4 space-y-3">
            <div className="flex items-center gap-4">
              {analysis.ad_strength_analysis.current_rating && (
                <Badge className="text-sm">
                  Current: {analysis.ad_strength_analysis.current_rating}
                </Badge>
              )}
              {analysis.ad_strength_analysis.headlines_count !== undefined && (
                <span className="text-xs text-muted-foreground">
                  Headlines: {analysis.ad_strength_analysis.headlines_count}/15
                </span>
              )}
              {analysis.ad_strength_analysis.descriptions_count !== undefined && (
                <span className="text-xs text-muted-foreground">
                  Descriptions: {analysis.ad_strength_analysis.descriptions_count}/4
                </span>
              )}
            </div>
            {analysis.ad_strength_analysis.missing && analysis.ad_strength_analysis.missing.length > 0 && (
              <div>
                <div className="text-xs font-semibold mb-1">Missing:</div>
                <ul className="text-xs text-muted-foreground space-y-0.5">
                  {analysis.ad_strength_analysis.missing.map((m, i) => <li key={i}>• {m}</li>)}
                </ul>
              </div>
            )}
            {analysis.ad_strength_analysis.suggested_headlines && analysis.ad_strength_analysis.suggested_headlines.length > 0 && (
              <div>
                <div className="text-xs font-semibold mb-1">Suggested Headlines:</div>
                <ul className="text-xs text-muted-foreground space-y-0.5">
                  {analysis.ad_strength_analysis.suggested_headlines.map((h, i) => <li key={i}>• {h}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Raw markdown (toggle) */}
      {showRawMd && (
        <div>
          <h3 className="text-sm font-semibold mb-2">Raw Analysis</h3>
          <div className="bg-secondary/30 border border-border rounded-md p-4 max-h-[400px] overflow-y-auto">
            <pre className="text-xs whitespace-pre-wrap font-mono">{raw_markdown}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
