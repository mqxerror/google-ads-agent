import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { Check, Loader2 } from 'lucide-react';

interface GuidelinesEditorProps {
  content: string;
  onChange: (content: string) => void;
}

export default function GuidelinesEditor({ content, onChange }: GuidelinesEditorProps) {
  const [localContent, setLocalContent] = useState(content);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSave = useCallback(
    (text: string) => {
      setSaveStatus('saving');
      // Simulate save delay
      setTimeout(() => {
        onChange(text);
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2000);
      }, 500);
    },
    [onChange]
  );

  useEffect(() => {
    if (localContent === content) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      handleSave(localContent);
    }, 2000);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [localContent, content, handleSave]);

  return (
    <div className="space-y-2">
      {/* Save indicator */}
      <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
        {saveStatus === 'saving' && (
          <>
            <Loader2 className="h-3 w-3 animate-spin" />
            Saving...
          </>
        )}
        {saveStatus === 'saved' && (
          <>
            <Check className="h-3 w-3 text-status-enabled" />
            Saved
          </>
        )}
      </div>

      {/* Split view */}
      <div className="grid grid-cols-2 gap-4 min-h-[400px]">
        {/* Editor */}
        <div className="flex flex-col">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 px-1">
            Editor
          </div>
          <textarea
            value={localContent}
            onChange={(e) => setLocalContent(e.target.value)}
            className="flex-1 bg-secondary/50 border border-border rounded-md p-3 text-sm font-mono text-foreground resize-none focus:outline-none focus:ring-1 focus:ring-ring"
            spellCheck={false}
          />
        </div>

        {/* Preview */}
        <div className="flex flex-col">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1 px-1">
            Preview
          </div>
          <div className="flex-1 bg-card border border-border rounded-md p-4 overflow-y-auto">
            <PreviewRenderer content={localContent} />
          </div>
        </div>
      </div>
    </div>
  );
}

function PreviewRenderer({ content }: { content: string }) {
  const lines = content.split('\n');
  const elements: ReactNode[] = [];
  let key = 0;

  for (const line of lines) {
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={key++} className="text-lg font-bold mb-2 mt-3 first:mt-0">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={key++} className="text-sm font-semibold mb-1.5 mt-3">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith('- ')) {
      elements.push(
        <li key={key++} className="text-xs text-foreground/80 ml-4 mb-0.5 list-disc">
          {line.slice(2)}
        </li>
      );
    } else if (line.startsWith('  - ')) {
      elements.push(
        <li key={key++} className="text-xs text-foreground/80 ml-8 mb-0.5 list-disc">
          {line.slice(4)}
        </li>
      );
    } else if (line.trim() === '') {
      elements.push(<div key={key++} className="h-1.5" />);
    } else {
      elements.push(
        <p key={key++} className="text-xs text-foreground/80 mb-1">
          {line}
        </p>
      );
    }
  }

  return <>{elements}</>;
}
