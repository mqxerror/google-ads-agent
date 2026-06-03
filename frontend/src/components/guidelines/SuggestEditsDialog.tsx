import { useEffect, useMemo, useState } from 'react';
import { X, Wand2, Loader2, Check, Trash2, AlertTriangle, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import { lineDiff, diffStats, type DiffOp } from '@/lib/lineDiff';

interface Proposal {
  id: string;
  filename: string;
  based_on_content: string;
  proposed_content: string;
  rationale?: string;
  evidence_summary?: string;
  status: string;
  created_at: string;
}

interface SuggestEditsDialogProps {
  open: boolean;
  onClose: () => void;
  filename: string;
  accountId: string;
  currentContent: string;
  onApplied?: () => void;     // parent should refetch after a successful apply
}

export default function SuggestEditsDialog({
  open, onClose, filename, accountId, currentContent, onApplied,
}: SuggestEditsDialogProps) {
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [extraFocus, setExtraFocus] = useState('');
  const [error, setError] = useState<string>('');
  const [info, setInfo] = useState<string>('');

  // Reset state each open
  useEffect(() => {
    if (!open) return;
    setProposal(null);
    setError('');
    setInfo('');
    setExtraFocus('');
  }, [open]);

  const generate = async () => {
    setGenerating(true);
    setError('');
    setInfo('');
    setProposal(null);
    try {
      const r = await fetch(`/api/guidelines/${encodeURIComponent(filename)}/suggest-edits`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId, extra_focus: extraFocus || null }),
      });
      const data = await r.json();
      if (!r.ok) {
        setError(data?.detail || `HTTP ${r.status}`);
        return;
      }
      if (data.status === 'proposed' && data.proposal) {
        setProposal(data.proposal);
      } else if (data.status === 'skipped') {
        setInfo(data.reason || 'No changes proposed.');
      } else if (data.status === 'error') {
        setError(data.reason || 'Optimizer failed.');
      } else {
        setError(JSON.stringify(data));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'request failed');
    } finally {
      setGenerating(false);
    }
  };

  const applyNow = async () => {
    if (!proposal) return;
    setApplying(true);
    setError('');
    try {
      const url = `/api/guidelines/${encodeURIComponent(filename)}/proposals/${proposal.id}/apply?account_id=${encodeURIComponent(accountId)}`;
      const r = await fetch(url, { method: 'POST' });
      const data = await r.json();
      if (!r.ok) {
        setError(data?.detail || `HTTP ${r.status}`);
        return;
      }
      if (data.status === 'applied') {
        setInfo('Applied. The guideline file has been updated.');
        onApplied?.();
        // Auto-close after a beat so the user sees confirmation
        setTimeout(onClose, 900);
      } else if (data.status === 'stale') {
        setError(data.reason || 'Proposal is stale — please regenerate.');
      } else {
        setError(data.reason || 'Apply failed.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'request failed');
    } finally {
      setApplying(false);
    }
  };

  const discard = async () => {
    if (!proposal) return;
    try {
      await fetch(
        `/api/guidelines/${encodeURIComponent(filename)}/proposals/${proposal.id}/discard?account_id=${encodeURIComponent(accountId)}`,
        { method: 'POST' },
      );
    } catch {}
    onClose();
  };

  const ops = useMemo<DiffOp[]>(() => {
    if (!proposal) return [];
    return lineDiff(proposal.based_on_content, proposal.proposed_content);
  }, [proposal]);
  const stats = useMemo(() => diffStats(ops), [ops]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-lg w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Wand2 className="h-4 w-4 text-pink-400" />
            <span className="text-sm font-semibold">Suggest edits</span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <FileText className="h-3 w-3" /> {filename}
            </span>
            {proposal && (
              <span className="text-[10px] px-2 py-0.5 rounded bg-secondary border border-border">
                <span className="text-emerald-400">+{stats.added}</span>
                {' / '}
                <span className="text-red-400">−{stats.removed}</span>
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!proposal && !generating && !info && !error && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                The agent will read your recent sessions, user corrections, and decisions, then propose
                edits to <code className="text-xs">{filename}</code>. You'll see the diff and can apply or discard it.
              </p>
              <div>
                <label className="text-xs text-muted-foreground block mb-1">
                  Optional focus (one line — e.g. "add UK ad copy rules"):
                </label>
                <input
                  value={extraFocus}
                  onChange={(e) => setExtraFocus(e.target.value)}
                  placeholder="(optional)"
                  className="w-full text-xs bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
                />
              </div>
              <button
                onClick={generate}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-pink-500/20 text-pink-300 hover:bg-pink-500/30 border border-pink-500/40 text-sm"
              >
                <Wand2 className="h-3.5 w-3.5" /> Generate suggestion
              </button>
            </div>
          )}

          {generating && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-12 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" />
              Reading recent sessions and drafting changes (this can take 30-90 seconds)...
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded p-2.5">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {info && !proposal && (
            <div className="text-xs text-muted-foreground bg-secondary/40 border border-border rounded p-3">
              {info}
            </div>
          )}

          {proposal && (
            <>
              {/* Rationale + evidence */}
              {proposal.rationale && (
                <div className="border border-border rounded p-3 bg-secondary/30">
                  <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1">Rationale</div>
                  <p className="text-xs text-foreground/90 whitespace-pre-wrap leading-relaxed">{proposal.rationale}</p>
                </div>
              )}
              {proposal.evidence_summary && (
                <details className="border border-border rounded bg-secondary/30">
                  <summary className="text-[10px] uppercase tracking-wide text-muted-foreground px-3 py-2 cursor-pointer">
                    Evidence ({proposal.evidence_summary.split('\n').filter(l => l.trim()).length} items)
                  </summary>
                  <pre className="px-3 pb-3 text-[10px] whitespace-pre-wrap text-foreground/80">{proposal.evidence_summary}</pre>
                </details>
              )}

              {/* Diff viewer */}
              <div className="border border-border rounded overflow-hidden">
                <div className="flex items-center justify-between bg-secondary/40 px-3 py-1.5 border-b border-border">
                  <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Proposed changes</span>
                  <span className="text-[10px] text-muted-foreground">
                    {stats.unchanged} unchanged · {stats.added + stats.removed} changed
                  </span>
                </div>
                <div className="font-mono text-[11px] leading-snug overflow-x-auto max-h-[420px] overflow-y-auto bg-background/60">
                  {ops.map((op, i) => {
                    const bg = op.type === 'added'   ? 'bg-emerald-500/10 border-l-2 border-emerald-500'
                            : op.type === 'removed' ? 'bg-red-500/10 border-l-2 border-red-500'
                            :                         '';
                    const sign = op.type === 'added' ? '+' : op.type === 'removed' ? '−' : ' ';
                    const num = op.type === 'removed'
                      ? `${op.oldNum}`
                      : op.type === 'added'
                        ? `   ${op.newNum}`
                        : `${(op as any).oldNum}→${(op as any).newNum}`;
                    return (
                      <div key={i} className={cn('flex gap-2 px-2 py-0.5', bg)}>
                        <span className="text-muted-foreground/60 w-12 text-right shrink-0 select-none">{num}</span>
                        <span className={cn('w-3 select-none shrink-0',
                          op.type === 'added' ? 'text-emerald-400' :
                          op.type === 'removed' ? 'text-red-400' :
                          'text-muted-foreground/40')}>{sign}</span>
                        <span className="whitespace-pre-wrap break-words">{op.line || ' '}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        {proposal && (
          <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-border bg-card">
            <button
              onClick={discard}
              disabled={applying}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/60 disabled:opacity-50"
            >
              <Trash2 className="h-3 w-3" /> Discard
            </button>
            <button
              onClick={generate}
              disabled={applying || generating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/60 disabled:opacity-50"
            >
              {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
              Re-generate
            </button>
            <button
              onClick={applyNow}
              disabled={applying}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 border border-emerald-500/40 disabled:opacity-50"
            >
              {applying ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
              Apply changes
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
