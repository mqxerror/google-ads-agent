import { useState, useEffect, useCallback } from 'react';
import { Pin, FileText, Plus, X, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useClientAccountId } from '@/hooks/useClientAccountId';

interface MemoryPanelProps {
  campaignId: string | null;
  campaignName?: string | null;
}

export default function MemoryPanel({ campaignId, campaignName }: MemoryPanelProps) {
  const accountId = useClientAccountId();
  const [pinnedFacts, setPinnedFacts] = useState('');
  const [decisions, setDecisions] = useState('');
  const [newFact, setNewFact] = useState('');
  const [showAddFact, setShowAddFact] = useState(false);
  const [expandedPinned, setExpandedPinned] = useState(true);
  const [expandedDecisions, setExpandedDecisions] = useState(false);

  const loadMemory = useCallback(async () => {
    if (!accountId || !campaignId) return;
    try {
      const [pinnedRes, memRes] = await Promise.all([
        fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/memory/pinned`),
        fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/memory`),
      ]);
      if (pinnedRes.ok) {
        const data = await pinnedRes.json();
        setPinnedFacts(data.pinned_facts || '');
      }
      if (memRes.ok) {
        const data = await memRes.json();
        // Extract decisions from context
        const ctx = data.context || '';
        const decisionsMatch = ctx.match(/# Decision Log[\s\S]*$/);
        setDecisions(decisionsMatch ? decisionsMatch[0] : '');
      }
    } catch {}
  }, [accountId, campaignId]);

  useEffect(() => {
    loadMemory();
  }, [loadMemory]);

  const handleAddFact = async () => {
    if (!newFact.trim() || !accountId || !campaignId) return;
    try {
      await fetch(`/api/accounts/${accountId}/campaigns/${campaignId}/memory/pinned`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fact: newFact.trim(), source: 'user' }),
      });
      setNewFact('');
      setShowAddFact(false);
      loadMemory();
    } catch {}
  };

  if (!campaignId) return null;

  // Parse pinned facts into list items
  const factLines = pinnedFacts
    .split('\n')
    .filter((l) => l.trim().startsWith('- **'))
    .map((l) => l.replace(/^- \*\*\[.*?\]\*\* /, '').replace(/ _\(source:.*?\)_$/, ''));

  // Parse decision rows
  const decisionRows = decisions
    .split('\n')
    .filter((l) => l.trim().startsWith('|') && !l.includes('---') && !l.includes('Date'))
    .map((l) => {
      const cells = l.split('|').map((c) => c.trim()).filter(Boolean);
      return { date: cells[0], action: cells[1], reason: cells[2], outcome: cells[3], role: cells[4] };
    })
    .filter((r) => r.action);

  return (
    <div className="border-t border-border">
      {/* Pinned Facts */}
      <button
        onClick={() => setExpandedPinned(!expandedPinned)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/30 transition-colors"
      >
        {expandedPinned ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Pin className="h-3 w-3" />
        Pinned Facts ({factLines.length})
        <button
          onClick={(e) => { e.stopPropagation(); setShowAddFact(!showAddFact); setExpandedPinned(true); }}
          className="ml-auto p-0.5 hover:bg-secondary rounded"
          title="Add pinned fact"
        >
          <Plus className="h-3 w-3" />
        </button>
      </button>

      {expandedPinned && (
        <div className="px-3 pb-2">
          {showAddFact && (
            <div className="flex gap-1 mb-1.5">
              <input
                value={newFact}
                onChange={(e) => setNewFact(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddFact()}
                placeholder="e.g. CPA target: $10"
                className="flex-1 text-[11px] bg-secondary/50 border border-border rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-ring"
                autoFocus
              />
              <button onClick={handleAddFact} className="text-[10px] px-2 py-1 bg-primary text-primary-foreground rounded hover:bg-primary/80">Pin</button>
              <button onClick={() => { setShowAddFact(false); setNewFact(''); }} className="p-1 text-muted-foreground hover:text-foreground">
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {factLines.length === 0 ? (
            <p className="text-[10px] text-muted-foreground italic">No pinned facts yet. Pin important context that should always be available.</p>
          ) : (
            <div className="space-y-0.5">
              {factLines.map((fact, i) => (
                <div key={i} className="flex items-start gap-1.5 text-[11px]">
                  <Pin className="h-2.5 w-2.5 mt-0.5 text-blue-400 shrink-0" />
                  <span>{fact}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Decision Log */}
      <button
        onClick={() => setExpandedDecisions(!expandedDecisions)}
        className="w-full flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium text-muted-foreground hover:text-foreground hover:bg-secondary/30 transition-colors border-t border-border"
      >
        {expandedDecisions ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <FileText className="h-3 w-3" />
        Decision Log ({decisionRows.length})
      </button>

      {expandedDecisions && (
        <div className="px-3 pb-2 max-h-40 overflow-y-auto">
          {decisionRows.length === 0 ? (
            <p className="text-[10px] text-muted-foreground italic">No decisions logged yet. The agent will log actions here automatically.</p>
          ) : (
            <div className="space-y-1">
              {decisionRows.slice(-10).reverse().map((d, i) => (
                <div key={i} className="text-[10px] border-l-2 border-blue-500/30 pl-2 py-0.5">
                  <div className="flex items-center gap-1">
                    <span className="text-muted-foreground">{d.date}</span>
                    {d.role && d.role !== 'agent' && (
                      <span className="bg-blue-500/10 text-blue-400 px-1 rounded text-[9px]">{d.role}</span>
                    )}
                  </div>
                  <p className="font-medium">{d.action}</p>
                  {d.reason && <p className="text-muted-foreground">{d.reason}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
