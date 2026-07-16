import { useRef, useState, useCallback, useEffect, type KeyboardEvent, type ClipboardEvent } from 'react';
import { SendHorizonal, Zap, Brain, Sparkles, LayoutTemplate, X, Square, Users, ChevronDown, Paperclip, FileText, Loader2, Film } from 'lucide-react';
import VideoCreator from './VideoCreator';
import { cn } from '@/lib/utils';
import templates, { TEMPLATE_CATEGORIES, type ChatTemplate } from '@/lib/chatTemplates';

export interface Attachment {
  filename: string;
  path: string;
  is_image: boolean;
  ext: string;
  url: string;
  size: number;
}

export type ModelId = 'fable' | 'sonnet' | 'opus' | 'haiku';

const MODELS: { id: ModelId; label: string; desc: string; icon: typeof Zap }[] = [
  { id: 'fable', label: 'Fable 5', desc: 'Deepest · default', icon: Brain },
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
  onSend: (text: string, model: ModelId, roleId?: string, attachments?: Attachment[], orchestrate?: boolean) => void;
  disabled: boolean;
  campaignName?: string | null;
  onStop?: () => void;
  /** FIX 2c — optimistic stop: Stop was clicked; show a spinner + disable it
   *  immediately, before the stop round-trip resolves. */
  stopping?: boolean;
  /** FIX 3 — a duplicate send was just dropped; show a brief inline hint. */
  dupHint?: boolean;
  conversations?: ConversationRef[];
  conversationId?: string | null;
  onEnsureConversation?: () => Promise<string>;
  onVideoReady?: (url: string, script: string, thumbnail?: string) => void;
}

export default function ChatInput({ onSend, disabled, campaignName, onStop, stopping, dupHint, conversations = [], conversationId, onEnsureConversation, onVideoReady }: ChatInputProps) {
  const [value, setValue] = useState('');
  const [model, setModel] = useState<ModelId>('fable');
  const [showTemplates, setShowTemplates] = useState(false);
  const [showRoles, setShowRoles] = useState(false);
  const [showTeam, setShowTeam] = useState(false);
  const [showVideo, setShowVideo] = useState(false);
  const [teamRoles, setTeamRoles] = useState<Set<string>>(new Set());
  // "Ask the team" — v2 orchestration toggle. DEFAULT OFF: the send stays the
  // byte-identical direct path until the user explicitly opts in. When ON, the
  // POST body carries `orchestrate:true` (force-orchestrate). Persisted
  // PER-CONVERSATION in localStorage (same convention as selectedCampaignId in
  // appStore) so the choice survives a refresh but stays scoped to the thread.
  const orchestrateKey = conversationId ? `orchestrate:${conversationId}` : null;
  const [orchestrate, setOrchestrateRaw] = useState<boolean>(() =>
    orchestrateKey ? localStorage.getItem(orchestrateKey) === 'true' : false,
  );
  // Re-hydrate from storage on a conversation switch (default OFF for a thread
  // that never opted in). Without this, switching conversations would carry the
  // previous thread's toggle over.
  useEffect(() => {
    setOrchestrateRaw(orchestrateKey ? localStorage.getItem(orchestrateKey) === 'true' : false);
  }, [orchestrateKey]);
  const setOrchestrate = useCallback(
    (next: boolean | ((v: boolean) => boolean)) => {
      setOrchestrateRaw((prev) => {
        const value = typeof next === 'function' ? next(prev) : next;
        if (orchestrateKey) {
          if (value) localStorage.setItem(orchestrateKey, 'true');
          else localStorage.removeItem(orchestrateKey);
        }
        return value;
      });
    },
    [orchestrateKey],
  );
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
      onSend(teamPrompt, model, 'director', attachments, orchestrate);
    } else {
      onSend(messageText, model, messageRole, attachments, orchestrate);
    }

    setValue('');
    setAttachments([]);
    setShowTeam(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [value, onSend, model, activeRole, roles, attachments, showTeam, teamRoles, orchestrate]);

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
                    <span className="text-[9px] text-warning bg-warning-soft px-1 rounded">needs campaign</span>
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
                  activeRole === role.id && 'bg-accent-soft border border-accent/30'
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
        <div className="bg-card border border-border rounded-lg shadow-lg overflow-hidden">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-accent-soft">
            <span className="text-[10px] font-medium text-accent">Team Session — Pick specialists to discuss</span>
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
                    ? 'bg-accent-soft border border-accent/40 text-accent'
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

      {/* Model selector + feature tabs — unified quiet ghosts. Selected =
          accent-soft; no per-feature blue/purple/pink theming. */}
      <div className="flex items-center gap-1">
        {MODELS.map((m) => {
          const Icon = m.icon;
          return (
            <button
              key={m.id}
              onClick={() => setModel(m.id)}
              className={cn(
                'flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] transition-colors',
                model === m.id
                  ? 'bg-accent-soft text-accent font-medium'
                  : 'text-muted-foreground hover:text-text hover:bg-surface-3'
              )}
              title={m.desc}
            >
              <Icon className="h-3 w-3" />
              {m.label}
            </button>
          );
        })}
        {/* "Ask the team" — v2 orchestration toggle. Quiet ghost, DEFAULT OFF.
            ON = the Director convenes specialists for this turn (orchestrate:true). */}
        <button
          onClick={() => setOrchestrate((v) => !v)}
          className={cn(
            'flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] transition-colors',
            orchestrate
              ? 'bg-accent-soft text-accent font-medium'
              : 'text-muted-foreground hover:text-text hover:bg-surface-3'
          )}
          title={orchestrate
            ? 'Ask the team is ON — the Director convenes specialists for this turn'
            : 'Ask the team — convene specialists (default off; direct chat otherwise)'}
          aria-pressed={orchestrate}
        >
          <Sparkles className="h-3 w-3" />
          Ask the team
        </button>
        <span className="ml-auto flex items-center gap-2">
          {/* Role selector */}
          <div className="relative">
            <button
              onClick={() => { setShowRoles(!showRoles); setShowTemplates(false); }}
              className={cn(
                'flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] transition-colors',
                activeRole || showRoles
                  ? 'bg-accent-soft text-accent font-medium'
                  : 'text-muted-foreground hover:text-text hover:bg-surface-3'
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
              'flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] transition-colors',
              showTemplates
                ? 'bg-accent-soft text-accent font-medium'
                : 'text-muted-foreground hover:text-text hover:bg-surface-3'
            )}
            title="Smart templates"
          >
            <LayoutTemplate className="h-3 w-3" />
            Templates
          </button>
          <button
            onClick={() => { setShowTeam(!showTeam); setShowTemplates(false); setShowRoles(false); setShowVideo(false); }}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] transition-colors',
              showTeam
                ? 'bg-accent-soft text-accent font-medium'
                : 'text-muted-foreground hover:text-text hover:bg-surface-3'
            )}
            title="Team session — multiple specialists discuss together"
          >
            <Users className="h-3 w-3" />
            Team
          </button>
          <button
            onClick={() => { setShowVideo(!showVideo); setShowTeam(false); setShowTemplates(false); setShowRoles(false); }}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] transition-colors',
              showVideo
                ? 'bg-accent-soft text-accent font-medium'
                : 'text-muted-foreground hover:text-text hover:bg-surface-3'
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

      {/* FIX 3 — duplicate-send hint. Quiet inline note (no new colors), shown
          briefly when an identical message was dropped while one was in flight. */}
      {dupHint && (
        <p className="px-1 text-[10px] text-subtle" role="status" aria-live="polite">
          Already queued, waiting for the current reply.
        </p>
      )}

      {/* Input + send — one sunken well framed as a single control. */}
      <div className="flex items-end gap-2 rounded-[12px] border border-border bg-surface-2 px-2 py-1.5 transition-colors focus-within:border-accent">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
        />
        {/* Attach button — quiet ghost */}
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          title="Attach file"
          className="flex h-8 w-8 shrink-0 items-center justify-center self-end rounded-md text-muted-foreground hover:bg-surface-3 hover:text-text disabled:opacity-50 transition-colors"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); handleInput(); }}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={disabled ? "Type to queue next message..." : "Ask about this campaign... (paste images with Cmd+V)"}
          rows={1}
          className="flex-1 resize-none bg-transparent px-1 py-1.5 text-sm text-text placeholder:text-subtle outline-none"
        />
        {disabled && onStop && (
          <button
            onClick={onStop}
            disabled={stopping}
            title={stopping ? 'Stopping…' : 'Stop agent'}
            className="flex h-8 w-8 shrink-0 items-center justify-center self-end rounded-md bg-danger text-on-accent hover:opacity-90 disabled:opacity-70 transition-opacity"
          >
            {stopping ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4 fill-current" />
            )}
          </button>
        )}
        <button
          disabled={!value.trim() && attachments.length === 0}
          onClick={handleSend}
          title={disabled ? "Queue message" : "Send message"}
          className="flex h-8 w-8 shrink-0 items-center justify-center self-end rounded-md bg-accent text-on-accent hover:bg-accent-hover disabled:opacity-40 disabled:hover:bg-accent transition-colors"
        >
          <SendHorizonal className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
