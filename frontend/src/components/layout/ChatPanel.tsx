import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { GripVertical, Maximize2, Minimize2, Trash2, Plus, Search, MessageSquare, ChevronLeft, ChevronRight, Download, Expand, Shrink, PanelRightClose } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { fetchConversations, createConversation, fetchConversation, deleteConversation, fetchMessages, searchConversations, stopAgentTask } from '@/lib/api';
import ContextBadge, { type ContextMetaData } from '@/components/chat/ContextBadge';
import ChatMessageComponent from '@/components/chat/ChatMessage';
import ChatInput, { type ModelId, type Attachment } from '@/components/chat/ChatInput';
import MemoryPanel from '@/components/chat/MemoryPanel';
import { Input } from '@/components/ui/input';
import type { ChatMessage, ToolCall, Campaign, Conversation, ConversationSearchResult } from '@/types';

export default function ChatPanel() {
  const { chatPanelWidth, setChatPanelWidth, selectedCampaignId, chatPanelCollapsed, toggleChatPanel } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isResponding, setIsResponding] = useState(false);
  const [conversationId, setConversationIdRaw] = useState<string | null>(() => {
    // Restore conversation from sessionStorage on mount
    const saved = sessionStorage.getItem('activeConversationId');
    return saved || null;
  });
  const setConversationId = useCallback((id: string | null) => {
    if (id) sessionStorage.setItem('activeConversationId', id);
    else sessionStorage.removeItem('activeConversationId');
    setConversationIdRaw(id);
  }, []);
  const [expanded, setExpanded] = useState(false);
  const [fullScreen, setFullScreen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [contextMeta, setContextMeta] = useState<ContextMetaData | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();
  const ACCOUNT_ID = useClientAccountId();

  const campaigns = queryClient.getQueryData<Campaign[]>(['campaigns', ACCOUNT_ID]) ?? [];
  const campaign = campaigns.find((c) => c.id === selectedCampaignId);

  // The CONVERSATION's actual campaign binding (authoritative — server-resolved).
  // The chat panel previously displayed selectedCampaignId in the badge and the
  // pinned-facts panel, while the agent loaded context for the conversation's
  // own campaign_id. When those disagreed (e.g. user clicks Panama while the
  // active thread is bound to MapleRoots), the badge + facts lied about the
  // agent's actual scope. Tracking the conv's real campaign here lets the
  // whole panel speak with one voice — the conversation's voice.
  const [activeConvCampaign, setActiveConvCampaign] = useState<{ id: string | null; name: string | null } | null>(null);

  // Look the conversation up whenever conversationId changes so badge / memory
  // panel / input all reflect what the agent will ACTUALLY operate on.
  useEffect(() => {
    if (!conversationId) {
      setActiveConvCampaign(null);
      return;
    }
    let cancelled = false;
    fetchConversation(conversationId).then((c) => {
      if (cancelled) return;
      setActiveConvCampaign(c ? { id: c.campaignId ?? null, name: c.campaignName ?? null } : null);
    });
    return () => { cancelled = true; };
  }, [conversationId]);

  // Effective scope for the whole panel = the conversation's campaign if we
  // have one, else the sidebar selection. Conversation wins because that's
  // what the agent reads.
  const effectiveCampaignId = activeConvCampaign?.id ?? selectedCampaignId;
  const effectiveCampaignName =
    activeConvCampaign?.name ?? campaign?.name ?? null;

  // Sidebar disagrees with the conversation — the user is asking for a
  // different campaign than the active thread is bound to. A NULL sidebar
  // (Account Overview / dashboard / Builder running campaign-less) is NOT a
  // mismatch — it means "no filter," so honor the conversation's own
  // binding. Same rule as ensureConversation below, so the two stay aligned
  // and Builder's chat:display handoff isn't yanked away.
  const campaignMismatch =
    !!activeConvCampaign &&
    selectedCampaignId !== null &&
    (activeConvCampaign.id ?? null) !== selectedCampaignId;

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

  // Auto-load conversation: restore from session or pick the most recent.
  // `conversations` is already scoped to the selected campaign server-side, so
  // a restored conversationId that isn't in it belongs to a DIFFERENT campaign
  // (e.g. refresh after a campaign switch, or a Builder handoff thread). Drop
  // it so the wrong campaign's history isn't shown. Gated on messages.length
  // === 0 so an in-flight send (optimistic messages present, fresh conv not
  // yet in the refetched list) is never cleared mid-stream.
  useEffect(() => {
    if (conversationId && messages.length === 0) {
      const inThisCampaign = conversations.some((c) => c.id === conversationId);
      if (!inThisCampaign && conversations.length > 0) {
        setConversationId(null); // foreign thread → fall through to picking one below
      } else {
        loadConversation(conversationId);
      }
    } else if (conversations.length > 0 && !conversationId) {
      // No active conversation — load the most recent one for this campaign
      loadConversation(conversations[0].id);
    }
  }, [conversations, conversationId, messages.length, loadConversation, setConversationId]);

  // Reconnect to running agent after page refresh
  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`/api/conversations/${conversationId}/agent/status`);
        const status = await res.json();
        if (status.running && !cancelled) {
          setIsResponding(true);
          // Reconnect to the stream from where the buffer is
          const streamRes = await fetch(`/api/conversations/${conversationId}/agent/stream?cursor=0`);
          const reader = streamRes.body?.getReader();
          if (!reader) return;

          const decoder = new TextDecoder();
          const assistantMsgId = `msg-${Date.now()}-reconnect`;
          let assistantText = '';
          const toolCalls: ToolCall[] = [];

          // Add a placeholder message for the reconnected stream
          setMessages((prev) => {
            // Don't add if already has a streaming message
            if (prev.some(m => m.content === '' && m.role === 'assistant')) return prev;
            return [...prev, { id: assistantMsgId, role: 'assistant', content: '(reconnecting...)\n\n', toolCalls: [], createdAt: new Date().toISOString() }];
          });

          let buffer = '';
          while (true) {
            const { done, value } = await reader.read();
            if (done || cancelled) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (!line.startsWith('data: ')) continue;
              const dataStr = line.slice(6).trim();
              if (!dataStr) continue;
              try {
                const event = JSON.parse(dataStr);
                if (event.type === 'text') {
                  assistantText += event.content || '';
                  setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                } else if (event.type === 'routing') {
                  setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, agentRole: event.role_id, agentRoleName: event.role_name, agentRoleAvatar: event.role_avatar } : m));
                } else if (event.type === 'done' || event.type === 'error') {
                  setIsResponding(false);
                }
              } catch {}
            }
          }
          setIsResponding(false);
        }
      } catch {
        // Agent status check failed — no agent running, that's fine
      }
    })();

    return () => { cancelled = true; };
  }, [conversationId]);

  // Deterministic campaign-switch reset. The old guard compared against a
  // sessionStorage value it mutated itself, which the Campaign Builder's
  // out-of-band conversation handoff defeated — so a thread bound to one
  // campaign survived a switch and the agent kept talking about the old
  // campaign. Track the previous campaign in a ref instead: on a genuine
  // switch (we had a campaign and it changed), drop the conversation so the
  // next send opens a fresh thread for the new campaign. The first run
  // (mount / initial null→campaign hydration) only records the baseline so a
  // refresh-restored conversation isn't nuked; ensureConversation still
  // verifies its campaign binding before reusing it.
  const prevCampaignRef = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    const prev = prevCampaignRef.current;
    prevCampaignRef.current = selectedCampaignId;
    setShowHistory(false);
    setSearchQuery('');
    setContextMeta(null); // Reset context badge for the new campaign
    // Any genuine change in the sidebar's selected campaign clears the active
    // conversation. The conversation's campaign is immutable on the backend
    // (see chat.py), so we never carry a thread across a real campaign change
    // — the next send opens a fresh thread bound to the new selection.
    if (prev !== undefined && prev !== selectedCampaignId) {
      setConversationId(null);
      setMessages([]);
      setActiveConvCampaign(null);
    }
  }, [selectedCampaignId, setConversationId]);

  // Refresh edge case: a conversationId restored from sessionStorage points
  // at a thread bound to a campaign different from the user's
  // localStorage-restored selectedCampaignId. The campaign-switch effect
  // above doesn't fire (selectedCampaignId never changed within this
  // session), so drop the foreign thread here once we've resolved its real
  // campaign. Guarded on !isResponding so we never yank a thread mid-stream.
  useEffect(() => {
    if (campaignMismatch && !isResponding) {
      setConversationId(null);
      setMessages([]);
      setActiveConvCampaign(null);
    }
  }, [campaignMismatch, isResponding, setConversationId]);

  // Create new conversation
  const handleNewConversation = useCallback(async () => {
    const conv = await createConversation({
      account_id: ACCOUNT_ID,
      campaign_id: selectedCampaignId || undefined,
      campaign_name: campaign?.name,
      title: campaign ? `${campaign.name} chat` : 'New chat',
    });
    setConversationId(conv.id);
    // Set the conversation's actual binding up-front so the badge / pinned
    // facts / input don't briefly flash the sidebar's campaign before the
    // fetchConversation effect resolves.
    setActiveConvCampaign({ id: conv.campaignId ?? null, name: conv.campaignName ?? null });
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

  // Export conversation as markdown
  const handleExportChat = useCallback(() => {
    if (messages.length === 0) return;
    const title = campaign?.name || 'Chat';
    const date = new Date().toISOString().slice(0, 10);
    const lines = [
      `# ${title}`,
      `Exported: ${date}`,
      `Messages: ${messages.length}`,
      '',
      '---',
      '',
    ];
    for (const msg of messages) {
      if (msg.role === 'user') {
        lines.push(`## User`);
      } else {
        const role = msg.agentRoleName || 'Assistant';
        lines.push(`## ${role}`);
      }
      lines.push('');
      lines.push(msg.content);
      if (msg.toolCalls && msg.toolCalls.length > 0) {
        lines.push('');
        lines.push(`> ${msg.toolCalls.length} tool call(s): ${msg.toolCalls.map(t => t.name).join(', ')}`);
      }
      lines.push('');
      lines.push('---');
      lines.push('');
    }
    const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/[^a-zA-Z0-9-_ ]/g, '')}_${date}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [messages, campaign?.name]);

  // Ensure conversation exists for sending
  const ensureConversation = useCallback(async (): Promise<string> => {
    // Reuse the active conversation when its campaign binding doesn't conflict
    // with the sidebar selection. A conversation belongs to one campaign for
    // life; reusing one from another campaign loads the wrong memory (the
    // original bug). But "no campaign selected" (Account Overview / dashboard
    // view) is NOT a conflict — it means no filter, so honor the loaded
    // conversation's own binding. Without this, sending a message while on
    // the overview spawned a fresh unbound thread that lost MapleRoots
    // context and responded "no campaign selected."
    if (conversationId) {
      const existing = await fetchConversation(conversationId);
      const ok =
        !!existing && (
          selectedCampaignId == null ||
          (existing.campaignId ?? null) === selectedCampaignId
        );
      if (ok) return conversationId;
      // Missing, or bound to a *different* campaign than the one selected — start a fresh thread.
      setConversationId(null);
    }
    const conv = await createConversation({
      account_id: ACCOUNT_ID,
      campaign_id: selectedCampaignId || undefined,
      campaign_name: campaign?.name,
      title: campaign ? `${campaign.name} chat` : 'New chat',
    });
    setConversationId(conv.id);
    // Pre-populate the conv's binding so the badge / pinned facts / input
    // reflect it immediately without waiting for the fetchConversation effect.
    setActiveConvCampaign({ id: conv.campaignId ?? null, name: conv.campaignName ?? null });
    refetchConversations();
    return conv.id;
  }, [conversationId, ACCOUNT_ID, selectedCampaignId, campaign?.name, refetchConversations, setConversationId]);

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

  // Message queue — allows sending while agent is working
  const [messageQueue, setMessageQueue] = useState<Array<{text: string, model: ModelId, roleId?: string, attachments?: Attachment[]}>>([]);

  // Drain queue when agent finishes
  useEffect(() => {
    if (!isResponding && messageQueue.length > 0) {
      const next = messageQueue[0];
      setMessageQueue((prev) => prev.slice(1));
      // Remove pending flag from the queued message
      setMessages((prev) => prev.map((m) => m.isPending ? { ...m, isPending: false } : m));
      actualSend(next.text, next.model, next.roleId, next.attachments);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isResponding, messageQueue.length]);

  // Send message (queues if agent is busy)
  const handleSend = useCallback(
    (text: string, model: ModelId = 'sonnet', roleId?: string, attachments?: Attachment[]) => {
      if (isResponding) {
        // Queue the message — show it in chat with pending state
        const queuedMsg: ChatMessage = {
          id: `msg-${Date.now()}-q`,
          role: 'user',
          content: text,
          createdAt: new Date().toISOString(),
          isPending: true,
        };
        setMessages((prev) => [...prev, queuedMsg]);
        setMessageQueue((prev) => [...prev, { text, model, roleId, attachments }]);
        return;
      }
      actualSend(text, model, roleId, attachments);
    },
    [isResponding],
  );

  // Actual send (creates conversation, streams response)
  const actualSend = useCallback(
    async (text: string, model: ModelId = 'sonnet', roleId?: string, attachments?: Attachment[]) => {
      // Add user message if not already shown (queued messages are already in chat)
      setMessages((prev) => {
        const alreadyShown = prev.some((m) => m.role === 'user' && m.content === text && !m.isPending);
        if (alreadyShown) return prev;
        // Check if there's a pending version to unflag
        const hasPending = prev.some((m) => m.isPending && m.content === text);
        if (hasPending) return prev.map((m) => m.isPending && m.content === text ? { ...m, isPending: false } : m);
        return [...prev, { id: `msg-${Date.now()}`, role: 'user' as const, content: text, createdAt: new Date().toISOString() }];
      });
      setIsResponding(true);

      try {
        const convId = await ensureConversation();
        const controller = new AbortController();
        abortControllerRef.current = controller;
        const res = await fetch(`/api/conversations/${convId}/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            content: text,
            account_id: ACCOUNT_ID,
            campaign_id: selectedCampaignId,
            campaign_name: campaign?.name,
            model,
            active_role: roleId || null,
            attachments: attachments || [],
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
              if (event.type === 'context_meta') {
                setContextMeta(event as ContextMetaData);
              } else if (event.type === 'routing') {
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
              } else if (event.type === 'resumed') {
                // Picked up a previously stopped session — full prior context restored
                assistantText += `> ↩︎ *Resumed the previous session — continuing the task with full context.*\n\n`;
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText, toolCalls: [...toolCalls] } : m));
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
                // These stops save the Claude session — sending any message
                // resumes the exact task with full context (no redo).
                const resumable = event.resume_session_id
                  ? ' Session saved — send **"continue"** to resume exactly where it left off (no work lost).'
                  : '';
                if (reason === 'cost_cap') {
                  stopNote = `\n\n> Agent paused — cost safety cap reached (${cost}).${resumable}`;
                } else if (reason === 'max_continuations') {
                  stopNote = `\n\n> Agent paused — turn limit reached (${turns} turns).${resumable || ' Send "continue" to keep going.'}`;
                } else if (reason === 'user_stopped') {
                  stopNote = `\n\n> Agent stopped by user.${resumable}`;
                } else if (reason && reason !== 'natural') {
                  stopNote = `\n\n> Agent stopped (${reason}, ${turns} turns, ${cost}).${resumable}`;
                }
                if (stopNote) {
                  assistantText += stopNote;
                  setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                }
                queryClient.invalidateQueries({ queryKey: ['campaigns'] });
                refetchConversations();
                // Notify Campaign Builder and other listeners that the agent is done
                window.dispatchEvent(new Event('agent:done'));
              } else if (event.type === 'error') {
                assistantText += `\n\n**Error:** ${event.message}`;
                setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                window.dispatchEvent(new Event('agent:done'));
              }
            } catch {}
          }
        }
      } catch (err) {
        // AbortError is expected when user clicks Stop — don't show as error
        if (err instanceof DOMException && err.name === 'AbortError') {
          setMessages((prev) => prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: assistantText + '\n\n> Agent stopped by user.' }
              : m
          ));
        } else {
          setMessages((prev) => [...prev, {
            id: `msg-${Date.now()}-err`, role: 'assistant',
            content: `**Connection error:** ${err instanceof Error ? err.message : 'Unknown error'}`,
            createdAt: new Date().toISOString(),
          }]);
        }
      } finally {
        abortControllerRef.current = null;
        setIsResponding(false);
        // Sweep: any tool calls still 'pending' when the stream ends are stuck/interrupted.
        setMessages((prev) => prev.map((m) => ({
          ...m,
          toolCalls: m.toolCalls?.map((tc) => tc.status === 'pending' ? { ...tc, status: 'error' as const } : tc),
        })));
      }
    },
    [ensureConversation, selectedCampaignId, ACCOUNT_ID, queryClient, refetchConversations]
  );

  // Listen for external "chat:send" events (from Landing Page tab, Builder, etc.)
  const handleSendRef = useRef(handleSend);
  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

  // Listen for 'chat:display' — switch to a conversation and poll for updates
  useEffect(() => {
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    const displayHandler = (e: Event) => {
      const { conversationId: convId } = (e as CustomEvent).detail || {};
      if (convId) {
        setConversationId(convId);
        setMessages([]);
        setIsResponding(true);
        fetchMessages(convId).then(setMessages).catch(() => {});
        refetchConversations();
        // Poll for new messages while agent is responding
        if (pollTimer) clearInterval(pollTimer);
        let unchangedCount = 0;
        let lastMsgCount = 0;
        pollTimer = setInterval(async () => {
          try {
            const msgs = await fetchMessages(convId);
            setMessages(msgs);
            if (msgs.length === lastMsgCount) {
              unchangedCount++;
              // If no new messages for 6 seconds after agent has responded, stop polling
              if (unchangedCount >= 3 && msgs.length > 1 && msgs[msgs.length - 1]?.role === 'assistant') {
                if (pollTimer) clearInterval(pollTimer);
                setIsResponding(false);
                window.dispatchEvent(new Event('agent:done'));
              }
            } else {
              unchangedCount = 0;
              lastMsgCount = msgs.length;
            }
          } catch {}
        }, 2000);
        // Safety: stop after 5 min
        setTimeout(() => { if (pollTimer) clearInterval(pollTimer); setIsResponding(false); }, 300000);
      }
    };
    // chat:send — send a message via the normal streaming path
    const sendHandler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.text) {
        handleSendRef.current(detail.text, detail.model || 'opus', detail.roleId);
      }
    };
    window.addEventListener('chat:display', displayHandler);
    window.addEventListener('chat:send', sendHandler);
    return () => {
      window.removeEventListener('chat:display', displayHandler);
      window.removeEventListener('chat:send', sendHandler);
    };
  }, [setConversationId, refetchConversations]);

  // Esc exits full-screen so the user always has an out
  useEffect(() => {
    if (!fullScreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFullScreen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [fullScreen]);

  const panelWidth = expanded ? Math.max(chatPanelWidth, 700) : chatPanelWidth;

  // Collapsed mode — render a thin reopener strip on the right edge so the user
  // can still get the chat back with one click. Persists across sessions via
  // appStore (localStorage). Full-screen overrides this — if you went full-
  // screen and then collapsed, exiting full-screen returns you to collapsed.
  if (chatPanelCollapsed && !fullScreen) {
    return (
      <div className="w-8 bg-sidebar border-l border-border flex flex-col items-center py-2 shrink-0">
        <button
          onClick={toggleChatPanel}
          className="p-1 text-muted-foreground hover:text-foreground hover:bg-secondary/60 rounded transition-colors"
          title="Show chat panel"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="mt-2 text-[9px] text-muted-foreground writing-mode-vertical opacity-60 select-none"
             style={{ writingMode: 'vertical-rl' as never }}>
          Chat
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        'bg-sidebar border-l border-border flex shrink-0 overflow-hidden',
        fullScreen
          ? 'fixed inset-0 z-50 border-l-0 transition-none'
          : 'relative transition-[width] duration-200'
      )}
      style={fullScreen ? undefined : { width: `${panelWidth}px`, maxWidth: '70vw' }}
    >
      {/* Resize handle — hidden in full-screen since it has nothing to resize */}
      {!fullScreen && (
        <div
          onMouseDown={handleMouseDown}
          className={cn('w-1.5 cursor-col-resize hover:bg-primary/30 transition-colors flex items-center justify-center', resizingRef.current && 'bg-primary/30')}
        >
          <GripVertical className="h-4 w-4 text-muted-foreground opacity-0 hover:opacity-100 transition-opacity" />
        </div>
      )}

      {/* Chat content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Toolbar */}
        <div className="border-b border-border flex items-center justify-between pr-2">
          <div className="flex items-center gap-1">
            {!fullScreen && (
              <button
                onClick={toggleChatPanel}
                className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                title="Hide chat panel"
              >
                <PanelRightClose className="h-3.5 w-3.5" />
              </button>
            )}
            {/* Badge reflects the CONVERSATION's actual binding, not the
                sidebar. If they disagree the campaign-switch / mismatch
                effects already drop the foreign thread; while that resolves
                the badge speaks for the agent, not the sidebar. */}
            <ContextBadge campaignName={effectiveCampaignName} guidelinesLoaded={true} contextMeta={contextMeta} />
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
              <>
                <button onClick={handleExportChat} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title="Export chat as Markdown">
                  <Download className="h-3.5 w-3.5" />
                </button>
                <button onClick={() => handleDeleteConversation(conversationId)} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title="Delete conversation">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </>
            )}
            {!fullScreen && (
              <button onClick={() => setExpanded(!expanded)} className="p-1 text-muted-foreground hover:text-foreground transition-colors" title={expanded ? 'Shrink panel' : 'Widen panel'}>
                {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
              </button>
            )}
            <button
              onClick={() => setFullScreen(v => !v)}
              className={cn(
                'p-1 transition-colors',
                fullScreen ? 'text-primary hover:text-foreground' : 'text-muted-foreground hover:text-foreground'
              )}
              title={fullScreen ? 'Exit full screen (Esc)' : 'Full screen'}
            >
              {fullScreen ? <Shrink className="h-3.5 w-3.5" /> : <Expand className="h-3.5 w-3.5" />}
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
          <div className={cn('py-2', fullScreen && 'max-w-3xl mx-auto w-full')}>
            {messages.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                Ask anything about your campaigns. The AI agent has access to all 87 Google Ads tools.
              </div>
            )}
            {messages.map((msg) => (
              <ChatMessageComponent
                key={msg.id}
                message={msg}
                conversationId={conversationId ?? undefined}
                onDelete={async (msgId) => {
                  if (!conversationId) return;
                  try {
                    const { deleteMessage } = await import('@/lib/api');
                    await deleteMessage(conversationId, msgId);
                    setMessages((prev) => prev.filter((m) => m.id !== msgId));
                  } catch {}
                }}
              />
            ))}
            {isResponding && messages[messages.length - 1]?.role === 'user' && (
              <div className="px-4 py-2 text-xs text-muted-foreground animate-pulse">
                Agent is thinking...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Memory Panel — hidden in full-screen so the chat dominates the view */}
        {!fullScreen && (
          {/* MemoryPanel (pinned facts, decisions, role notes) reads the
              same campaign the agent loads — the conversation's binding.
              Previously it keyed off selectedCampaignId, so it would happily
              show Panama's pinned facts while the agent was operating on
              MapleRoots; the user would then see the facts being "ignored"
              when in fact they were never sent to the agent at all. */}
          <MemoryPanel
            campaignId={effectiveCampaignId}
            campaignName={effectiveCampaignName}
          />
        )}

        {/* Input — centered to a readable column in full-screen */}
        <div className={cn(fullScreen && 'max-w-3xl mx-auto w-full')}>
        <ChatInput
          onSend={handleSend}
          disabled={isResponding}
          campaignName={effectiveCampaignName}
          conversationId={conversationId}
          onEnsureConversation={ensureConversation}
          onVideoReady={(url, script, thumbnail) => {
            setMessages((prev) => [
              ...prev,
              {
                id: `msg-video-${Date.now()}`,
                role: 'assistant',
                content: script ? `Your video ad:\n\n_“${script}”_` : 'Your video ad is ready.',
                createdAt: new Date().toISOString(),
                videoUrl: url,
                videoThumbnail: thumbnail,
                agentRole: 'script_generator',
                agentRoleName: 'Video Script Generator',
                agentRoleAvatar: 'film',
              },
            ]);
          }}
          conversations={conversations.map(c => ({
            id: c.id,
            title: c.title || 'Untitled',
            campaignName: c.campaignName || null,
            messageCount: c.messageCount || 0,
          }))}
          onStop={async () => {
            // 1. Abort the SSE fetch stream immediately
            if (abortControllerRef.current) {
              abortControllerRef.current.abort();
              abortControllerRef.current = null;
            }
            // 2. Kill the backend subprocess
            if (conversationId) {
              try { await stopAgentTask(conversationId); } catch {}
            }
            // 3. Reset UI state
            setIsResponding(false);
            // 4. Mark any pending tool calls as stopped
            setMessages((prev) => prev.map((m) => ({
              ...m,
              toolCalls: m.toolCalls?.map((tc) => tc.status === 'pending' ? { ...tc, status: 'error' as const } : tc),
            })));
          }}
        />
        </div>
      </div>
    </div>
  );
}
