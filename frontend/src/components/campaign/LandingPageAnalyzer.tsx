import { useState, useMemo, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
} from 'recharts';
import {
  Gauge, Zap, Search, Eye, Type, Shield, MousePointer,
  Link2, Activity, Smartphone, Users,
  AlertTriangle, Lightbulb, FlaskConical, Sparkles,
  RefreshCw, ExternalLink, Trash2, Loader2, ChevronDown,
  Flame, Dumbbell, Sprout, Send, CheckCircle2, TrendingUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchLandingPageAnalysis, clearLandingPageAnalysis } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface LandingPageAnalyzerProps {
  campaign: { id: string; name: string };
  accountId: string;
}

// ── Section icon mapping ─────────────────────────────────────────
const SECTION_ICON_MAP: { keywords: string[]; icon: typeof Zap }[] = [
  { keywords: ['performance', 'speed', 'lighthouse', 'core web'], icon: Zap },
  { keywords: ['dom', 'element', 'structure'], icon: Search },
  { keywords: ['visual', 'design', 'layout'], icon: Eye },
  { keywords: ['copy', 'headline', 'message', 'value prop'], icon: Type },
  { keywords: ['trust', 'badge', 'signal', 'review'], icon: Shield },
  { keywords: ['conversion element', 'cta', 'form', 'button'], icon: MousePointer },
  { keywords: ['ad', 'alignment', 'message match'], icon: Link2 },
  { keywords: ['tracking', 'gtm', 'pixel', 'analytics'], icon: Activity },
  { keywords: ['mobile', 'responsive', 'touch'], icon: Smartphone },
  { keywords: ['competitor', 'compare'], icon: Users },
  { keywords: ['ab test', 'a/b', 'experiment'], icon: FlaskConical },
  { keywords: ['cro score', 'calculation', 'overall'], icon: Gauge },
];

function iconForSection(title: string): typeof Zap {
  const t = title.toLowerCase();
  for (const m of SECTION_ICON_MAP) {
    if (m.keywords.some(k => t.includes(k))) return m.icon;
  }
  return Lightbulb;
}

interface ParsedSection {
  title: string;
  score?: number;
  grade?: string;
  body: string;
  number?: number;
}

interface ParsedReport {
  overallScore?: number;
  overallGrade?: string;
  url?: string;
  sections: ParsedSection[];
  recommendations: string[];
  abTests: string[];
  introContent: string;
}

interface ActionItem {
  title: string;
  detail?: string;
  bucket: 'today' | 'week' | 'month';
  impact?: string;
}

/** Parse markdown report to extract structure: STEP headings, scores, sections */
function parseMarkdownReport(markdown: string): ParsedReport {
  const result: ParsedReport = {
    sections: [],
    recommendations: [],
    abTests: [],
    introContent: '',
  };

  const urlMatch = markdown.match(/https?:\/\/[^\s)]+/);
  if (urlMatch) result.url = urlMatch[0];

  const overallMatch = markdown.match(/(?:CRO Score|Overall Score|Total Score|Final Score)[:\s]*(\d+)\s*\/\s*100/i);
  if (overallMatch) result.overallScore = parseInt(overallMatch[1], 10);

  const gradeMatch = markdown.match(/(?:Grade|Rating)[:\s]*([A-F][+-]?)/i);
  if (gradeMatch) result.overallGrade = gradeMatch[1];

  const sectionRegex = /(?:^|\n)#{1,3}\s*(?:STEP\s*(\d+)\s*[—\-:]?\s*)?([^\n]+)/gi;
  const matches = [...markdown.matchAll(sectionRegex)];

  if (matches.length > 0) {
    result.introContent = markdown.slice(0, matches[0].index || 0).trim();

    for (let i = 0; i < matches.length; i++) {
      const match = matches[i];
      const nextStart = i + 1 < matches.length ? matches[i + 1].index! : markdown.length;
      const sectionStart = (match.index || 0) + match[0].length;
      const body = markdown.slice(sectionStart, nextStart).trim();
      const title = match[2].trim().replace(/[*#]/g, '').trim();
      const number = match[1] ? parseInt(match[1], 10) : undefined;

      const scoreMatch = body.match(/Score:\s*(\d+)\s*\/\s*100\s*(?:\(([A-F][+-]?)\))?/i);
      const score = scoreMatch ? parseInt(scoreMatch[1], 10) : undefined;
      const grade = scoreMatch?.[2];

      if (i === 0 && /^(cro\s+analysis|landing\s+page|summary|overview)/i.test(title) && !score) {
        result.introContent = body;
        continue;
      }

      result.sections.push({ title, number, score, grade, body });
    }
  } else {
    result.introContent = markdown;
  }

  if (!result.overallScore && result.sections.length > 0) {
    const scored = result.sections.filter(s => s.score !== undefined);
    if (scored.length > 0) {
      const avg = scored.reduce((sum, s) => sum + (s.score || 0), 0) / scored.length;
      result.overallScore = Math.round(avg);
    }
  }

  return result;
}

function gradeFromScore(score: number): string {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
}

function getScoreColor(score: number): string {
  if (score >= 90) return 'text-emerald-500';
  if (score >= 75) return 'text-green-500';
  if (score >= 60) return 'text-yellow-500';
  if (score >= 40) return 'text-orange-500';
  return 'text-red-500';
}

function getScoreFill(score: number): string {
  if (score >= 90) return '#10b981';
  if (score >= 75) return '#22c55e';
  if (score >= 60) return '#eab308';
  if (score >= 40) return '#f97316';
  return '#ef4444';
}

function getScoreBg(score: number): string {
  if (score >= 90) return 'from-emerald-500/15 to-emerald-500/5 border-emerald-500/30';
  if (score >= 75) return 'from-green-500/15 to-green-500/5 border-green-500/30';
  if (score >= 60) return 'from-yellow-500/15 to-yellow-500/5 border-yellow-500/30';
  if (score >= 40) return 'from-orange-500/15 to-orange-500/5 border-orange-500/30';
  return 'from-red-500/15 to-red-500/5 border-red-500/30';
}

/** Generate one-sentence verdict from the report */
function extractVerdict(report: ParsedReport): string {
  const score = report.overallScore || 0;
  const weakSections = report.sections.filter(s => s.score !== undefined && s.score < 60);
  const strongSections = report.sections.filter(s => s.score !== undefined && s.score >= 80);

  if (score >= 90) return `Stellar landing page — only ${weakSections.length} minor improvements left.`;
  if (score >= 75) {
    if (weakSections.length === 0) return `Healthy page with consistent performance across all dimensions.`;
    return `Solid foundation, but ${weakSections.length} dimension${weakSections.length > 1 ? 's' : ''} need attention.`;
  }
  if (score >= 60) {
    if (weakSections.length > 0) {
      const worst = weakSections.sort((a, b) => (a.score || 0) - (b.score || 0))[0];
      return `Mid-tier performance — your weakest link is ${worst.title.replace(/^\d+\.\s*/, '')}.`;
    }
    return `Average page with room to grow. ${strongSections.length} strong areas, ${weakSections.length} weak.`;
  }
  if (score >= 40) {
    return `Multiple critical gaps — ${weakSections.length} dimension${weakSections.length > 1 ? 's are' : ' is'} hurting conversions.`;
  }
  return `This page is bleeding conversions across ${weakSections.length} critical dimensions. Triage time.`;
}

/** Find sections with critical issues (score < 60 or matching critical keywords) */
function extractCriticalAlerts(report: ParsedReport): ParsedSection[] {
  return report.sections
    .filter(s => s.score !== undefined && s.score < 60)
    .sort((a, b) => (a.score || 0) - (b.score || 0))
    .slice(0, 5);
}

/** Categorize recommendations into action buckets by section score */
function categorizeIssues(report: ParsedReport): ActionItem[] {
  const items: ActionItem[] = [];
  for (const s of report.sections) {
    if (s.score === undefined) continue;
    let bucket: 'today' | 'week' | 'month';
    if (s.score < 60) bucket = 'today';
    else if (s.score < 80) bucket = 'week';
    else bucket = 'month';

    // Try to extract first bullet/action from the body
    const firstBullet = s.body.match(/(?:^|\n)\s*[-*•]\s*(.+?)(?:\n|$)/);
    const detail = firstBullet ? firstBullet[1].replace(/[*_]/g, '').slice(0, 120) : undefined;

    items.push({
      title: s.title.replace(/^\d+\.\s*/, ''),
      detail,
      bucket,
      impact: s.score < 60 ? `Score ${s.score} → 80+` : s.score < 80 ? `Score ${s.score} → 90+` : `Score ${s.score} → 95+`,
    });
  }
  return items;
}

/** Animated count-up hook */
function useCountUp(target: number, duration = 1500): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    let start: number | null = null;
    const step = (ts: number) => {
      if (start === null) start = ts;
      const elapsed = ts - start;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [target, duration]);

  return value;
}

// ─── Sub-components ──────────────────────────────────────────────

function HeroVerdict({ score, grade, verdict, sectionCount, criticalCount }: {
  score: number;
  grade: string;
  verdict: string;
  sectionCount: number;
  criticalCount: number;
}) {
  const animated = useCountUp(score);
  const fillColor = getScoreFill(score);
  const circumference = 2 * Math.PI * 80;
  const offset = circumference - (animated / 100) * circumference;
  const quickWins = sectionCount - criticalCount;

  return (
    <div className={cn(
      'relative overflow-hidden rounded-2xl border bg-gradient-to-br p-8',
      getScoreBg(score),
    )}>
      <div className="flex items-center gap-8 relative z-10">
        {/* Animated score ring */}
        <div className="relative shrink-0">
          <svg width="200" height="200" className="-rotate-90">
            <circle cx="100" cy="100" r="80" fill="none" stroke="currentColor" strokeWidth="12" className="text-foreground/10" />
            <circle
              cx="100" cy="100" r="80"
              fill="none"
              stroke={fillColor}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              style={{ transition: 'stroke-dashoffset 1.5s cubic-bezier(0.16, 1, 0.3, 1)' }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className={cn('text-6xl font-bold tabular-nums', getScoreColor(score))}>{animated}</div>
            <div className="text-xs text-muted-foreground mt-1 tracking-wider">CRO SCORE</div>
            <Badge className={cn('mt-2 text-base font-bold px-3', getScoreColor(score))}>{grade}</Badge>
          </div>
        </div>

        {/* Verdict + quick stats */}
        <div className="flex-1">
          <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">The Verdict</div>
          <p className="text-2xl font-semibold leading-tight mb-6">{verdict}</p>

          <div className="flex gap-3 flex-wrap">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-background/60 backdrop-blur border border-border/50">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <div>
                <div className="text-lg font-bold leading-none">{criticalCount}</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Critical</div>
              </div>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-background/60 backdrop-blur border border-border/50">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <div>
                <div className="text-lg font-bold leading-none">{quickWins}</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Healthy</div>
              </div>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-background/60 backdrop-blur border border-border/50">
              <TrendingUp className="h-4 w-4 text-blue-500" />
              <div>
                <div className="text-lg font-bold leading-none">+{Math.max(0, 95 - score)}%</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Potential</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CriticalIssuesStrip({ alerts, onJump, onAskFix }: {
  alerts: ParsedSection[];
  onJump: (sectionTitle: string) => void;
  onAskFix: (section: ParsedSection) => void;
}) {
  if (alerts.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 to-emerald-500/5 p-4 flex items-center gap-3">
        <CheckCircle2 className="h-6 w-6 text-emerald-500 shrink-0" />
        <div>
          <div className="font-semibold text-sm">All major elements are healthy</div>
          <div className="text-xs text-muted-foreground">No critical issues found in the audit</div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle className="h-4 w-4 text-red-500 animate-pulse" />
        <h3 className="text-sm font-bold">
          {alerts.length} thing{alerts.length > 1 ? 's' : ''} bleeding conversions right now
        </h3>
      </div>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 snap-x">
        {alerts.map((alert, i) => {
          const Icon = iconForSection(alert.title);
          return (
            <div
              key={i}
              className={cn(
                'shrink-0 w-72 snap-start rounded-xl border p-4 cursor-pointer hover:scale-[1.02] transition-transform',
                'border-red-500/40 bg-gradient-to-br from-red-500/10 to-red-500/5',
                i === 0 && 'ring-2 ring-red-500/40 ring-offset-2 ring-offset-background',
              )}
              onClick={() => onJump(alert.title)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-red-500/20">
                    <Icon className="h-4 w-4 text-red-500" />
                  </div>
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                    {alert.title.replace(/^\d+\.\s*/, '').slice(0, 24)}
                  </span>
                </div>
                <div className="text-xl font-bold text-red-500">{alert.score}</div>
              </div>
              <p className="text-xs text-muted-foreground line-clamp-2 mb-3">
                {alert.body.replace(/[#*`|]/g, '').replace(/\s+/g, ' ').trim().slice(0, 100)}…
              </p>
              <Button
                size="sm"
                variant="outline"
                className="w-full text-xs border-red-500/40 hover:bg-red-500/10"
                onClick={(e) => { e.stopPropagation(); onAskFix(alert); }}
              >
                <Sparkles className="h-3 w-3 mr-1" /> Fix Now
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HealthRadar({ sections, onAxisClick }: {
  sections: ParsedSection[];
  onAxisClick: (sectionTitle: string) => void;
}) {
  const data = sections
    .filter(s => s.score !== undefined)
    .map(s => ({
      category: s.title.replace(/^\d+\.\s*/, '').slice(0, 18),
      fullTitle: s.title,
      score: s.score,
    }));

  if (data.length < 3) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-bold flex items-center gap-2">
            <Gauge className="h-4 w-4" />
            Health Radar
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">Click any axis to jump to details</p>
        </div>
        <div className="flex gap-3 text-[10px]">
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" /> 80+</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-yellow-500" /> 60-79</span>
          <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" /> &lt;60</span>
        </div>
      </div>
      <div className="h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data}>
            <PolarGrid stroke="currentColor" strokeOpacity={0.15} />
            <PolarAngleAxis
              dataKey="category"
              tick={(props: { x: number; y: number; payload: { value: string; index: number } }) => {
                const { x, y, payload } = props;
                const item = data[payload.index];
                const color = item.score! >= 80 ? '#10b981' : item.score! >= 60 ? '#eab308' : '#ef4444';
                return (
                  <g transform={`translate(${x},${y})`} className="cursor-pointer" onClick={() => onAxisClick(item.fullTitle)}>
                    <text x={0} y={0} dy={4} textAnchor="middle" fill={color} className="text-[11px] font-semibold">
                      {payload.value}
                    </text>
                    <text x={0} y={0} dy={18} textAnchor="middle" fill={color} className="text-[10px] font-bold">
                      {item.score}
                    </text>
                  </g>
                );
              }}
            />
            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10, fill: 'currentColor', opacity: 0.4 }} />
            <Radar
              name="Score"
              dataKey="score"
              stroke="#6366f1"
              fill="#6366f1"
              fillOpacity={0.35}
              strokeWidth={2}
              dot={{ r: 3, fill: '#6366f1' }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ActionQueue({ items, onSendToChat }: {
  items: ActionItem[];
  onSendToChat: (item: ActionItem) => void;
}) {
  const buckets = {
    today: items.filter(i => i.bucket === 'today'),
    week: items.filter(i => i.bucket === 'week'),
    month: items.filter(i => i.bucket === 'month'),
  };

  const columns = [
    { key: 'today' as const, label: 'Do Today', icon: Flame, color: 'red', items: buckets.today },
    { key: 'week' as const, label: 'Do This Week', icon: Dumbbell, color: 'orange', items: buckets.week },
    { key: 'month' as const, label: 'Do This Month', icon: Sprout, color: 'emerald', items: buckets.month },
  ];

  return (
    <div>
      <h3 className="text-sm font-bold mb-3 flex items-center gap-2">
        <Lightbulb className="h-4 w-4 text-yellow-500" />
        Action Queue
      </h3>
      <div className="grid gap-4 md:grid-cols-3">
        {columns.map((col) => {
          const Icon = col.icon;
          const colorMap: Record<string, string> = {
            red: 'border-red-500/30 bg-red-500/5',
            orange: 'border-orange-500/30 bg-orange-500/5',
            emerald: 'border-emerald-500/30 bg-emerald-500/5',
          };
          const headerColor: Record<string, string> = {
            red: 'text-red-500',
            orange: 'text-orange-500',
            emerald: 'text-emerald-500',
          };
          return (
            <div key={col.key} className={cn('rounded-xl border p-3', colorMap[col.color])}>
              <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border/50">
                <Icon className={cn('h-4 w-4', headerColor[col.color])} />
                <h4 className={cn('text-xs font-bold uppercase tracking-wider', headerColor[col.color])}>{col.label}</h4>
                <span className="ml-auto text-xs text-muted-foreground">{col.items.length}</span>
              </div>
              <div className="space-y-2">
                {col.items.length === 0 && (
                  <div className="text-xs text-muted-foreground italic text-center py-4">Nothing here — nice!</div>
                )}
                {col.items.map((item, i) => (
                  <div key={i} className="rounded-lg bg-background/60 border border-border/50 p-3 hover:border-border transition-colors">
                    <div className="text-sm font-semibold mb-1">{item.title}</div>
                    {item.detail && (
                      <div className="text-[11px] text-muted-foreground line-clamp-2 mb-2">{item.detail}</div>
                    )}
                    <div className="flex items-center justify-between mt-2">
                      {item.impact && (
                        <span className="text-[10px] text-muted-foreground font-mono">{item.impact}</span>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 text-[10px] px-2 ml-auto hover:bg-primary/10"
                        onClick={() => onSendToChat(item)}
                      >
                        <Send className="h-3 w-3 mr-1" /> Ask agent
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SectionAccordion({ sections, expandedId, onToggle }: {
  sections: ParsedSection[];
  expandedId: string | null;
  onToggle: (id: string) => void;
}) {
  return (
    <div>
      <h3 className="text-sm font-bold mb-3 flex items-center gap-2">
        <Search className="h-4 w-4" />
        Deep Dive ({sections.length} sections)
      </h3>
      <div className="space-y-2">
        {sections.map((section) => {
          const Icon = iconForSection(section.title);
          const isOpen = expandedId === section.title;
          const score = section.score;
          return (
            <div
              key={section.title}
              id={`section-${section.title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`}
              className={cn(
                'rounded-lg border transition-colors',
                score !== undefined && score < 60 && 'border-red-500/30',
                score !== undefined && score >= 60 && score < 80 && 'border-yellow-500/30',
                score !== undefined && score >= 80 && 'border-emerald-500/30',
                score === undefined && 'border-border',
              )}
            >
              <button
                onClick={() => onToggle(section.title)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-secondary/30 transition-colors text-left"
              >
                <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-sm font-semibold flex-1">{section.title}</span>
                {score !== undefined && (
                  <Badge className={cn('font-bold', getScoreColor(score))}>{score}</Badge>
                )}
                <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
              </button>
              {isOpen && (
                <div className="px-4 pb-4 pt-2 border-t border-border/50 prose prose-sm dark:prose-invert max-w-none
                  [&_p]:my-1.5 [&_p]:text-sm
                  [&_ul]:my-1.5 [&_ul]:pl-4 [&_ul]:text-sm
                  [&_li]:my-0.5
                  [&_strong]:text-foreground [&_strong]:font-semibold
                  [&_table]:text-xs [&_table]:my-2
                  [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1
                  [&_code]:text-xs [&_code]:bg-secondary/50 [&_code]:px-1 [&_code]:rounded
                  [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:my-2
                  [&_h4]:text-xs [&_h4]:font-semibold [&_h4]:my-1.5">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{section.body}</ReactMarkdown>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────

export default function LandingPageAnalyzer({ campaign, accountId }: LandingPageAnalyzerProps) {
  const queryClient = useQueryClient();
  const [showRawMd, setShowRawMd] = useState(false);
  const [expandedSectionId, setExpandedSectionId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['landing-page-analysis', accountId, campaign.id],
    queryFn: () => fetchLandingPageAnalysis(accountId, campaign.id),
    refetchInterval: 5000,
    staleTime: 0,
  });

  const parsedReport = useMemo(() => {
    if (!data?.raw_markdown) return null;
    return parseMarkdownReport(data.raw_markdown);
  }, [data?.raw_markdown]);

  const triggerCROAudit = () => {
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

Save the full analysis to campaign memory.`,
        roleId: 'cro_specialist',
      },
    });
    window.dispatchEvent(event);
  };

  const askAgentToFix = (sectionOrItem: ParsedSection | ActionItem) => {
    const title = 'title' in sectionOrItem ? sectionOrItem.title : sectionOrItem.title;
    const event = new CustomEvent('chat:send', {
      detail: {
        text: `As CRO Specialist, help me fix "${title}" on the "${campaign.name}" landing page. Walk me through the specific changes step by step, and use Chrome MCP to verify the change works.`,
        roleId: 'cro_specialist',
      },
    });
    window.dispatchEvent(event);
  };

  const jumpToSection = (sectionTitle: string) => {
    setExpandedSectionId(sectionTitle);
    setTimeout(() => {
      const id = `section-${sectionTitle.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`;
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 50);
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

  // ── Empty state ────────────────────────────────────────────
  if (!data?.has_data) {
    return (
      <div className="py-12">
        <div className="max-w-2xl mx-auto text-center">
          {/* Sample preview */}
          <div className="mb-8 opacity-40 pointer-events-none">
            <div className="rounded-2xl border border-border bg-gradient-to-br from-secondary/30 to-secondary/10 p-8">
              <div className="flex items-center gap-8">
                <div className="relative shrink-0">
                  <svg width="160" height="160" className="-rotate-90">
                    <circle cx="80" cy="80" r="64" fill="none" stroke="currentColor" strokeWidth="10" className="text-foreground/10" />
                    <circle cx="80" cy="80" r="64" fill="none" stroke="#6366f1" strokeWidth="10" strokeLinecap="round" strokeDasharray={402} strokeDashoffset={120} />
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <div className="text-5xl font-bold text-foreground/40">??</div>
                    <div className="text-[10px] text-muted-foreground tracking-wider mt-1">CRO SCORE</div>
                  </div>
                </div>
                <div className="flex-1 text-left">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">The Verdict</div>
                  <div className="h-6 bg-foreground/10 rounded mb-2" />
                  <div className="h-6 bg-foreground/10 rounded w-3/4 mb-4" />
                  <div className="flex gap-2">
                    <div className="h-12 w-20 bg-foreground/5 rounded-lg" />
                    <div className="h-12 w-20 bg-foreground/5 rounded-lg" />
                    <div className="h-12 w-20 bg-foreground/5 rounded-lg" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <Sparkles className="h-12 w-12 mx-auto text-primary mb-4" />
          <h3 className="text-2xl font-bold mb-2">Your landing page audit awaits</h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
            The CRO Specialist will analyze performance, copy, trust signals, and competitor pages to give you a score, prioritized fixes, and A/B test ideas.
          </p>
          <Button onClick={triggerCROAudit} size="lg" className="gap-2">
            <Sparkles className="h-4 w-4" />
            Run Full CRO Audit
          </Button>
          <p className="text-xs text-muted-foreground mt-4">
            Takes 3-5 minutes. Uses Chrome browser automation.
          </p>
        </div>
      </div>
    );
  }

  if (!parsedReport) return null;

  const overallScore = parsedReport.overallScore || 0;
  const grade = parsedReport.overallGrade || (overallScore ? gradeFromScore(overallScore) : 'N/A');
  const verdict = extractVerdict(parsedReport);
  const criticalAlerts = extractCriticalAlerts(parsedReport);
  const actionItems = categorizeIssues(parsedReport);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Top bar */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Gauge className="h-5 w-5" />
            Landing Page Analysis
          </h2>
          {parsedReport.url && (
            <a
              href={parsedReport.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-muted-foreground hover:text-primary inline-flex items-center gap-1 mt-1"
            >
              {parsedReport.url}
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowRawMd(!showRawMd)}>
            {showRawMd ? 'Hide Raw' : 'Raw'}
          </Button>
          <Button variant="outline" size="sm" onClick={triggerCROAudit}>
            <RefreshCw className="h-3 w-3 mr-1" /> Re-run
          </Button>
          <Button variant="outline" size="sm" onClick={handleClear}>
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* 1. Hero Verdict */}
      <HeroVerdict
        score={overallScore}
        grade={grade}
        verdict={verdict}
        sectionCount={parsedReport.sections.length}
        criticalCount={criticalAlerts.length}
      />

      {/* 2. Critical Issues Strip */}
      <CriticalIssuesStrip
        alerts={criticalAlerts}
        onJump={jumpToSection}
        onAskFix={askAgentToFix}
      />

      {/* 3. Health Radar */}
      <HealthRadar sections={parsedReport.sections} onAxisClick={jumpToSection} />

      {/* 4. Action Queue */}
      <ActionQueue items={actionItems} onSendToChat={askAgentToFix} />

      {/* 5. Section Accordion */}
      <SectionAccordion
        sections={parsedReport.sections}
        expandedId={expandedSectionId}
        onToggle={(id) => setExpandedSectionId(expandedSectionId === id ? null : id)}
      />

      {/* Raw markdown toggle */}
      {showRawMd && (
        <div>
          <h3 className="text-sm font-semibold mb-2">Raw Markdown</h3>
          <div className="bg-secondary/30 border border-border rounded-md p-4 max-h-[400px] overflow-y-auto">
            <pre className="text-xs whitespace-pre-wrap font-mono">{data.raw_markdown}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
