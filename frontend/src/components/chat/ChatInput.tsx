import { useRef, useState, useCallback, useEffect, type KeyboardEvent, type ClipboardEvent } from 'react';
import { SendHorizonal, Zap, Brain, Sparkles, LayoutTemplate, X, Square, Users, ChevronDown, Paperclip, FileText, Image as ImageIcon, Loader2, Film } from 'lucide-react';
import VideoCreator from './VideoCreator';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import templates, { TEMPLATE_CATEGORIES, type ChatTemplate } from '@/lib/chatTemplates';
import type { Campaign } from '@/types';

export interface Attachment {
  filename: string;
  path: string;
  is_image: boolean;
  ext: string;
  url: string;
  size: number;
}

export type ModelId = 'sonnet' | 'opus' | 'haiku';

const MODELS: { id: ModelId; label: string; desc: string; icon: typeof Zap }[] = [
  { id: 'sonnet', label: 'Sonnet', desc: 'Fast & smart', icon: Zap },
  { id: 'opus', label: 'Opus', desc: 'Deep analysis', icon: Brain },
  { id: 'haiku', label: 'Haiku', desc: 'Quick & cheap', icon: Sparkles },
];

interface AgencyRole {
  id: string;
  name: string;
  avatar: string;
  specialty: string;
}

const ROLE_ICONS: Record<string, string> = {
  briefcase: '💼', target: '🎯', search: '🔍', palette: '🎨',
  chart: '📊', eye: '👁️', code: '💻', rocket: '🚀',
};

interface ConversationRef {
  id: string;
  title: string;
  campaignName: string | null;
  messageCount: number;
}

interface ChatInputProps {
  onSend: (text: string, model: ModelId, roleId?: string, attachments?: Attachment[]) => void;
  disabled: boolean;
  campaignName?: string | null;
  onStop?: () => void;
  conversations?: ConversationRef[];
  conversationId?: string | null;
  onEnsureConversation?: () => Promise<string>;
  onVideoReady?: (url: string, script: string, thumbnail?: string) => void;
}

export default function ChatInput({ onSend, disabled, campaignName, onStop, conversations = [], conversationId, onEnsureConversation, onVideoReady }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [model, setModel] = useState<ModelId>('opus');
  const [showTemplates, setShowTemplates] = useState(false);
  const [showRoles, setShowRoles] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const [showVideo, setShowVideo] = useState(false);
  const [teamRoles, setTeamRoles] = useState<Set<string>>(new Set());
  const [templateCategory, setTemplateCategory] = useState<string>('analyze');
  const [roles, setRoles] = useState<AgencyRole[]>([]);
  const [activeRole, setActiveRole] = useState<string | null>(null);
  const [showMentions, setShowMentions] = useState(false);
  const [showSlashRoles, setShowSlashRoles] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [slashFilter, setSlashFilter] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload a file to the backend
  const uploadFile = useCallback(async (file: File): Promise<Attachment | null> => {
    let convId = conversationId;
    if (!convId && onEnsureConversation) {
      try {
        convId = await onEnsureConversation();
      } catch {
        return null;
      }
    }
    if (!convId) return null;

    const formData = new FormData();
    formData.append('conversation_id', convId);
    formData.append('file', file);

    try {
      const res = await fetch('/api/uploads', { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.text();
        console.error('Upload failed:', err);
        return null;
      }
      return await res.json();
    } catch (e) {
      console.error('Upload error:', e);
      return null;
    }
  }, [conversationId, onEnsureConversation]);

  // Handle file selection from input
  const handleFileSelect = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const uploaded: Attachment[] = [];
      for (const file of Array.from(files)) {
        const result = await uploadFile(file);
        if (result) uploaded.push(result);
      }
      setAttachments((prev) => [...prev, ...uploaded]);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [uploadFile]);

  // Handle clipboard paste — capture images
  const handlePaste = useCallback(async (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    const imageFiles: File[] = [];
    for (const item of Array.from(items)) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) {
          // Generate a meaningful filename
          const ext = file.type.split('/')[1] || 'png';
          const renamed = new File([file], `pasted-${Date.now()}.${ext}`, { type: file.type });
          imageFiles.push(renamed);
        }
      }
    }

    if (imageFiles.length > 0) {
      e.preventDefault();
      setUploading(true);
      try {
        const uploaded: Attachment[] = [];
        for (const file of imageFiles) {
          const result = await uploadFile(file);
          if (result) uploaded.push(result);
        }
        setAttachments((prev) => [...prev, ...uploaded]);
      } finally {
        setUploading(false);
      }
    }
  }, [uploadFile]);

  const removeAttachment = (filename: string) => {
    setAttachments((prev) => prev.filter((a) => a.filename !== filename));
  };

  // Fetch available roles
  useEffect(() => {
    fetch('/api/roles')
      .then((r) => r.json())
      .then((data) => setRoles(data.roles || []))
      .catch(() => {});
  }, []);

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed && attachments.length === 0) return;

    // Check for /role_name at start of message → override role for this message
    const slashMatch = trimmed.match(/^\/(\w+)\s+(.*)/s);
    let messageText = trimmed || '(see attached files)';
    let messageRole = activeRole || undefined;
    if (slashMatch) {
      const matchedRole = roles.find(r => r.id === slashMatch[1] || r.name.toLowerCase().replace(/\s+/g, '_') === slashMatch[1]);
      if (matchedRole) {
        messageRole = matchedRole.id;
        messageText = slashMatch[2];
      }
    }

    // Team Session mode: wrap the message with multi-persona instructions
    if (showTeam && teamRoles.size > 0) {
      const selectedRoles = roles.filter(r => teamRoles.has(r.id));
      const roleNames = selectedRoles.map(r => `${r.name} (${r.id})`).join(', ');
      const teamPrompt = `TEAM SESSION — Respond as each of these specialists IN SEQUENCE. For each role, use this EXACT format:

---ROLE: [role_id]---
[Your analysis as that specialist]
---END ROLE---

Selected team: ${roleNames}

Each specialist should:
1. State their perspective based on their expertise
2. Reference and build on what previous specialists said
3. Be specific with numbers, metrics, and actionable recommendations
4. Disagree if they have a different view — don't just agree

After ALL specialists respond, as the Agency Director, provide a CONSENSUS summary with the recommended action plan.

The question/topic: ${messageText}`;
      onSend(teamPrompt, model, 'director', attachments);
    } else {
      onSend(messageText, model, messageRole, attachments);
    }

    setValue('');
    setAttachments([]);
    setShowTeam(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, onSend, model, activeRole, roles, attachments, showTeam, teamRoles]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // Don't send if mention/slash dropdown is open
      if (showMentions || showSlashRoles) {
        e.preventDefault();
        return;
      }
      e.preventDefault();
      handleSend();
    }
    if (e.key === 'Escape') {
      setShowMentions(false);
      setShowSlashRoles(false);
    }
  };

  // Detect @ and / triggers while typing
  const handleChange = (newValue: string) => {
    setValue(newValue);

    // @ mention detection — look for @ followed by text
    const atMatch = newValue.match(/@(\w*)$/);
    if (atMatch) {
      setShowMentions(true);
      setMentionFilter(atMatch[1].toLowerCase());
      setShowSlashRoles(false);
    } else {
      setShowMentions(false);
    }

    // / role detection — only at start of input
    const slashMatch = newValue.match(/^\/(\w*)$/);
    if (slashMatch) {
      setShowSlashRoles(true);
      setSlashFilter(slashMatch[1].toLowerCase());
      setShowMentions(false);
    } else if (!newValue.startsWith('/')) {
      setShowSlashRoles(false);
    }
  };

  const insertMention = (conv: ConversationRef) => {
    // Replace the @filter with a reference tag
    const label = conv.title || conv.campaignName || 'chat';
    const newValue = value.replace(/@\w*$/, `@[${label}](conv:${conv.id}) `);
    setValue(newValue);
    setShowMentions(false);
    textareaRef.current?.focus();
  };

  const insertSlashRole = (role: AgencyRole) => {
    setValue(`/${role.id} `);
    setShowSlashRoles(false);
    textareaRef.current?.focus();
  };

  const filteredConversations = conversations.filter(c =>
    !mentionFilter || (c.title || c.campaignName || '').toLowerCase().includes(mentionFilter)
  ).slice(0, 8);

  const filteredSlashRoles = roles.filter(r =>
    !slashFilter || r.id.includes(slashFilter) || r.name.toLowerCase().includes(slashFilter)
  );

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    handleChange(el.value);
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

      {/* @ Mention dropdown — reference previous conversations */}
      {showMentions && filteredConversations.length > 0 && (
        <div className="bg-card border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
          <div className="px-3 py-1.5 border-b border-border bg-secondary/30">
            <span className="text-[10px] font-medium text-muted-foreground">Reference a conversation — type @ to search</span>
          </div>
          <div className="p-1">
            {filteredConversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => insertMention(conv)}
                className="w-full text-left px-3 py-1.5 rounded-md hover:bg-secondary/60 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium truncate">{conv.title || 'Untitled'}</span>
                  <span className="text-[9px] text-muted-foreground ml-2">{conv.messageCount} msgs</span>
                </div>
                <p className="text-[10px] text-muted-foreground truncate">{conv.campaignName || 'General'}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* / Role command dropdown — invoke a role inline */}
      {showSlashRoles && filteredSlashRoles.length > 0 && (
        <div className="bg-card border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto">
          <div className="px-3 py-1.5 border-b border-border bg-secondary/30">
            <span className="text-[10px] font-medium text-muted-foreground">Invoke a specialist — type / then role name</span>
          </div>
          <div className="p-1">
            {filteredSlashRoles.map((role) => (
              <button
                key={role.id}
                onClick={() => insertSlashRole(role)}
                className="w-full text-left px-3 py-1.5 rounded-md hover:bg-secondary/60 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{ROLE_ICONS[role.avatar] || '👤'}</span>
                  <span className="text-xs font-medium">/{role.id}</span>
                  <span className="text-[10px] text-muted-foreground ml-auto">{role.name}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Role picker overlay */}
      {showRoles && roles.length > 0 && (
        <div className="bg-card border border-border rounded-lg shadow-lg max-h-80 overflow-hidden">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-secondary/30">
            <span className="text-[10px] font-medium text-muted-foreground">Agency Team — Select Specialist</span>
            <button onClick={() => setShowRoles(false)} className="p-0.5 text-muted-foreground hover:text-foreground">
              <X className="h-3 w-3" />
            </button>
          </div>
          <div className="overflow-y-auto max-h-56 p-1.5">
            {/* Auto-detect option */}
            <button
              onClick={() => { setActiveRole(null); setShowRoles(false); }}
              className={cn(
                'w-full text-left px-3 py-2 rounded-md hover:bg-secondary/60 transition-colors',
                !activeRole && 'bg-secondary/40'
              )}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm">🤖</span>
                <span className="text-xs font-medium">Auto-Detect</span>
                <span className="text-[9px] text-muted-foreground ml-auto">Director routes automatically</span>
              </div>
              <p className="text-[10px] text-muted-foreground mt-0.5 ml-6">The Director picks the best specialist based on your message</p>
            </button>
            {roles.map((role) => (
              <button
                key={role.id}
                onClick={() => { setActiveRole(role.id); setShowRoles(false); }}
                className={cn(
                  'w-full text-left px-3 py-2 rounded-md hover:bg-secondary/60 transition-colors',
                  activeRole === role.id && 'bg-blue-500/10 border border-blue-500/30'
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm">{ROLE_ICONS[role.avatar] || '👤'}</span>
                  <span className="text-xs font-medium">{role.name}</span>
                </div>
                <p className="text-[10px] text-muted-foreground mt-0.5 ml-6">{role.specialty}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Video creator panel */}
      <VideoCreator
        open={showVideo}
        onClose={() => setShowVideo(false)}
        onVideoReady={(url, script, thumb) => {
          onVideoReady?.(url, script, thumb);
          setShowVideo(false);
        }}
      />

      {/* Team Session role picker */}
      {showTeam && roles.length > 0 && (
        <div className="bg-card border border-purple-500/30 rounded-lg shadow-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-purple-500/10">
            <span className="text-[10px] font-medium text-purple-400">Team Session — Pick specialists to discuss</span>
            <button onClick={() => setShowTeam(false)} className="p-0.5 text-muted-foreground hover:text-foreground">
              <X className="h-3 w-3" />
            </button>
          </div>
          <div className="p-2 grid grid-cols-3 gap-1">
            {roles.filter(r => r.id !== 'director').map((role) => (
              <button
                key={role.id}
                onClick={() => {
                  setTeamRoles(prev => {
                    const next = new Set(prev);
                    if (next.has(role.id)) next.delete(role.id);
                    else next.add(role.id);
                    return next;
                  });
                }}
                className={cn(
                  'flex items-center gap-1.5 px-2 py-1.5 rounded-md text-left transition-colors text-[10px]',
                  teamRoles.has(role.id)
                    ? 'bg-purple-500/20 border border-purple-500/40 text-purple-300'
                    : 'hover:bg-secondary/60 text-muted-foreground'
                )}
              >
                <span>{ROLE_ICONS[role.avatar] || '👤'}</span>
                <span className="truncate">{role.name}</span>
              </button>
            ))}
          </div>
          {teamRoles.size > 0 && (
            <div className="px-3 py-1.5 border-t border-border bg-secondary/20 text-[10px] text-muted-foreground">
              {teamRoles.size} specialist{teamRoles.size !== 1 ? 's' : ''} selected + Director (always included). Type your question and send.
            </div>
          )}
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
          {/* Role selector */}
          <div className="relative">
            <button
              onClick={() => { setShowRoles(!showRoles); setShowTemplates(false); }}
              className={cn(
                'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors',
                activeRole
                  ? 'bg-blue-500/20 text-blue-400 font-medium'
                  : showRoles
                    ? 'bg-primary/20 text-primary font-medium'
                    : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
              )}
              title="Select specialist role"
            >
              <Users className="h-3 w-3" />
              {activeRole ? (roles.find(r => r.id === activeRole)?.name || 'Role') : 'Auto'}
              <ChevronDown className="h-2.5 w-2.5" />
            </button>
          </div>
          <button
            onClick={() => { setShowTemplates(!showTemplates); setShowRoles(false); setShowTeam(false); }}
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
          <button
            onClick={() => { setShowTeam(!showTeam); setShowTemplates(false); setShowRoles(false); setShowVideo(false); }}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors',
              showTeam
                ? 'bg-purple-500/20 text-purple-400 font-medium'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
            )}
            title="Team session — multiple specialists discuss together"
          >
            <Users className="h-3 w-3" />
            Team
          </button>
          <button
            onClick={() => { setShowVideo(!showVideo); setShowTeam(false); setShowTemplates(false); setShowRoles(false); }}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] transition-colors',
              showVideo
                ? 'bg-pink-500/20 text-pink-400 font-medium'
                : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
            )}
            title="Generate a video ad from a script (ElevenLabs + HeyGen)"
          >
            <Film className="h-3 w-3" />
            Video
          </button>
          <span className="text-[10px] text-muted-foreground">{currentModel.desc}</span>
        </span>
      </div>

      {/* Attachment previews */}
      {(attachments.length > 0 || uploading) && (
        <div className="flex flex-wrap gap-1.5 px-1">
          {attachments.map((att) => (
            <div
              key={att.filename}
              className="group relative flex items-center gap-1.5 px-2 py-1 rounded-md bg-secondary/60 border border-border text-[11px]"
            >
              {att.is_image ? (
                <img
                  src={att.url}
                  alt={att.filename}
                  className="h-8 w-8 rounded object-cover"
                />
              ) : (
                <FileText className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              <span className="max-w-[140px] truncate">{att.filename}</span>
              <span className="text-[9px] text-muted-foreground">
                {att.size > 1024 * 1024
                  ? `${(att.size / (1024 * 1024)).toFixed(1)}MB`
                  : `${Math.round(att.size / 1024)}KB`}
              </span>
              <button
                onClick={() => removeAttachment(att.filename)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-0.5 hover:bg-destructive/20 rounded"
                title="Remove"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
          {uploading && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-secondary/60 border border-border text-[11px]">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>Uploading…</span>
            </div>
          )}
        </div>
      )}

      {/* Input + send */}
      <div className="flex items-end gap-2">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
        />
        {/* Attach button */}
        <Button
          size="icon"
          variant="ghost"
          className="h-9 w-9 shrink-0 self-end"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          title="Attach file"
        >
          <Paperclip className="h-4 w-4" />
        </Button>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); handleInput(); }}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={disabled ? "Type to queue next message..." : "Ask about this campaign... (paste images with Cmd+V)"}
          rows={1}
          className="flex-1 resize-none bg-secondary/50 border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        {disabled && onStop && (
          <Button
            size="icon"
            variant="destructive"
            className="h-9 w-9 shrink-0"
            onClick={onStop}
            title="Stop agent"
          >
            <Square className="h-4 w-4 fill-current" />
          </Button>
        )}
        <Button
          size="icon"
          className="h-9 w-9 shrink-0"
          disabled={!value.trim() && attachments.length === 0}
          onClick={handleSend}
          title={disabled ? "Queue message" : "Send message"}
        >
          <SendHorizonal className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
