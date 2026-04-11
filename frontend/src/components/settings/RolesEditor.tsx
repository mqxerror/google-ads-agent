import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Loader2, Save, RotateCcw, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import { fetchRoles, fetchRoleDetail, customizeRole, resetRole, type AgencyRoleSummary } from '@/lib/api';

const ROLE_ICONS: Record<string, string> = {
  briefcase: '💼', target: '🎯', search: '🔍', palette: '🎨',
  chart: '📊', eye: '👁️', code: '💻', rocket: '🚀', gauge: '📈',
};

interface RoleRowProps {
  role: AgencyRoleSummary;
  isOpen: boolean;
  onToggle: () => void;
}

function RoleRow({ role, isOpen, onToggle }: RoleRowProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(role.name);
  const [specialty, setSpecialty] = useState(role.specialty);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: detail, isLoading } = useQuery({
    queryKey: ['role-detail', role.id],
    queryFn: () => fetchRoleDetail(role.id),
    enabled: isOpen,
    staleTime: 60_000,
  });

  // Initialize editor fields when detail loads
  if (detail && systemPrompt === '' && !dirty) {
    setName(detail.name);
    setSpecialty(detail.specialty);
    setSystemPrompt(detail.system_prompt);
  }

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      await customizeRole(role.id, { name, specialty, system_prompt: systemPrompt });
      setDirty(false);
      setFeedback('Saved');
      queryClient.invalidateQueries({ queryKey: ['role-detail', role.id] });
      queryClient.invalidateQueries({ queryKey: ['roles-list'] });
      setTimeout(() => setFeedback(null), 2000);
    } catch (e) {
      setFeedback(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm(`Reset "${role.name}" to its default system prompt? Your customizations will be lost.`)) return;
    setResetting(true);
    try {
      await resetRole(role.id);
      setDirty(false);
      setSystemPrompt('');
      setFeedback('Reset to default — restart backend to apply');
      queryClient.invalidateQueries({ queryKey: ['role-detail', role.id] });
      queryClient.invalidateQueries({ queryKey: ['roles-list'] });
      setTimeout(() => setFeedback(null), 4000);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className={cn(
      'border rounded-lg transition-colors',
      role.customized ? 'border-blue-500/40' : 'border-border',
    )}>
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-secondary/30 transition-colors text-left"
      >
        <span className="text-xl">{ROLE_ICONS[role.avatar] || '🤖'}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">{role.name}</h3>
            {role.customized && (
              <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-600 dark:text-blue-300 font-semibold">
                Customized
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate">{role.specialty}</p>
        </div>
        <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform shrink-0', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <div className="px-4 pb-4 pt-2 border-t border-border/50 space-y-3">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : detail ? (
            <>
              {/* Name */}
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => { setName(e.target.value); setDirty(true); }}
                  className="w-full bg-secondary/50 border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>

              {/* Specialty */}
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">Specialty (one-line summary)</label>
                <input
                  type="text"
                  value={specialty}
                  onChange={(e) => { setSpecialty(e.target.value); setDirty(true); }}
                  className="w-full bg-secondary/50 border border-border rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>

              {/* System Prompt */}
              <div>
                <label className="text-[11px] text-muted-foreground block mb-1">
                  System Prompt — full instructions for the agent
                </label>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => { setSystemPrompt(e.target.value); setDirty(true); }}
                  rows={20}
                  className="w-full bg-secondary/50 border border-border rounded-md px-3 py-2 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring resize-y leading-relaxed"
                />
                <p className="text-[10px] text-muted-foreground mt-1">
                  {systemPrompt.length.toLocaleString()} characters · Customizations save to <code>data/roles/{role.id}.md</code>
                </p>
              </div>

              {/* Tools focus + context needs (read-only) */}
              {detail.tools_focus && detail.tools_focus.length > 0 && (
                <div>
                  <label className="text-[11px] text-muted-foreground block mb-1">Tool Focus</label>
                  <div className="flex flex-wrap gap-1">
                    {detail.tools_focus.map((t) => (
                      <span key={t} className="text-[10px] px-2 py-0.5 rounded bg-secondary/60 border border-border">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-2 pt-2">
                <button
                  onClick={handleSave}
                  disabled={!dirty || saving}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                    dirty
                      ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                      : 'bg-secondary text-muted-foreground cursor-not-allowed',
                  )}
                >
                  {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                  Save Customization
                </button>
                {role.customized && (
                  <button
                    onClick={handleReset}
                    disabled={resetting}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border hover:bg-secondary transition-colors"
                  >
                    {resetting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RotateCcw className="h-3 w-3" />}
                    Reset to Default
                  </button>
                )}
                {feedback && (
                  <span className="text-xs text-muted-foreground ml-auto">{feedback}</span>
                )}
              </div>
            </>
          ) : (
            <p className="text-xs text-destructive">Failed to load role details</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function RolesEditor() {
  const [openId, setOpenId] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ['roles-list'],
    queryFn: fetchRoles,
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data?.roles) return null;

  return (
    <section>
      <h2 className="text-sm font-semibold mb-1 flex items-center gap-2">
        <Sparkles className="h-4 w-4" />
        Marketing Agency Roles ({data.roles.length})
      </h2>
      <p className="text-xs text-muted-foreground mb-4">
        Each role is a specialist persona the agent can adopt. Edit any role's name, specialty, or system prompt.
        Customizations save to <code>data/roles/&lt;role_id&gt;.md</code> and override the defaults on backend restart.
      </p>

      <div className="space-y-2">
        {data.roles.map((role) => (
          <RoleRow
            key={role.id}
            role={role}
            isOpen={openId === role.id}
            onToggle={() => setOpenId(openId === role.id ? null : role.id)}
          />
        ))}
      </div>
    </section>
  );
}
