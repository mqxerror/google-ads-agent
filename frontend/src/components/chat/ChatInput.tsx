import { useRef, useState, useCallback, type KeyboardEvent } from 'react';
import { SendHorizonal, Zap, Brain, Sparkles, LayoutTemplate, X, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import templates, { TEMPLATE_CATEGORIES, type ChatTemplate } from '@/lib/chatTemplates';
import type { Campaign } from '@/types';

export type ModelId = 'sonnet' | 'opus' | 'haiku';

const MODELS: { id: ModelId; label: string; desc: string; icon: typeof Zap }[] = [
  { id: 'sonnet', label: 'Sonnet', desc: 'Fast & smart', icon: Zap },
  { id: 'opus', label: 'Opus', desc: 'Deep analysis', icon: Brain },
  { id: 'haiku', label: 'Haiku', desc: 'Quick & cheap', icon: Sparkles },
];

interface ChatInputProps {
  onSend: (text: string, model: ModelId) => void;
  disabled: boolean;
  campaignName?: string | null;
  onStop?: () => void;
}

export default function ChatInput({ onSend, disabled, campaignName, onStop }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [model, setModel] = useState<ModelId>('sonnet');
  const [showTemplates, setShowTemplates] = useState(false);
  const [templateCategory, setTemplateCategory] = useState<string>('analyze');
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
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  const handleSelectTemplate = (template: ChatTemplate) => {
    let prompt = template.prompt;
    // Replace {campaign} placeholder
    if (template.needsCampaign && campaignName) {
      prompt = prompt.replace(/\{campaign\}/g, campaignName);
    } else if (template.needsCampaign && !campaignName) {
      prompt = prompt.replace(/\{campaign\}/g, '[SELECT A CAMPAIGN FIRST]');
    }
    setValue(prompt);
    if (template.suggestedModel) {
      setModel(template.suggestedModel);
    }
    setShowTemplates(false);
    // Focus textarea so user can edit
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
      }
    }, 50);
  };

  const filteredTemplates = templates.filter((t) => t.category === templateCategory);

  const currentModel = MODELS.find((m) => m.id === model)!;

  return (
    <div className="border-t border-border px-3 py-2 space-y-2">
      {/* Template picker overlay */}
      {showTemplates && (
        <div className="bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-hidden">
          {/* Category tabs */}
          <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-border bg-secondary/30 overflow-x-auto">
            {TEMPLATE_CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setTemplateCategory(cat.id)}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 text-[10px] rounded-md whitespace-nowrap transition-colors',
                  templateCategory === cat.id
                    ? 'bg-primary text-primary-foreground font-medium'
                    : 'text-muted-foreground hover:bg-secondary'
                )}
              >
                <span>{cat.icon}</span>
                {cat.label}
              </button>
            ))}
            <button
              onClick={() => setShowTemplates(false)}
              className="ml-auto p-1 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          </div>

          {/* Template list */}
          <div className="overflow-y-auto max-h-56 p-1.5">
            {filteredTemplates.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelectTemplate(t)}
                className="w-full text-left px-3 py-2 rounded-md hover:bg-secondary/60 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{t.icon}</span>
                  <span className="text-xs font-medium">{t.label}</span>
                  {t.needsCampaign && !campaignName && (
                    <span className="text-[9px] text-yellow-500 bg-yellow-500/10 px-1 rounded">needs campaign</span>
                  )}
                  {t.suggestedModel && (
                    <span className="text-[9px] text-muted-foreground ml-auto">{t.suggestedModel}</span>
                  )}
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5 ml-6">{t.description}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Model selector + template button */}
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
        <span className="ml-auto flex items-center gap-2">
          <button
            onClick={() => setShowTemplates(!showTemplates)}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors',
              showTemplates
                ? 'bg-primary/20 text-primary font-medium'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
            )}
            title="Smart templates"
          >
            <LayoutTemplate className="h-3 w-3" />
            Templates
          </button>
          <span className="text-[10px] text-muted-foreground">{currentModel.desc}</span>
        </span>
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
        {disabled && onStop ? (
          <Button
            size="icon"
            variant="destructive"
            className="h-9 w-9 shrink-0"
            onClick={onStop}
            title="Stop agent"
          >
            <Square className="h-4 w-4 fill-current" />
          </Button>
        ) : (
          <Button
            size="icon"
            className="h-9 w-9 shrink-0"
            disabled={disabled || !value.trim()}
            onClick={handleSend}
          >
            <SendHorizonal className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
