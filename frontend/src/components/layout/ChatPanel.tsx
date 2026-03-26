import { useState, useRef, useEffect, useCallback } from 'react';
import { GripVertical, Maximize2, Minimize2, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/stores/appStore';
import { useQueryClient } from '@tanstack/react-query';
import ContextBadge from '@/components/chat/ContextBadge';
import ChatMessageComponent from '@/components/chat/ChatMessage';
import ChatInput, { type ModelId } from '@/components/chat/ChatInput';
import type { ChatMessage, ToolCall, Campaign } from '@/types';

const ACCOUNT_ID = '7178239091';

export default function ChatPanel() {
  const { chatPanelWidth, setChatPanelWidth, selectedCampaignId } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isResponding, setIsResponding] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const resizingRef = useRef(false);
  const queryClient = useQueryClient();

  const campaigns = queryClient.getQueryData<Campaign[]>(['campaigns', ACCOUNT_ID]) ?? [];
  const campaign = campaigns.find((c) => c.id === selectedCampaignId);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Create conversation on first message if needed
  const ensureConversation = useCallback(async (): Promise<string> => {
    if (conversationId) return conversationId;
    const res = await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_id: ACCOUNT_ID,
        campaign_id: selectedCampaignId,
        campaign_name: campaign?.name,
        title: 'Chat session',
      }),
    });
    const conv = await res.json();
    setConversationId(conv.id);
    return conv.id;
  }, [conversationId, selectedCampaignId, campaign?.name]);

  // Reset conversation when campaign changes
  useEffect(() => {
    setConversationId(null);
    setMessages([]);
  }, [selectedCampaignId]);

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
        const newWidth = Math.max(300, Math.min(700, startWidth + delta));
        setChatPanelWidth(newWidth);
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

  const handleSend = useCallback(
    async (text: string, model: ModelId = 'sonnet') => {
      // Add user message
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

        // Send message and stream response
        const res = await fetch(`/api/conversations/${convId}/message`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: text,
            account_id: ACCOUNT_ID,
            campaign_id: selectedCampaignId,
            model,
          }),
        });

        if (!res.ok) {
          throw new Error(`API error ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let assistantText = '';
        const toolCalls: ToolCall[] = [];
        const assistantMsgId = `msg-${Date.now()}-resp`;

        // Add placeholder assistant message
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content: '',
            toolCalls: [],
            createdAt: new Date().toISOString(),
          },
        ]);

        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE lines
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6).trim();
            if (!dataStr || dataStr === '[DONE]') continue;

            try {
              const event = JSON.parse(dataStr);

              if (event.type === 'text') {
                assistantText += event.content || '';
                // Update the assistant message with accumulated text
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, content: assistantText, toolCalls: [...toolCalls] }
                      : m
                  )
                );
              } else if (event.type === 'tool_call') {
                toolCalls.push({
                  id: event.id || `tc-${Date.now()}`,
                  source: event.source || 'google-ads',
                  name: event.name || 'unknown',
                  input: event.input || {},
                  status: 'pending',
                });
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, toolCalls: [...toolCalls] }
                      : m
                  )
                );
              } else if (event.type === 'tool_result') {
                // Update the matching tool call with result
                const tcIdx = toolCalls.findIndex((tc) => tc.id === event.id);
                if (tcIdx >= 0) {
                  toolCalls[tcIdx] = {
                    ...toolCalls[tcIdx],
                    output: typeof event.output === 'string'
                      ? { result: event.output }
                      : event.output || {},
                    status: event.status === 'error' ? 'error' : 'success',
                  };
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.id === assistantMsgId
                        ? { ...m, toolCalls: [...toolCalls] }
                        : m
                    )
                  );
                }
              } else if (event.type === 'done') {
                // Refresh campaign data after agent actions
                queryClient.invalidateQueries({ queryKey: ['campaigns'] });
              } else if (event.type === 'error') {
                assistantText += `\n\n**Error:** ${event.message}`;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMsgId
                      ? { ...m, content: assistantText }
                      : m
                  )
                );
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      } catch (err) {
        // Add error message
        setMessages((prev) => [
          ...prev,
          {
            id: `msg-${Date.now()}-err`,
            role: 'assistant',
            content: `**Connection error:** ${err instanceof Error ? err.message : 'Unknown error'}. Make sure the backend is running.`,
            createdAt: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsResponding(false);
      }
    },
    [ensureConversation, selectedCampaignId, queryClient]
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
        className={cn(
          'w-1.5 cursor-col-resize hover:bg-primary/30 transition-colors flex items-center justify-center',
          resizingRef.current && 'bg-primary/30'
        )}
      >
        <GripVertical className="h-4 w-4 text-muted-foreground opacity-0 hover:opacity-100 transition-opacity" />
      </div>

      {/* Chat content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Context badge + toolbar */}
        <div className="border-b border-border flex items-center justify-between pr-2">
          <ContextBadge
            campaignName={campaign?.name ?? null}
            guidelinesLoaded={true}
          />
          <div className="flex items-center gap-1">
            {messages.length > 0 && (
              <button
                onClick={() => { setMessages([]); setConversationId(null); }}
                className="p-1 text-muted-foreground hover:text-foreground transition-colors"
                title="Clear chat"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 text-muted-foreground hover:text-foreground transition-colors"
              title={expanded ? 'Collapse chat' : 'Expand chat'}
            >
              {expanded ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>

        {/* Messages — scrollable */}
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

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={isResponding} />
      </div>
    </div>
  );
}
