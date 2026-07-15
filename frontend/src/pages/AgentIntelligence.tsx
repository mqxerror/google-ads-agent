import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { Brain, Zap, TrendingUp, RotateCcw, ChevronRight, ArrowLeft, Save, GitCompareArrows as GitCompare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const ROLE_ICONS: Record<string, string> = {
  briefcase: '💼', target: '🎯', search: '🔍', palette: '🎨',
  chart: '📊', eye: '👁️', code: '💻', rocket: '🚀', gauge: '📏',
};

interface RoleSkill {
  role_id: string;
  role_name: string;
  avatar: string;
  version: number;
  versions_count: number;
  techniques_count: number;
  total_actions: number;
  measured_actions: number;
  improved_actions: number;
  success_rate: number | null;
  has_skill_file: boolean;
  last_optimized: string | null;
}

interface SkillDetail {
  role_id: string;
  content: string | null;
  versions: Array<{ version: number; created_at: string; size: number }>;
  version: number;
  skill_score: number;
  total_recommendations: number;
  measured: number;
  improved: number;
  success_rate: number | null;
}

async function fetchSkills(accountId: string): Promise<{ roles: RoleSkill[] }> {
  const res = await fetch(`/api/accounts/${accountId}/skills`);
  if (!res.ok) throw new Error('Failed');
  return res.json();
}

async function fetchSkillDetail(accountId: string, roleId: string): Promise<SkillDetail> {
  const res = await fetch(`/api/accounts/${accountId}/skills/${roleId}`);
  if (!res.ok) throw new Error('Failed');
  return res.json();
}

export default function AgentIntelligence({ onClose }: { onClose?: () => void }) {
  const accountId = useClientAccountId();
  const queryClient = useQueryClient();
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['skills', accountId],
    queryFn: () => fetchSkills(accountId),
    staleTime: 30_000,
    enabled: !!accountId,
  });

  const [optimizingAll, setOptimizingAll] = useState(false);
  const [optimizeAllResult, setOptimizeAllResult] = useState<string | null>(null);

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading agent intelligence...</div>;

  const roles = data?.roles || [];

  if (selectedRole) {
    return (
      <RoleDetail
        accountId={accountId}
        roleId={selectedRole}
        onBack={() => { setSelectedRole(null); queryClient.invalidateQueries({ queryKey: ['skills'] }); }}
      />
    );
  }

  const totalActions = roles.reduce((s, r) => s + r.total_actions, 0);
  const totalMeasured = roles.reduce((s, r) => s + r.measured_actions, 0);
  const totalImproved = roles.reduce((s, r) => s + r.improved_actions, 0);
  const overallRate = totalMeasured > 0 ? Math.round(totalImproved / totalMeasured * 100) : null;

  return (
    <div className="h-full overflow-y-auto">
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        {onClose && (
          <button onClick={onClose} className="p-1 hover:bg-secondary rounded" title="Back to campaigns">
            <ArrowLeft className="h-4 w-4" />
          </button>
        )}
        <Brain className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-lg font-semibold">Agent Intelligence</h1>
          <p className="text-xs text-muted-foreground">Self-improving role skills — autoresearch pattern</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="ml-auto gap-1.5"
          disabled={optimizingAll}
          onClick={async () => {
            setOptimizingAll(true);
            setOptimizeAllResult(null);
            try {
              const res = await fetch(`/api/accounts/${accountId}/skills/optimize-all`, { method: 'POST' });
              const data = await res.json();
              const results = data.results || [];
              const optimized = results.filter((r: any) => r.status === 'optimized').length;
              const skipped = results.filter((r: any) => r.status === 'skipped').length;
              const errors = results.filter((r: any) => r.status === 'error').length;
              setOptimizeAllResult(`Done: ${optimized} optimized, ${skipped} skipped, ${errors} errors`);
              queryClient.invalidateQueries({ queryKey: ['skills'] });
            } catch {
              setOptimizeAllResult('Error: optimization failed');
            } finally {
              setOptimizingAll(false);
            }
          }}
        >
          {optimizingAll ? (
            <><Zap className="h-3.5 w-3.5 animate-spin" /> Optimizing... (this takes ~2 min)</>
          ) : (
            <><Zap className="h-3.5 w-3.5" /> Optimize All</>
          )}
        </Button>
      </div>

      {/* Optimize all result */}
      {optimizeAllResult && (
        <div className={cn(
          'px-4 py-2 rounded-lg text-xs mb-4',
          optimizeAllResult.startsWith('Done') ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400' :
          'bg-red-500/10 text-red-700 dark:text-red-400'
        )}>
          {optimizeAllResult}
        </div>
      )}

      {/* Overall stats */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <StatCard label="Total Actions" value={String(totalActions)} />
        <StatCard label="Measured" value={String(totalMeasured)} />
        <StatCard label="Improved" value={String(totalImproved)} icon={<TrendingUp className="h-3.5 w-3.5 text-emerald-500" />} />
        <StatCard
          label="Overall Success"
          value={overallRate != null ? `${overallRate}%` : 'N/A'}
          color={overallRate && overallRate >= 70 ? 'text-emerald-600' : overallRate && overallRate >= 50 ? 'text-yellow-600' : undefined}
        />
      </div>

      {/* Role cards */}
      <div className="grid grid-cols-2 gap-3">
        {roles.map((role) => (
          <button
            key={role.role_id}
            onClick={() => setSelectedRole(role.role_id)}
            className="bg-card border border-border rounded-lg p-4 text-left hover:border-primary/50 hover:bg-secondary/20 transition-colors group"
          >
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">{ROLE_ICONS[role.avatar] || '🤖'}</span>
              <span className="font-medium text-sm flex-1">{role.role_name}</span>
              <span className="text-[10px] text-muted-foreground">v{role.version}</span>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground group-hover:text-foreground transition-colors" />
            </div>

            {/* Skill bar */}
            <div className="flex items-center gap-2 mb-2">
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    role.success_rate && role.success_rate >= 70 ? 'bg-emerald-500' :
                    role.success_rate && role.success_rate >= 50 ? 'bg-yellow-500' :
                    role.success_rate ? 'bg-red-500' : 'bg-muted-foreground/30'
                  )}
                  style={{ width: `${role.success_rate ?? 0}%` }}
                />
              </div>
              <span className="text-xs tabular-nums w-10 text-right">
                {role.success_rate != null ? `${role.success_rate}%` : '—'}
              </span>
            </div>

            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <span>{role.techniques_count} techniques</span>
              <span>{role.total_actions} actions</span>
              {role.last_optimized && <span>optimized {role.last_optimized}</span>}
            </div>
          </button>
        ))}
      </div>
    </div>
    </div>
  );
}

function RoleDetail({ accountId, roleId, onBack }: { accountId: string; roleId: string; onBack: () => void }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [optimizing, setOptimizing] = useState(false);
  const [optimizeResult, setOptimizeResult] = useState<string | null>(null);
  const [compareVersions, setCompareVersions] = useState<[number, number] | null>(null);
  const [compareContent, setCompareContent] = useState<{ old: string; new: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['skill-detail', accountId, roleId],
    queryFn: () => fetchSkillDetail(accountId, roleId),
    staleTime: 10_000,
  });

  if (isLoading || !data) return <div className="p-6 text-muted-foreground">Loading...</div>;

  const handleOptimize = async () => {
    setOptimizing(true);
    setOptimizeResult(null);
    try {
      const res = await fetch(`/api/accounts/${accountId}/skills/${roleId}/optimize`, { method: 'POST' });
      const result = await res.json();
      if (result.status === 'optimized') {
        setOptimizeResult(`Optimized v${result.from_version} → v${result.to_version} (score ${result.score_before} → ${result.score_after})`);
      } else if (result.status === 'skipped') {
        setOptimizeResult(`Skipped: ${result.reason}`);
      } else if (result.status === 'discarded') {
        setOptimizeResult(`Discarded: ${result.reason}`);
      } else {
        setOptimizeResult(`${result.status}: ${result.reason || 'Unknown'}`);
      }
      queryClient.invalidateQueries({ queryKey: ['skill-detail'] });
    } catch (e) {
      setOptimizeResult('Error: optimization failed');
    } finally {
      setOptimizing(false);
    }
  };

  const handleSave = async () => {
    await fetch(`/api/accounts/${accountId}/skills/${roleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: editContent }),
    });
    setEditing(false);
    queryClient.invalidateQueries({ queryKey: ['skill-detail'] });
  };

  const handleRollback = async (version: number) => {
    await fetch(`/api/accounts/${accountId}/skills/${roleId}/rollback/${version}`, { method: 'POST' });
    queryClient.invalidateQueries({ queryKey: ['skill-detail'] });
  };

  return (
    <div className="h-full overflow-y-auto">
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={onBack} className="p-1 hover:bg-secondary rounded">
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <h2 className="text-lg font-semibold">{roleId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</h2>
          <p className="text-xs text-muted-foreground">
            Version {data.version} | Score: {data.skill_score} |
            {data.success_rate != null ? ` Success: ${data.success_rate}%` : ' No outcomes yet'}
          </p>
        </div>
        <Button variant="outline" size="sm" className="gap-1.5" onClick={handleOptimize} disabled={optimizing}>
          <Zap className="h-3.5 w-3.5" />
          {optimizing ? 'Optimizing...' : 'Optimize Now'}
        </Button>
        {!editing ? (
          <Button variant="outline" size="sm" onClick={() => { setEditing(true); setEditContent(data.content || ''); }}>
            Edit Skill
          </Button>
        ) : (
          <Button size="sm" className="gap-1.5" onClick={handleSave}>
            <Save className="h-3.5 w-3.5" />
            Save
          </Button>
        )}
      </div>

      {/* Optimize result message */}
      {optimizeResult && (
        <div className={cn(
          'px-4 py-2 rounded-lg text-xs mb-4',
          optimizeResult.startsWith('Optimized') ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400' :
          optimizeResult.startsWith('Skipped') ? 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400' :
          'bg-red-500/10 text-red-700 dark:text-red-400'
        )}>
          {optimizeResult}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        <StatCard label="Version" value={`v${data.version}`} />
        <StatCard label="Skill Score" value={String(data.skill_score)} />
        <StatCard label="Recommendations" value={`${data.improved}/${data.measured}`} />
        <StatCard
          label="Success Rate"
          value={data.success_rate != null ? `${data.success_rate}%` : 'N/A'}
          color={data.success_rate && data.success_rate >= 70 ? 'text-emerald-600' : undefined}
        />
      </div>

      {/* Skill content */}
      <div className="bg-card border border-border rounded-lg p-4 mb-6">
        <h3 className="text-sm font-medium mb-3">Current Skill File</h3>
        {editing ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full h-96 bg-secondary/30 border border-border rounded-md p-3 text-xs font-mono resize-y focus:outline-none focus:ring-1 focus:ring-ring"
          />
        ) : (
          <pre className="text-xs font-mono whitespace-pre-wrap text-muted-foreground max-h-96 overflow-y-auto">
            {data.content || 'No skill file yet. Click "Optimize Now" to generate one.'}
          </pre>
        )}
      </div>

      {/* Version history + compare */}
      {data.versions.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-4">
          <h3 className="text-sm font-medium mb-3">Version History</h3>
          <div className="space-y-1.5">
            {data.versions.map((v, idx) => (
              <div key={v.version} className="flex items-center gap-3 text-xs py-1">
                <span className={cn(
                  'font-mono font-medium',
                  v.version === data.version ? 'text-primary' : 'text-muted-foreground'
                )}>
                  v{v.version}
                </span>
                <span className="text-muted-foreground flex-1">{v.created_at.slice(0, 16)}</span>
                <span className="text-muted-foreground">{Math.round(v.size / 1024 * 10) / 10}KB</span>
                {idx > 0 && (
                  <button
                    onClick={async () => {
                      const prev = data.versions[idx - 1].version;
                      const curr = v.version;
                      setCompareVersions([prev, curr]);
                      const [oldRes, newRes] = await Promise.all([
                        fetch(`/api/accounts/${accountId}/skills/${roleId}/versions/${prev}`).then(r => r.json()),
                        fetch(`/api/accounts/${accountId}/skills/${roleId}/versions/${curr}`).then(r => r.json()),
                      ]);
                      setCompareContent({ old: oldRes.content || '', new: newRes.content || '' });
                    }}
                    className="flex items-center gap-1 text-blue-500 hover:text-blue-700"
                    title={`Compare v${data.versions[idx-1].version} → v${v.version}`}
                  >
                    <GitCompare className="h-3 w-3" />
                    Compare
                  </button>
                )}
                {v.version !== data.version && (
                  <button
                    onClick={() => handleRollback(v.version)}
                    className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
                    title={`Rollback to v${v.version}`}
                  >
                    <RotateCcw className="h-3 w-3" />
                    Rollback
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Version diff viewer */}
      {compareVersions && compareContent && (
        <div className="bg-card border border-border rounded-lg p-4 mt-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">
              Comparing v{compareVersions[0]} → v{compareVersions[1]}
            </h3>
            <button
              onClick={() => { setCompareVersions(null); setCompareContent(null); }}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>
          <SkillDiff oldText={compareContent.old} newText={compareContent.new} />
        </div>
      )}
    </div>
    </div>
  );
}

function SkillDiff({ oldText, newText }: { oldText: string; newText: string }) {
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');

  // Simple line-by-line diff
  const oldSet = new Set(oldLines.map(l => l.trim()));
  const newSet = new Set(newLines.map(l => l.trim()));

  const removed = oldLines.filter(l => l.trim() && !newSet.has(l.trim()));
  const added = newLines.filter(l => l.trim() && !oldSet.has(l.trim()));
  const unchanged = newLines.filter(l => l.trim() && oldSet.has(l.trim()));

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className="flex gap-4 text-xs">
        <span className="text-emerald-600">+{added.length} added</span>
        <span className="text-red-500">-{removed.length} removed</span>
        <span className="text-muted-foreground">{unchanged.length} unchanged</span>
      </div>

      {/* Added lines */}
      {added.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-emerald-600 mb-1">Added</p>
          <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-md p-2 space-y-0.5">
            {added.map((line, i) => (
              <div key={i} className="text-[11px] font-mono text-emerald-700 dark:text-emerald-400">
                <span className="text-emerald-500 mr-1">+</span>{line}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Removed lines */}
      {removed.length > 0 && (
        <div>
          <p className="text-[10px] font-medium text-red-500 mb-1">Removed</p>
          <div className="bg-red-500/5 border border-red-500/20 rounded-md p-2 space-y-0.5">
            {removed.map((line, i) => (
              <div key={i} className="text-[11px] font-mono text-red-700 dark:text-red-400">
                <span className="text-red-500 mr-1">-</span>{line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }: {
  label: string; value: string; icon?: React.ReactNode; color?: string;
}) {
  return (
    <div className="bg-card border border-border rounded-lg p-3">
      <div className="flex items-center gap-1.5 text-muted-foreground text-[10px] mb-1">
        {icon}
        {label}
      </div>
      <div className={cn('text-lg font-semibold', color)}>{value}</div>
    </div>
  );
}
