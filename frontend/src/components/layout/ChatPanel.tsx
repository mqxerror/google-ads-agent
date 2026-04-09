import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { GripVertical, Maximize2, Minimize2, Trash2, Plus, Search, MessageSquare, ChevronLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { fetchConversations, createConversation, deleteConversation, fetchMessages, searchConversations, stopAgentTask } from '@/lib/api';
import ContextBadge from '@/components/chat/ContextBadge';
import ChatMessageComponent from '@/components/chat/ChatMessage';
import ChatInput, { type ModelId } from '@/components/chat/ChatInput';
import MemoryPanel from '@/components/chat/MemoryPanel';
import { Input } from '@/components/ui/input';
import type { ChatMessage, ToolCall, Campaign, Conversation, ConversationSearchResult } from '@/types';

export default function ChatPanel() {
  const { chatPanelWidth, setChatPanelWidth, selectedCampaignId } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isResponding, setIsResponding] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef(false);
  const queryClient = useQueryClient();
  const ACCOUNT_ID = useClientAccountId();

  const campaigns = queryClient.getQueryData<Campaign[]>(['campaigns', ACCOUNT_ID]) ?? [];
  const campaign = campaigns.find((c) => c.id === selectedCampaignId);

  // Fetch conversation history for current context
  const { data: conversations = [], refetch: refetchConversations } = useQuery({
    queryKey: ['conversations', ACCOUNT_ID, selectedCampaignId],
    queryFn: () => fetchConversations(ACCOUNT_ID, selectedCampaignId || undefined),
    staleTime: 30_000,
    enabled: !!ACCOUNT_ID,
  });

  // Search results
  const { data: searchResults = [] } = useQuery({
    queryKey: ['conversation-search', searchQuery, ACCOUNT_ID],
    queryFn: () => searchConversations(searchQuery, ACCOUNT_ID),
    enabled: searchQuery.length >= 2,
    staleTime: 10_000,
  });

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load conversation messages when switching conversations
  const loadConversation = useCallback(async (convId: string) => {
    setConversationId(convId);
    setShowHistory(false);
    try {
      const msgs = await fetchMessages(convId);
      setMessages(msgs);
    } catch {
      setMessages([]);
    }
  }, []);

  // Auto-load last conversation for current campaign
  useEffect(() => {
    if (conversations.length > 0 && !conversationId) {
      // Load the most recent conversation for this campaign
      loadConversation(conversations[0].id);
    }
  }, [conversations, conversationId, loadConversation]);

  // Reset when campaign changes
  useEffect(() => {
    setConversationId(null);
    setMessages([]);
    setShowHistory(false);
    setSearchQuery('');
  }, [selectedCampaignId]);

  // Create new conversation
  const handleNewConversation = useCallback(async () => {
    const conv = await createConversation({
      account_id: ACCOUNT_ID,
      campaign_id: selectedCampaignId || undefined,
      campaign_name: campaign?.name,
      title: campaign ? `${campaign.name} chat` : 'New chat',
    });
    setConversationId(conv.id);
    setMessages([]);
    setShowHistory(false);
    refetchConversations();
  }, [ACCOUNT_ID, selectedCampaignId, campaign?.name, refetchConversations]);

  // Delete conversation
  const handleDeleteConversation = useCallback(async (convId: string) => {
    await deleteConversation(convId);
    if (conversationId === convId) {
      setConversationId(null);
      setMessages([]);
    }
    refetchConversations();
  }, [conversationId, refetchConversations]);

  // Ensure conversation exists for sending
  const ensureConversation = useCallback(async (): Promise<string> => {
    if (conversationId) return conversationId;
    const conv = await createConversation({
      account_id: ACCOUNT_ID,
      campaign_id: selectedCampaignId || undefined,
      campaign_name: campaign?.name,
      title: campaign ? `${campaign.name} chat` : 'New chat',
    });
    setConversationId(conv.id);
    refetchConversations();
    return conv.id;
  }, [conversationId, ACCOUNT_ID, selectedCampaignId, campaign?.name, refetchConversations]);

  // Resize handling
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      resizingRef.current = true;
      const startX = e.clientX;
      const startWidth = chatPanelWidth;
      const handleMouseMove = (ev: MouseEvent) => {
        if (!resizingRef.current) return;
        const delta = startX - ev.clientX;
        setChatPanelWidth(Math.max(300, Math.min(700, startWidth + delta)));
      };
      const handleMouseUp = () => {
        resizingRef.current = false;
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [chatPanelWidth, setChatPanelWidth]
  );

  // Send message
  const handleSend = useCallback(
    async (text: string, model: ModelId = 'sonnet', roleId?: string) => {
      const userMsg: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: text,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsResponding(true);

      try {
        const convId = await ensureConversation();
        const res = await fetch(`/api/conversations/${convId}/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: text,
            account_id: ACCOUNT_ID,
            campaign_id: selectedCampaignId,
            model,
            active_role: roleId || null,
          }),
        });

        if (!res.ok) throw new Error(`API error ${res.status}`);
        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let assistantText = '';
        const toolCalls: ToolCall[] = [];
        const assistantMsgId = `msg-${Date.now()}-resp`;
        let resolvedRole = { id: '', name: '', avatar: '' };

        setMessages((prev) => [
          ...prev,
          { id: assistantMsgId, role: 'assistant', content: '', toolCalls: [], createdAt: new Date().toISOString() },
        ]);

        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6).trim();
            if (!dataStr || dataStr === '[DONE]') continue;
            try {
              const event = JSON.parse(dataStr);
              if (event.type === 'routing') {
                resolvedRole = { id: event.role_id || '', name: event.role_name || '', avatar: event.role_avatar || '' };
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, agentRole: resolvedRole.id, agentRoleName: resolvedRole.name, agentRoleAvatar: resolvedRole.avatar } : m));
              } else if (event.type === 'text') {
                assistantText += event.content || '';
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText, toolCalls: [...toolCalls] } : m));
              } else if (event.type === 'tool_call') {
                toolCalls.push({ id: event.id || `tc-${Date.now()}`, source: event.source || 'google-ads', name: event.name || 'unknown', input: event.input || {}, status: 'pending' });
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, toolCalls: [...toolCalls] } : m));
              } else if (event.type === 'tool_result') {
                const tcIdx = toolCalls.findIndex((tc) => tc.id === event.id);
                if (tcIdx >= 0) {
                  toolCalls[tcIdx] = { ...toolCalls[tcIdx], output: typeof event.output === 'string' ? { result: event.output } : event.output || {}, status: event.status === 'error' ? 'error' : 'success' };
                  setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, toolCalls: [...toolCalls] } : m));
                }
              } else if (event.type === 'continuation') {
                // Agent auto-continuing after max-turns — show subtle indicator
                assistantText += `\n\n---\n*Continuing... (${event.accumulated_turns} turns)*\n\n`;
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText, toolCalls: [...toolCalls] } : m));
              } else if (event.type === 'done') {
                // Show stop reason so user knows WHY the agent stopped
                const reason = event.stop_reason;
                const turns = event.turns || 0;
                const cost = event.cost ? `$${Number(event.cost).toFixed(2)}` : '';
                let stopNote = '';
                if (reason === 'cost_cap') {
                  stopNote = `\n\n> Agent stopped — cost safety limit reached (${cost}).`;
                } else if (reason === 'max_continuations') {
                  stopNote = `\n\n> Agent stopped — turn limit reached (${turns} turns). Send "continue" to keep going.`;
                } else if (reason === 'user_stopped') {
                  stopNote = '\n\n> Agent stopped by user.';
                } else if (reason && reason !== 'natural') {
                  stopNote = `\n\n> Agent stopped (${reason}, ${turns} turns, ${cost}).`;
                }
                if (stopNote) {
                  assistantText += stopNote;
                  setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                }
                queryClient.invalidateQueries({ queryKey: ['campaigns'] });
                refetchConversations();
              } else if (event.type === 'error') {
                assistantText += `\n\n**Error:** ${event.message}`;
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
              }
            } catch {}
          }
        }
      } catch (err) {
        setMessages((prev) => [...prev, {
          id: `msg-${Date.now()}-err`, role: 'assistant',
          content: `**Connection error:** ${err instanceof Error ? err.message : 'Unknown error'}`,
          createdAt: new Date().toISOString(),
        }]);
      } finally {
        setIsResponding(false);
        // Sweep: any tool calls still 'pending' when the stream ends are stuck/interrupted.
        // Mark them as error so the user sees they didn't complete.
        setMessages((prev) => prev.map((m) => ({
          ...m,
          toolCalls: m.toolCalls?.map((tc) => tc.status === 'pending' ? { ...tc, status: 'error' as const } : tc),
        })));
      }
    },
    [ensureConversation, selectedCampaignId, ACCOUNT_ID, queryClient, refetchConversations]
  );

  const panelWidth = expanded ? Math.max(chatPanelWidth, 700) : chatPanelWidth;

  return (
    <div
      className="bg-sidebar border-l border-border flex shrink-0 overflow-hidden transition-[width] duration-200"
      style={{ width: `${panelWidth}px`, maxWidth: '70vw' }}
    >
      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className={cn('w-1.5 cursor-col-resize hover:bg-primary/30 transition-colors flex items-center justify-center', resizingRef.current && 'bg-primary/30')}
      >
        <GripVertical className="h-4 w-4 text-muted-foreground opacity-0 hover:opacity-100 transition-opacity" />
      </div>

      {/* Chat content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Toolbar */}
        <div className="border-b border-border flex items-center justify-between pr-2">
          <div className="flex items-center gap-1">
            <ContextBadge campaignName={campaign?.name ?? null} guidelinesLoaded={true} />
            {conversations.length > 0 && (
              <button
                onClick={() => setShowHistory(!showHistory)}
                className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                title={`${conversations.length} conversation${conversations.length !== 1 ? 's' : ''}`}
              >
                <MessageSquare className="h-3.5 w-3.5" />
                <span className="text-[9px] ml-0.5">{conversations.length}</span>
              </button>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button onClick={handleNewConversation} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title="New conversation">
              <Plus className="h-3.5 w-3.5" />
            </button>
            {conversationId && (
              <button onClick={() => handleDeleteConversation(conversationId)} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title="Delete conversation">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
            <button onClick={() => setExpanded(!expanded)} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title={expanded ? 'Collapse' : 'Expand'}>
              {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>

        {/* Conversation History Panel */}
        {showHistory && (
          <div className="border-b border-border bg-card max-h-64 overflow-y-auto">
            {/* Search */}
            <div className="p-2">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search conversations..."
                  className="h-7 text-xs pl-7 bg-secondary/50"
                />
              </div>
            </div>

            {/* Search results */}
            {searchQuery.length >= 2 && searchResults.length > 0 && (
              <div className="px-2 pb-1">
                <p className="text-[10px] text-muted-foreground px-1 mb-1">Search results</p>
                {searchResults.map((r) => (
                  <button
                    key={r.message_id}
                    onClick={() => loadConversation(r.conversation_id)}
                    className="w-full text-left px-2 py-1.5 text-xs hover:bg-secondary/60 rounded-sm"
                  >
                    <span className="text-muted-foreground">{r.campaign_name || 'General'}</span>
                    <p className="truncate text-[11px]">{r.content_snippet}</p>
                  </button>
                ))}
              </div>
            )}

            {/* Conversation list */}
            {(!searchQuery || searchQuery.length < 2) && (
              <div className="px-2 pb-2">
                {conversations.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => loadConversation(conv.id)}
                    className={cn(
                      'w-full text-left flex items-center justify-between px-2 py-1.5 text-xs rounded-sm hover:bg-secondary/60 transition-colors',
                      conversationId === conv.id && 'bg-secondary font-medium'
                    )}
                  >
                    <div className="min-w-0">
                      <p className="truncate">{conv.title || 'Untitled'}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {conv.campaignName || 'General'} — {conv.messageCount || 0} msgs
                      </p>
                    </div>
                    <span className="text-[9px] text-muted-foreground shrink-0 ml-2">
                      {conv.updatedAt ? new Date(conv.updatedAt).toLocaleDateString() : ''}
                    </span>
                  </button>
                ))}
                {conversations.length === 0 && (
                  <p className="text-[11px] text-muted-foreground text-center py-3">No conversations yet</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="py-2">
            {messages.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Ask anything about your campaigns. The AI agent has access to all 87 Google Ads tools.
              </div>
            )}
            {messages.map((msg) => (
              <ChatMessageComponent key={msg.id} message={msg} />
            ))}
            {isResponding && messages[messages.length - 1]?.role === 'user' && (
              <div className="px-4 py-2 text-xs text-muted-foreground animate-pulse">
                Agent is thinking...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Memory Panel */}
        <MemoryPanel
          campaignId={selectedCampaignId}
          campaignName={campaign?.name}
        />

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          disabled={isResponding}
          campaignName={campaign?.name}
          conversations={conversations.map(c => ({
            id: c.id,
            title: c.title || 'Untitled',
            campaignName: c.campaignName || null,
            messageCount: c.messageCount || 0,
          }))}
          onStop={async () => {
            if (conversationId) {
              try { await stopAgentTask(conversationId); } catch {}
              setIsResponding(false);
            }
          }}
        />
      </div>
    </div>
  );
}
