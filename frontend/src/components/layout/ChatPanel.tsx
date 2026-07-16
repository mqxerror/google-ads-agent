import { useState, useRef, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { GripVertical, Maximize2, Minimize2, Trash2, Plus, Search, MessageSquare, ChevronLeft, Download, Expand, Shrink, PanelRightClose, Hash, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { fetchConversations, createConversation, fetchConversation, deleteConversation, fetchMessages, searchConversations, stopAgentTask, startTurn, streamTurn, stopTurn, stopTurnCall } from '@/lib/api';
import type { OrchestrationEvent } from '@/types/orchestration';
import ContextBadge, { type ContextMetaData } from '@/components/chat/ContextBadge';
import ChatMessageComponent from '@/components/chat/ChatMessage';
import AgentAvatar from '@/components/chat/AgentAvatar';
import ChatInput, { type ModelId, type Attachment } from '@/components/chat/ChatInput';
import MemoryPanel from '@/components/chat/MemoryPanel';
import { Input } from '@/components/ui/input';
import type { ChatMessage, ToolCall, Campaign } from '@/types';

// FIX 3 — window inside which an IDENTICAL trimmed message is treated as an
// accidental duplicate (queue+lag re-fire) and dropped. A DIFFERENT message is
// never affected; the same text after this window is a legit repeat and sends.
const DEDUP_WINDOW_MS = 10_000;

export default function ChatPanel() {
  const { chatPanelWidth, setChatPanelWidth, selectedCampaignId, chatPanelCollapsed, toggleChatPanel } = useAppStore();
  const navigate = useNavigate();
  // URL is now the authoritative source for which conversation is active.
  // `useParams` reads `/c/:conversationId` — null when the user is on a
  // non-chat route (e.g. dashboard, setup). sessionStorage is kept as a
  // fallback for *non-chat-route* loads (open `/` directly and the last
  // chat resumes) but the URL always wins when both are present.
  const { conversationId: urlConversationId } = useParams<{ conversationId?: string }>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isResponding, setIsResponding] = useState(false);
  // v2 orchestration: accumulated turn-stream events + terminal flags, keyed by
  // turn_id. ChatMessage reads these to render the OrchestrationLedger for a
  // bubble whose `turnId` is set. Empty for every direct-mode turn (toggle OFF),
  // so direct rendering is byte-identical to today.
  const [turnEvents, setTurnEvents] = useState<Record<string, OrchestrationEvent[]>>({});
  const [completeTurns, setCompleteTurns] = useState<Record<string, boolean>>({});
  // The conversation+turn currently streaming, so per-specialist stop (story
  // 3.4/2.6) can route to the right turn. Cleared on terminal / switch.
  const activeTurnRef = useRef<{ conversationId: string; turnId: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [conversationId, setConversationIdRaw] = useState<string | null>(() => {
    // URL > sessionStorage on first mount.
    if (urlConversationId) return urlConversationId;
    const saved = sessionStorage.getItem('activeConversationId');
    return saved || null;
  });
  const setConversationId = useCallback((id: string | null) => {
    if (id) sessionStorage.setItem('activeConversationId', id);
    else sessionStorage.removeItem('activeConversationId');
    setConversationIdRaw(id);
    // Mirror to the URL so refresh / browser-back / share-by-link all
    // resolve to the right chat. `replace:true` keeps history from
    // ballooning when the user clicks through several conversations.
    // Skip the push when the user is on a non-chat route (e.g.
    // `/studio` — Studio has its own URL ownership). Without this
    // guard the chat panel's mount-time setConversationId hijacks the
    // URL back to `/c/<id>`, breaking deep-links to other surfaces.
    const path = window.location.pathname;
    const onChatRoute = path === '/' || path.startsWith('/c/');
    if (id && onChatRoute) {
      if (path !== `/c/${id}`) navigate(`/c/${id}`, { replace: true });
    } else if (!id && path.startsWith('/c/')) {
      navigate('/', { replace: true });
    }
  }, [navigate]);

  // If the user pastes a `/c/:id` URL while a different chat is active,
  // the URL wins — sync the in-memory id to it.
  useEffect(() => {
    if (urlConversationId && urlConversationId !== conversationId) {
      setConversationIdRaw(urlConversationId);
      sessionStorage.setItem('activeConversationId', urlConversationId);
    }
  }, [urlConversationId, conversationId]);

  // Copy-to-clipboard for the visible conversation id.
  const handleCopyId = useCallback(async () => {
    if (!conversationId) return;
    try {
      await navigator.clipboard.writeText(conversationId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // navigator.clipboard fails in insecure contexts — fallback would
      // need a hidden textarea; not worth the code for localhost dev.
    }
  }, [conversationId]);
  const [expanded, setExpanded] = useState(false);
  const [fullScreen, setFullScreen] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [contextMeta, setContextMeta] = useState<ContextMetaData | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Identity anchor for async writers. `conversationId` is live state that
  // async closures capture stale; this ref always holds the CURRENTLY-displayed
  // conversation. Every stream writer captures its own `convId` at start and
  // bails on any setMessages when conversationIdRef.current !== convId — killing
  // the F7 cross-campaign bleed where a stale writer wrote into the new window.
  const conversationIdRef = useRef<string | null>(conversationId);
  // chat:display poller timers hoisted to refs so a conversation/campaign switch
  // can tear them down (the interval otherwise fires every 2s for up to 5 min,
  // overwriting whatever chat is now open).
  const chatDisplayPollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chatDisplaySafetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queryClient = useQueryClient();

  // FIX 3 — duplicate-send guard. The last text we accepted for send + when.
  // An identical trimmed string re-submitted within DEDUP_WINDOW_MS while the
  // agent is busy (in-flight OR queued) is dropped — kills the double-bubble /
  // double-turn cost from queue+lag re-fires. A DIFFERENT message, or the same
  // text after the window, is never blocked (a legit repeat still works).
  const lastSendRef = useRef<{ text: string; ts: number } | null>(null);
  const [dupHint, setDupHint] = useState(false);
  const dupHintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // FIX 2c — optimistic stop. Flip true the instant Stop is clicked so the
  // button shows a spinner + disables without waiting for the stopTurn
  // round-trip; reset whenever a fresh turn begins.
  const [stopping, setStopping] = useState(false);

  // Keep the identity anchor in sync with the live conversation state.
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  // Tear down the chat:display poller (both timers). Called on any
  // conversation/campaign switch so a stale poller can't overwrite the new
  // window. useCallback so effects that depend on it have a stable reference.
  const tearDownChatDisplayPoller = useCallback(() => {
    if (chatDisplayPollTimerRef.current) {
      clearInterval(chatDisplayPollTimerRef.current);
      chatDisplayPollTimerRef.current = null;
    }
    if (chatDisplaySafetyTimerRef.current) {
      clearTimeout(chatDisplaySafetyTimerRef.current);
      chatDisplaySafetyTimerRef.current = null;
    }
  }, []);
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
    // Identity anchor: this reader may only touch shared state while the
    // displayed conversation is still the one it reconnected to. Guards every
    // setMessages / setIsResponding below (in addition to the `cancelled` flag,
    // which only catches switches between chunks).
    const convId = conversationId;
    const isCurrent = () => !cancelled && conversationIdRef.current === convId;

    (async () => {
      try {
        const res = await fetch(`/api/conversations/${conversationId}/agent/status`);
        const status = await res.json();
        if (status.running && isCurrent()) {
          setIsResponding(true);
          // Reconnect to the stream from where the buffer is
          const streamRes = await fetch(`/api/conversations/${conversationId}/agent/stream?cursor=0`);
          const reader = streamRes.body?.getReader();
          if (!reader) return;

          const decoder = new TextDecoder();
          const assistantMsgId = `msg-${Date.now()}-reconnect`;
          let assistantText = '';

          // Add a placeholder message for the reconnected stream
          if (isCurrent()) setMessages((prev) => {
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
                  if (isCurrent()) setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                } else if (event.type === 'routing') {
                  if (isCurrent()) setMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, agentRole: event.role_id, agentRoleName: event.role_name, agentRoleAvatar: event.role_avatar } : m));
                } else if (event.type === 'done' || event.type === 'error') {
                  if (isCurrent()) setIsResponding(false);
                }
              } catch {}
            }
          }
          if (isCurrent()) setIsResponding(false);
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
      // THE CORE BLEED FIX: kill the in-flight send reader and the chat:display
      // poller BEFORE clearing state, so neither can write into the new
      // campaign's window. Without this the old reader's finally/error paths and
      // the 2s poller keep mutating the now-foreign `messages`.
      abortControllerRef.current?.abort();
      tearDownChatDisplayPoller();
      setConversationId(null);
      setMessages([]);
      setActiveConvCampaign(null);
    }
  }, [selectedCampaignId, setConversationId, tearDownChatDisplayPoller]);

  // On ANY conversation switch, abort the previous send reader and tear down the
  // poller. React runs the previous effect's cleanup (for the OLD conversationId)
  // before the new effect body, so keying on conversationId safely targets the
  // OLD controller/timers — a just-created controller for the new send is never
  // touched. Complements the campaign-switch effect (which covers sidebar
  // switches); this covers conversation-only switches (history click, Builder
  // handoff, mismatch-drop).
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      tearDownChatDisplayPoller();
    };
  }, [conversationId, tearDownChatDisplayPoller]);

  // FIX 3 — clear the dup-hint timer on unmount so it can't fire into a torn-down tree.
  useEffect(() => {
    return () => {
      if (dupHintTimerRef.current) clearTimeout(dupHintTimerRef.current);
    };
  }, []);

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
  const [messageQueue, setMessageQueue] = useState<Array<{text: string, model: ModelId, roleId?: string, attachments?: Attachment[], orchestrate?: boolean}>>([]);

  // Drain queue when agent finishes
  useEffect(() => {
    if (!isResponding && messageQueue.length > 0) {
      const next = messageQueue[0];
      setMessageQueue((prev) => prev.slice(1));
      // Remove pending flag from the queued message
      setMessages((prev) => prev.map((m) => m.isPending ? { ...m, isPending: false } : m));
      actualSend(next.text, next.model, next.roleId, next.attachments, next.orchestrate);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isResponding, messageQueue.length]);

  // Brief "already queued" hint (FIX 3) — auto-clears after a short beat.
  const flashDupHint = useCallback(() => {
    setDupHint(true);
    if (dupHintTimerRef.current) clearTimeout(dupHintTimerRef.current);
    dupHintTimerRef.current = setTimeout(() => setDupHint(false), 2500);
  }, []);

  // Send message (queues if agent is busy)
  const handleSend = useCallback(
    (text: string, model: ModelId = 'fable', roleId?: string, attachments?: Attachment[], orchestrate?: boolean) => {
      const trimmed = text.trim();

      // FIX 3 — duplicate-send guard. Drop an IDENTICAL text re-submitted within
      // DEDUP_WINDOW_MS while a send is in-flight OR queued (the queue+lag
      // double-fire that produced two identical bubbles + double turn cost).
      // A DIFFERENT message is never blocked; the same text after the window is
      // a legit repeat and goes through.
      const last = lastSendRef.current;
      const busy = isResponding || messageQueue.length > 0;
      if (
        busy &&
        last &&
        last.text === trimmed &&
        Date.now() - last.ts < DEDUP_WINDOW_MS
      ) {
        flashDupHint();
        return;
      }
      lastSendRef.current = { text: trimmed, ts: Date.now() };

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
        setMessageQueue((prev) => [...prev, { text, model, roleId, attachments, orchestrate }]);
        return;
      }
      actualSend(text, model, roleId, attachments, orchestrate);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isResponding, messageQueue.length, flashDupHint],
  );

  // v2 orchestrated send — the two-step flow (story 3.1/3.2). Separate from the
  // direct path so `actualSend`'s byte-identical streaming logic is untouched.
  // Same identity-guard discipline: every state write checks conversationIdRef
  // against the convId this send targeted, so a stale run can't bleed into
  // another campaign's window (F7 invariant, generalized onto the turn transport).
  const orchestratedSend = useCallback(
    async (text: string, model: ModelId, roleId?: string, attachments?: Attachment[]) => {
      let convId: string | null = null;
      const guardedSetMessages: typeof setMessages = (updater) => {
        if (conversationIdRef.current === convId) setMessages(updater);
      };
      const assistantMsgId = `msg-${Date.now()}-orch`;
      let directorText = '';
      let turnId: string | null = null;

      // FIX 2a — batched event ingestion. `onEvent` pushes into this buffer
      // (cheap, no re-render) instead of calling setTurnEvents per event; a
      // ~90ms interval drains the whole buffer into ONE setTurnEvents state
      // update per tick. A turn's claim-gate alone emits ~66 events and
      // token-level text_deltas add many more, so per-event state writes made
      // the ledger re-render on every token. The identity guards + the
      // final_chunk→bubble path stay per-event (below); only the ledger's
      // turnEvents accumulation is batched.
      let pendingEvents: OrchestrationEvent[] = [];
      let flushTimer: ReturnType<typeof setInterval> | null = null;
      const flushPending = () => {
        if (pendingEvents.length === 0) return;
        if (conversationIdRef.current !== convId) { pendingEvents = []; return; }
        const batch = pendingEvents;
        pendingEvents = [];
        const tid = turnId;
        if (!tid) return;
        setTurnEvents((prev) => ({ ...prev, [tid]: [...(prev[tid] ?? []), ...batch] }));
      };
      const stopFlushTimer = () => {
        if (flushTimer !== null) { clearInterval(flushTimer); flushTimer = null; }
      };

      try {
        convId = await ensureConversation();
        const controller = new AbortController();
        abortControllerRef.current = controller;

        // Step 1 — POST /message with orchestrate:true → {turn_id} (fast JSON,
        // NOT a stream). backend field: orchestrate.
        const { turn_id } = await startTurn(
          convId,
          {
            content: text,
            account_id: ACCOUNT_ID,
            campaign_id: selectedCampaignId,
            campaign_name: campaign?.name,
            model,
            active_role: roleId || null,
            attachments: attachments || [],
          },
          controller.signal,
        );
        turnId = turn_id;
        activeTurnRef.current = { conversationId: convId, turnId };

        // Seed the assistant bubble carrying this turn_id — ChatMessage renders
        // the ledger from `turnEvents[turnId]` and the Director prose from its
        // own `content`.
        guardedSetMessages((prev) => [
          ...prev,
          { id: assistantMsgId, role: 'assistant', content: '', toolCalls: [], createdAt: new Date().toISOString(), turnId: turn_id, agentRole: 'director' },
        ]);
        setTurnEvents((prev) => ({ ...prev, [turn_id]: [] }));
        setCompleteTurns((prev) => ({ ...prev, [turn_id]: false }));
        setStopping(false); // fresh turn — clear any prior optimistic-stop state

        // Start the batched drain now that turnId is known. ~90ms cadence keeps
        // the ledger visibly live without a state write per token.
        flushTimer = setInterval(flushPending, 90);

        const markComplete = () => {
          if (conversationIdRef.current === convId) {
            setCompleteTurns((prev) => ({ ...prev, [turn_id]: true }));
          }
        };

        // Step 2 — open the turn SSE from cursor 0, accumulate v2 events, stream
        // the Director's prose from final_chunk. Terminal events flip complete.
        await streamTurn(convId, turn_id, 0, {
          signal: controller.signal,
          onEvent: (ev) => {
            // Isolation guard (Epic-0): apply ONLY when the event's turn is the
            // one we subscribed to AND this conversation is still displayed.
            // Runs PER-EVENT, before buffering — a stale run never buffers.
            if (ev.turn_id && ev.turn_id !== turn_id) return;
            if (conversationIdRef.current !== convId) return;

            // FIX 2a: buffer the event for the ledger's replayable model — the
            // scheduled flush drains it into ONE setTurnEvents update per tick,
            // instead of a re-render per event.
            pendingEvents.push(ev);

            switch (ev.type) {
              case 'routing': {
                // Direct-mode turns can still arrive under a v2 envelope; keep
                // the role label honest if the backend routes one.
                const p = ev.payload as { role_id?: string; role_name?: string; role_avatar?: string } | undefined;
                if (p?.role_id) {
                  guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, agentRole: p.role_id, agentRoleName: p.role_name, agentRoleAvatar: p.role_avatar } : m));
                }
                break;
              }
              case 'context_meta':
                setContextMeta(ev.payload as unknown as ContextMetaData);
                break;
              case 'final_chunk': {
                const p = ev.payload as { text?: string; content?: string } | undefined;
                directorText += p?.text ?? p?.content ?? '';
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: directorText } : m));
                break;
              }
              case 'final_done': {
                const p = ev.payload as { message_id?: string } | undefined;
                // Adopt the persisted message id so a later history reload lines
                // the ledger up with the same bubble.
                if (p?.message_id) {
                  guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, id: p.message_id! } : m));
                }
                break;
              }
              case 'turn_done':
              case 'turn_error':
              case 'turn_stopped': {
                if (ev.type === 'turn_error') {
                  const p = ev.payload as { message?: string } | undefined;
                  directorText += `\n\n**Error:** ${p?.message ?? 'orchestration failed'}`;
                  guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: directorText } : m));
                } else if (ev.type === 'turn_stopped') {
                  directorText += '\n\n> Stopped by user.';
                  guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: directorText } : m));
                }
                // FIX 2a: terminal event — drain the buffer synchronously so the
                // ledger's final rows land in the SAME commit that marks the
                // turn complete (no lingering ~90ms gap before it collapses).
                stopFlushTimer();
                flushPending();
                markComplete();
                break;
              }
              default:
                // director_thought / memory_recall / verification / plan /
                // agent_* / conflict / decision / claim_gate → ledger only.
                break;
            }
          },
        });
        // Stream ended without an explicit terminal (rare) → drain any buffered
        // tail + mark complete so the ledger collapses honestly rather than
        // spinning forever.
        stopFlushTimer();
        flushPending();
        markComplete();
        if (conversationIdRef.current === convId) {
          queryClient.invalidateQueries({ queryKey: ['campaigns'] });
          refetchConversations();
          window.dispatchEvent(new Event('agent:done'));
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: directorText + '\n\n> Stopped by user.' } : m));
        } else {
          guardedSetMessages((prev) => [...prev, {
            id: `msg-${Date.now()}-err`, role: 'assistant',
            content: `**Connection error:** ${err instanceof Error ? err.message : 'Unknown error'}`,
            createdAt: new Date().toISOString(),
          }]);
        }
        if (turnId && conversationIdRef.current === convId) {
          setCompleteTurns((prev) => ({ ...prev, [turnId!]: true }));
        }
      } finally {
        // FIX 2a: tear down the drain timer + flush any buffered tail (covers
        // the abort/error paths where no terminal event ran). Guarded flush
        // no-ops if this conversation is no longer displayed.
        stopFlushTimer();
        flushPending();
        abortControllerRef.current = null;
        if (activeTurnRef.current?.turnId === turnId) activeTurnRef.current = null;
        if (conversationIdRef.current === convId) {
          setIsResponding(false);
          setStopping(false);
        }
      }
    },
    [ensureConversation, selectedCampaignId, ACCOUNT_ID, campaign?.name, queryClient, refetchConversations],
  );

  // Actual send (creates conversation, streams response)
  const actualSend = useCallback(
    async (text: string, model: ModelId = 'fable', roleId?: string, attachments?: Attachment[], orchestrate?: boolean) => {
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

      // ── v2 ORCHESTRATED PATH (toggle ON) ─────────────────────────────────
      // Two-step: POST /message → {turn_id}, then open the turn SSE and feed v2
      // events to the OrchestrationLedger. The Director's prose arrives as
      // `final_chunk` events, streamed into the assistant bubble exactly like
      // today's `text`. Terminal on final_done/turn_done/turn_stopped/turn_error.
      // The direct path below is NEVER touched when this branch runs.
      if (orchestrate) {
        await orchestratedSend(text, model, roleId, attachments);
        return;
      }

      // convId is captured in the outer scope so the catch/finally guards can
      // read it too. Guarded writes below only land while the displayed
      // conversation still equals the one this send targeted — killing the F7
      // bleed where a stale reader wrote into the new campaign's window.
      let convId: string | null = null;
      const guardedSetMessages: typeof setMessages = (updater) => {
        if (conversationIdRef.current === convId) setMessages(updater);
      };
      // Hoisted to the outer scope so the catch's AbortError path can append the
      // "stopped by user" note to the in-flight assistant bubble (previously these
      // were declared inside try, so the catch referenced out-of-scope names —
      // a TS2304 compile error that broke `tsc -b` / `vite build`).
      let assistantText = '';
      let assistantMsgId = '';
      try {
        convId = await ensureConversation();
        const controller = new AbortController();
        abortControllerRef.current = controller;
        // ?stream=1 restores the pre-v2 legacy streaming contract: the backend
        // now defaults to JSON `{turn_id}` (detached turn) and only emits the
        // legacy StreamingResponse when this flag is present. Without it the
        // reader below gets a ~30-byte JSON body, no frames, and spins forever.
        const res = await fetch(`/api/conversations/${convId}/message?stream=1`, {
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
        assistantText = '';
        const toolCalls: ToolCall[] = [];
        assistantMsgId = `msg-${Date.now()}-resp`;
        let resolvedRole = { id: '', name: '', avatar: '' };

        guardedSetMessages((prev) => [
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
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, agentRole: resolvedRole.id, agentRoleName: resolvedRole.name, agentRoleAvatar: resolvedRole.avatar } : m));
              } else if (event.type === 'text') {
                assistantText += event.content || '';
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText, toolCalls: [...toolCalls] } : m));
              } else if (event.type === 'tool_call') {
                toolCalls.push({ id: event.id || `tc-${Date.now()}`, source: event.source || 'google-ads', name: event.name || 'unknown', input: event.input || {}, status: 'pending' });
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, toolCalls: [...toolCalls] } : m));
              } else if (event.type === 'tool_result') {
                const tcIdx = toolCalls.findIndex((tc) => tc.id === event.id);
                if (tcIdx >= 0) {
                  toolCalls[tcIdx] = { ...toolCalls[tcIdx], output: typeof event.output === 'string' ? { result: event.output } : event.output || {}, status: event.status === 'error' ? 'error' : 'success' };
                  guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, toolCalls: [...toolCalls] } : m));
                }
              } else if (event.type === 'resumed') {
                // Picked up a previously stopped session — full prior context restored
                assistantText += `> ↩︎ *Resumed the previous session — continuing the task with full context.*\n\n`;
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText, toolCalls: [...toolCalls] } : m));
              } else if (event.type === 'continuation') {
                // Agent auto-continuing after max-turns — show subtle indicator
                assistantText += `\n\n---\n*Continuing... (${event.accumulated_turns} turns)*\n\n`;
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText, toolCalls: [...toolCalls] } : m));
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
                  guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                }
                queryClient.invalidateQueries({ queryKey: ['campaigns'] });
                refetchConversations();
                // Notify Campaign Builder and other listeners that the agent is done
                window.dispatchEvent(new Event('agent:done'));
              } else if (event.type === 'error') {
                assistantText += `\n\n**Error:** ${event.message}`;
                guardedSetMessages((prev) => prev.map((m) => m.id === assistantMsgId ? { ...m, content: assistantText } : m));
                window.dispatchEvent(new Event('agent:done'));
              }
            } catch {}
          }
        }
      } catch (err) {
        // AbortError is expected when user clicks Stop — don't show as error
        if (err instanceof DOMException && err.name === 'AbortError') {
          guardedSetMessages((prev) => prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: assistantText + '\n\n> Agent stopped by user.' }
              : m
          ));
        } else {
          guardedSetMessages((prev) => [...prev, {
            id: `msg-${Date.now()}-err`, role: 'assistant',
            content: `**Connection error:** ${err instanceof Error ? err.message : 'Unknown error'}`,
            createdAt: new Date().toISOString(),
          }]);
        }
      } finally {
        // Clearing the controller is always safe — it belongs to this send.
        abortControllerRef.current = null;
        // But only flip isResponding / sweep tool calls for the STILL-DISPLAYED
        // conversation. If the user switched away, this send's finally must not
        // yank isResponding or mutate the now-foreign window.
        if (conversationIdRef.current === convId) {
          setIsResponding(false);
          // Sweep: any tool calls still 'pending' when the stream ends are stuck/interrupted.
          setMessages((prev) => prev.map((m) => ({
            ...m,
            toolCalls: m.toolCalls?.map((tc) => tc.status === 'pending' ? { ...tc, status: 'error' as const } : tc),
          })));
        }
      }
    },
    [ensureConversation, selectedCampaignId, ACCOUNT_ID, queryClient, refetchConversations, orchestratedSend]
  );

  // Listen for external "chat:send" events (from Landing Page tab, Builder, etc.)
  const handleSendRef = useRef(handleSend);
  useEffect(() => { handleSendRef.current = handleSend; }, [handleSend]);

  // Listen for 'chat:display' — switch to a conversation and poll for updates
  useEffect(() => {
    const displayHandler = (e: Event) => {
      const { conversationId: convId } = (e as CustomEvent).detail || {};
      if (convId) {
        setConversationId(convId);
        setMessages([]);
        setIsResponding(true);
        fetchMessages(convId).then((msgs) => {
          // Only apply the initial load if this handoff's conversation is still
          // the displayed one.
          if (conversationIdRef.current === convId) setMessages(msgs);
        }).catch(() => {});
        refetchConversations();
        // Poll for new messages while agent is responding. Tear down any prior
        // poller first (timers live in refs so a later switch can also kill it).
        tearDownChatDisplayPoller();
        let unchangedCount = 0;
        let lastMsgCount = 0;
        chatDisplayPollTimerRef.current = setInterval(async () => {
          try {
            const msgs = await fetchMessages(convId);
            // Guard: this poller belongs to `convId`. If the user switched away,
            // don't overwrite the now-displayed conversation (the F7 worst-case
            // bleeder — every 2s for up to 5 min).
            if (conversationIdRef.current !== convId) return;
            setMessages(msgs);
            if (msgs.length === lastMsgCount) {
              unchangedCount++;
              // If no new messages for 6 seconds after agent has responded, stop polling
              if (unchangedCount >= 3 && msgs.length > 1 && msgs[msgs.length - 1]?.role === 'assistant') {
                tearDownChatDisplayPoller();
                if (conversationIdRef.current === convId) setIsResponding(false);
                window.dispatchEvent(new Event('agent:done'));
              }
            } else {
              unchangedCount = 0;
              lastMsgCount = msgs.length;
            }
          } catch {}
        }, 2000);
        // Safety: stop after 5 min
        chatDisplaySafetyTimerRef.current = setTimeout(() => {
          tearDownChatDisplayPoller();
          if (conversationIdRef.current === convId) setIsResponding(false);
        }, 300000);
      }
    };
    // chat:send — send a message via the normal streaming path
    const sendHandler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.text) {
        handleSendRef.current(detail.text, detail.model || 'fable', detail.roleId);
      }
    };
    window.addEventListener('chat:display', displayHandler);
    window.addEventListener('chat:send', sendHandler);
    return () => {
      window.removeEventListener('chat:display', displayHandler);
      window.removeEventListener('chat:send', sendHandler);
      // Kill the poller if this effect unmounts/re-runs so no orphaned timer
      // keeps polling into a stale window.
      tearDownChatDisplayPoller();
    };
  }, [setConversationId, refetchConversations, tearDownChatDisplayPoller]);

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
      <div className="w-8 bg-surface-2 border-l border-border flex flex-col items-center py-2 shrink-0">
        <button
          onClick={toggleChatPanel}
          className="p-1 text-muted-foreground hover:text-text hover:bg-surface-3 rounded transition-colors"
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
        'bg-surface border-l border-border flex shrink-0 overflow-hidden',
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
          className={cn('w-1.5 cursor-col-resize hover:bg-accent/20 transition-colors flex items-center justify-center', resizingRef.current && 'bg-accent/20')}
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
            {/* Conversation id chip — short prefix, click-to-copy, full
                id in the tooltip. Hidden when no chat is active. Surfacing
                the id was the missing affordance for sharing/debugging
                a specific thread; the same id is now in the URL too. */}
            {conversationId && (
              <button
                onClick={handleCopyId}
                className="px-1.5 py-0.5 flex items-center gap-1 text-[10px] font-mono text-muted-foreground hover:text-foreground hover:bg-secondary/50 rounded transition-colors"
                title={copied ? 'Copied' : `Copy conversation id: ${conversationId}`}
              >
                {copied ? <Check className="h-3 w-3 text-success" /> : <Hash className="h-3 w-3" />}
                <span>{conversationId.slice(0, 8)}</span>
              </button>
            )}
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
            {messages.map((msg, idx) => (
              <ChatMessageComponent
                key={msg.id}
                message={msg}
                isStreaming={
                  isResponding &&
                  idx === messages.length - 1 &&
                  msg.role === 'assistant'
                }
                conversationId={conversationId ?? undefined}
                // v2: feed the live turn's accumulated events + terminal flag +
                // per-specialist stop. Only the currently-active turn is "live"
                // (onStopCall wired); history bubbles lazily fetch /events and
                // get no live events → the ledger hides per-row stops.
                turnEvents={msg.turnId ? turnEvents[msg.turnId] : undefined}
                turnComplete={msg.turnId ? completeTurns[msg.turnId] : undefined}
                onStopCall={
                  msg.turnId &&
                  activeTurnRef.current?.turnId === msg.turnId &&
                  conversationId
                    ? (callId) => { stopTurnCall(conversationId, msg.turnId!, callId).catch(() => {}); }
                    : undefined
                }
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
              <div className="flex items-center gap-3 px-3 py-2">
                <AgentAvatar size="sm" showStatus isWorking />
                <span className="text-xs italic text-muted-foreground">
                  thinking
                  <span className="studio-caret ml-0.5">▍</span>
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Memory Panel — hidden in full-screen so the chat dominates the view.
            Reads the conversation's actual campaign (effectiveCampaignId), not
            the sidebar's, so the pinned facts shown here are exactly the ones
            the agent loaded. Previously this keyed off selectedCampaignId, so
            it would happily show Panama's pinned facts while the agent was
            operating on MapleRoots. */}
        {!fullScreen && (
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
          stopping={stopping}
          dupHint={dupHint}
          onStop={async () => {
            // FIX 2c — optimistic stop: reflect the click in the UI (spinner +
            // disabled) BEFORE the stopTurn round-trip. Reset happens when the
            // turn actually terminates (orchestratedSend finally) or below.
            setStopping(true);
            // 1. Abort the SSE fetch stream immediately
            if (abortControllerRef.current) {
              abortControllerRef.current.abort();
              abortControllerRef.current = null;
            }
            // 2. Kill the backend run. For a live v2 turn (story 3.4) route to
            //    the per-turn stop, which reaps the whole turn's process group +
            //    emits turn_stopped. For direct-mode turns the legacy conversation
            //    stop still applies (backend 1.5 aliases it to the active turn).
            const active = activeTurnRef.current;
            if (active && conversationId && active.conversationId === conversationId) {
              try { await stopTurn(conversationId, active.turnId); } catch {}
              setCompleteTurns((prev) => ({ ...prev, [active.turnId]: true }));
              activeTurnRef.current = null;
            } else if (conversationId) {
              try { await stopAgentTask(conversationId); } catch {}
            }
            // 3. No auto-resurrection (spec 0.1c). A message queued before the
            //    stop would otherwise auto-fire the moment isResponding flips
            //    false (drain effect :420-429) and resume the just-killed
            //    session. Clear the queue and strip pending user bubbles so
            //    nothing drains. React batches these with setIsResponding(false)
            //    below, so the drain effect sees messageQueue.length === 0 → no
            //    drain. Frontend-only: an explicit user "continue" still
            //    resumes; we only kill the AUTOMATIC resurrection.
            setMessageQueue([]);
            // 4. Reset UI state (clear the optimistic-stop flag now the stop has
            //    landed — covers the direct-mode path where orchestratedSend's
            //    finally doesn't run).
            setIsResponding(false);
            setStopping(false);
            // 5. Strip pending (queued) messages + mark any pending tool calls as stopped
            setMessages((prev) => prev
              .filter((m) => !m.isPending)
              .map((m) => ({
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
