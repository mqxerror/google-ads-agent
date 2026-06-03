import { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { BookOpen, FileText, Wand2, Loader2, History } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import SuggestEditsDialog from './SuggestEditsDialog';

interface GuidelineFile {
  filename: string;
  campaign_id?: string | null;
  campaign_name?: string | null;
  size_bytes?: number;
}

interface GuidelineContent {
  filename: string;
  content: string;
  sections?: { heading: string; level: number }[];
}

async function fetchFiles(): Promise<GuidelineFile[]> {
  const r = await fetch('/api/guidelines');
  if (!r.ok) return [];
  return r.json();
}
async function fetchContent(filename: string): Promise<GuidelineContent | null> {
  const r = await fetch(`/api/guidelines/${encodeURIComponent(filename)}`);
  if (!r.ok) return null;
  return r.json();
}
async function fetchProposals(filename: string, accountId: string) {
  const r = await fetch(`/api/guidelines/${encodeURIComponent(filename)}/proposals?account_id=${encodeURIComponent(accountId)}`);
  if (!r.ok) return [];
  return r.json();
}

export default function GuidelinesPage() {
  const accountId = useClientAccountId();
  const { setShowGuidelines } = useAppStore();
  const [selected, setSelected] = useState<string | null>(null);
  const [showSuggest, setShowSuggest] = useState(false);

  const { data: files = [], isLoading: filesLoading } = useQuery({
    queryKey: ['guideline-files'],
    queryFn: fetchFiles,
    staleTime: 30_000,
  });

  // Auto-select first file on load
  useEffect(() => {
    if (!selected && files.length > 0) setSelected(files[0].filename);
  }, [files, selected]);

  const { data: content, refetch: refetchContent, isFetching: contentLoading } = useQuery({
    queryKey: ['guideline-content', selected],
    queryFn: () => selected ? fetchContent(selected) : Promise.resolve(null),
    enabled: !!selected,
    staleTime: 30_000,
  });

  const { data: proposals = [], refetch: refetchProposals } = useQuery({
    queryKey: ['guideline-proposals', selected, accountId],
    queryFn: () => (selected && accountId) ? fetchProposals(selected, accountId) : Promise.resolve([]),
    enabled: !!selected && !!accountId,
    staleTime: 15_000,
  });

  const pendingProposals = useMemo(
    () => proposals.filter((p: any) => p.status === 'pending'),
    [proposals],
  );

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-amber-400" />
            Guidelines
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Account-wide rules the agent reads on every conversation. Click "Suggest edits" to have the agent propose updates based on recent sessions.
          </p>
        </div>
        <button onClick={() => setShowGuidelines(false)} className="text-xs text-muted-foreground hover:text-foreground px-2 py-1">
          Back to campaigns
        </button>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* File list */}
        <div className="col-span-3">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-2">Files</div>
          {filesLoading ? (
            <div className="text-xs text-muted-foreground flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> loading...</div>
          ) : files.length === 0 ? (
            <div className="text-xs text-muted-foreground italic">No guideline files yet.</div>
          ) : (
            <div className="space-y-1">
              {files.map((f) => (
                <button
                  key={f.filename}
                  onClick={() => setSelected(f.filename)}
                  className={cn(
                    'w-full text-left text-xs px-2 py-1.5 rounded flex items-center gap-1.5 transition-colors',
                    selected === f.filename
                      ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50 border border-transparent',
                  )}
                >
                  <FileText className="h-3 w-3 shrink-0" />
                  <span className="truncate">{f.filename}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Content + actions */}
        <div className="col-span-9">
          {selected && (
            <div className="border border-border rounded-lg bg-card overflow-hidden">
              {/* File header */}
              <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-secondary/30">
                <div className="flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-sm font-medium">{selected}</span>
                  {pendingProposals.length > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-pink-500/15 text-pink-300 border border-pink-500/30">
                      {pendingProposals.length} pending suggestion{pendingProposals.length === 1 ? '' : 's'}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {pendingProposals.length > 0 && (
                    <button
                      onClick={() => setShowSuggest(true)}
                      className="text-[10px] px-2 py-1 rounded bg-secondary hover:bg-secondary/80 flex items-center gap-1 border border-border"
                      title="Review pending suggestion"
                    >
                      <History className="h-3 w-3" /> Review
                    </button>
                  )}
                  <button
                    onClick={() => setShowSuggest(true)}
                    disabled={!accountId || !content}
                    className="text-[10px] px-2 py-1 rounded bg-pink-500/15 text-pink-300 hover:bg-pink-500/25 flex items-center gap-1 border border-pink-500/30 disabled:opacity-50"
                  >
                    <Wand2 className="h-3 w-3" /> Suggest edits
                  </button>
                </div>
              </div>

              {/* Body */}
              <div className="p-4 max-h-[calc(100vh-240px)] overflow-y-auto">
                {contentLoading && !content && (
                  <div className="text-xs text-muted-foreground flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> loading...</div>
                )}
                {content && (
                  <div className="prose prose-sm prose-invert max-w-none
                    [&_h1]:text-base [&_h1]:font-bold [&_h1]:mt-4 [&_h1]:mb-2
                    [&_h2]:text-sm [&_h2]:font-bold [&_h2]:mt-3 [&_h2]:mb-2
                    [&_h3]:text-xs [&_h3]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1
                    [&_p]:my-1.5 [&_p]:text-sm
                    [&_ul]:my-1.5 [&_ul]:pl-4 [&_ul]:text-sm
                    [&_li]:my-0.5
                    [&_strong]:text-foreground [&_strong]:font-semibold
                    [&_code]:text-xs [&_code]:bg-background/50 [&_code]:px-1 [&_code]:rounded
                    [&_table]:text-xs [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1
                  ">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.content}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Suggest edits dialog */}
      {selected && content && accountId && (
        <SuggestEditsDialog
          open={showSuggest}
          onClose={() => setShowSuggest(false)}
          filename={selected}
          accountId={accountId}
          currentContent={content.content}
          onApplied={() => { refetchContent(); refetchProposals(); }}
        />
      )}
    </div>
  );
}
