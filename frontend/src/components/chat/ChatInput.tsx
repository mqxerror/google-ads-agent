import { useRef, useState, useCallback, type KeyboardEvent } from 'react';
import { SendHorizonal, Zap, Brain, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type ModelId = 'sonnet' | 'opus' | 'haiku';

const MODELS: { id: ModelId; label: string; desc: string; icon: typeof Zap }[] = [
  { id: 'sonnet', label: 'Sonnet', desc: 'Fast & smart', icon: Zap },
  { id: 'opus', label: 'Opus', desc: 'Deep analysis', icon: Brain },
  { id: 'haiku', label: 'Haiku', desc: 'Quick & cheap', icon: Sparkles },
];

interface ChatInputProps {
  onSend: (text: string, model: ModelId) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [model, setModel] = useState<ModelId>('sonnet');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, model);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, disabled, onSend, model]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 80)}px`;
  };

  const currentModel = MODELS.find((m) => m.id === model)!;

  return (
    <div className="border-t border-border px-3 py-2 space-y-2">
      {/* Model selector */}
      <div className="flex items-center gap-1">
        {MODELS.map((m) => {
          const Icon = m.icon;
          return (
            <button
              key={m.id}
              onClick={() => setModel(m.id)}
              className={cn(
                'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors',
                model === m.id
                  ? 'bg-primary/20 text-primary font-medium'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
              )}
              title={m.desc}
            >
              <Icon className="h-3 w-3" />
              {m.label}
            </button>
          );
        })}
        <span className="ml-auto text-[10px] text-muted-foreground">{currentModel.desc}</span>
      </div>

      {/* Input + send */}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); handleInput(); }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask about this campaign..."
          rows={1}
          className="flex-1 resize-none bg-secondary/50 border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-50"
        />
        <Button
          size="icon"
          className="h-9 w-9 shrink-0"
          disabled={disabled || !value.trim()}
          onClick={handleSend}
        >
          <SendHorizonal className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
