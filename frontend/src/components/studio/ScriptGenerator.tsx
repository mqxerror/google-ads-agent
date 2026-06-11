import { useState, useCallback } from 'react';
import { Wand2, Loader2, Sparkles, ClipboardCopy, Film } from 'lucide-react';
import { cn } from '@/lib/utils';
import { sanitizeScript } from '@/lib/scriptSanitizer';

interface ScriptGeneratorProps {
  accountId?: string;
  campaignId?: string | null;
  campaignName?: string | null;
  onUseScript: (spoken: string) => void;  // fill VideoCreator with extracted spoken text
}

type Length = 6 | 15 | 30 | 60;

const LENGTH_HINTS: Record<Length, string> = {
  6: 'bumper — one idea, hard CTA',
  15: 'single hook + benefit + CTA',
  30: 'hook + problem + solution + proof + CTA',
  60: 'full story — hook, proof, offer, CTA',
};

// Split the generator's raw output into per-variant blocks so we can render them
// as separate selectable cards.
function splitVariants(raw: string): string[] {
  const text = raw.trim();
  if (!text) return [];
  // Split on "VARIANT X" headers or horizontal rules
  const parts = text.split(/\n\s*(?=VARIANT\s+[A-Z0-9])|\n\s*---+\s*\n/i);
  return parts.map(p => p.trim()).filter(Boolean);
}

export default function ScriptGenerator({ accountId, campaignId, campaignName, onUseScript }: ScriptGeneratorProps) {
  const [brief, setBrief] = useState('');
  const [length, setLength] = useState<Length>(15);
  const [variants, setVariants] = useState(2);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);

  const handleGenerate = useCallback(async () => {
    if (!brief.trim()) return;
    setGenerating(true);
    setError('');
    setResult('');
    setElapsed(0);

    const t0 = Date.now();
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);

    try {
      const res = await fetch('/api/video/script-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief: brief.trim(),
          length_seconds: length,
          variants,
          account_id: accountId,
          campaign_id: campaignId,
          model: 'sonnet',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body?.getReader();
      if (!reader) throw new Error('no response body');
      const decoder = new TextDecoder();
      let buf = '';
      let text = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'text') {
              text += evt.content;
              setResult(text);
            } else if (evt.type === 'error') {
              setError(evt.message);
            }
          } catch { /* ignore partial lines */ }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'generation failed');
    } finally {
      clearInterval(tick);
      setGenerating(false);
    }
  }, [brief, length, variants, accountId, campaignId]);

  const variantBlocks = splitVariants(result);

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-secondary/30">
        <Wand2 className="h-3.5 w-3.5 text-primary" />
        <span className="text-xs font-medium">Script Generator</span>
        {campaignName && (
          <span className="text-[10px] text-accent bg-accent-soft px-1.5 py-0.5 rounded">
            using {campaignName} context
          </span>
        )}
      </div>

      {/* Form */}
      <div className="p-3 space-y-2">
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          disabled={generating}
          placeholder="Brief: e.g. 'Greece Golden Visa — target UK investors worried about retirement security' — the script writer uses this + pinned facts from the selected campaign."
          className="w-full min-h-[60px] text-xs bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring resize-y disabled:opacity-60"
        />

        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <div className="flex items-center gap-0.5 border border-border rounded overflow-hidden">
            {([6, 15, 30, 60] as Length[]).map(l => (
              <button
                key={l}
                onClick={() => setLength(l)}
                disabled={generating}
                className={cn(
                  'px-2 py-1 text-[10px] transition-colors',
                  length === l ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:bg-secondary/50'
                )}
                title={LENGTH_HINTS[l]}
              >
                {l}s
              </button>
            ))}
          </div>

          <label className="flex items-center gap-1 text-muted-foreground">
            Variants:
            <select
              value={variants}
              onChange={(e) => setVariants(parseInt(e.target.value))}
              disabled={generating}
              className="bg-background border border-border rounded px-1 py-0.5 text-[10px]"
            >
              {[1, 2, 3, 4].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>

          <span className="text-[10px] text-muted-foreground italic">
            {LENGTH_HINTS[length]}
          </span>

          <button
            onClick={handleGenerate}
            disabled={!brief.trim() || generating}
            className="ml-auto flex items-center gap-1 px-3 py-1 rounded text-xs bg-primary text-primary-foreground hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
            {generating ? `Generating… ${elapsed}s` : 'Generate'}
          </button>
        </div>

        {error && (
          <div className="text-[10px] text-danger bg-danger-soft border border-danger/30 rounded px-2 py-1">
            ⚠ {error}
          </div>
        )}

        {/* Results */}
        {variantBlocks.length > 0 && (
          <div className="space-y-2 pt-2 border-t border-border">
            {variantBlocks.map((block, i) => {
              const { spoken } = sanitizeScript(block);
              return (
                <div key={i} className="border border-border rounded bg-secondary/20 p-2">
                  <pre className="text-[10px] whitespace-pre-wrap font-mono text-foreground/80 mb-1.5">{block}</pre>
                  {spoken && (
                    <div className="flex items-start gap-2 text-[10px] border-t border-border pt-1.5">
                      <div className="flex-1">
                        <div className="text-success font-medium mb-0.5">Spoken ({spoken.split(/\s+/).length} words):</div>
                        <div className="italic text-foreground/80">"{spoken}"</div>
                      </div>
                      <div className="flex flex-col gap-1 shrink-0">
                        <button
                          onClick={() => onUseScript(block)}
                          className="flex items-center gap-1 px-2 py-1 rounded text-[10px] bg-accent-soft text-accent hover:bg-accent-soft/80"
                        >
                          <Film className="h-2.5 w-2.5" /> Use for video
                        </button>
                        <button
                          onClick={() => navigator.clipboard.writeText(block)}
                          className="flex items-center gap-1 px-2 py-1 rounded text-[10px] bg-secondary/60 hover:bg-secondary text-muted-foreground"
                        >
                          <ClipboardCopy className="h-2.5 w-2.5" /> Copy
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {generating && !variantBlocks.length && result && (
          <pre className="text-[10px] whitespace-pre-wrap font-mono text-muted-foreground bg-secondary/20 border border-border rounded p-2">
            {result}
          </pre>
        )}
      </div>
    </div>
  );
}
