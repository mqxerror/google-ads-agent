/**
 * Direct chat message API — bypasses React state entirely.
 *
 * Solves the stale closure race condition where CustomEvent('chat:send')
 * fires before React state updates propagate to ensureConversation().
 *
 * Usage: Builder/Research/Templates call sendChatMessage() directly,
 * then dispatch 'chat:display' to tell ChatPanel to show the conversation.
 */

import { createConversation } from './api';

export interface SendChatParams {
  text: string;
  accountId: string;
  campaignId?: string;
  campaignName?: string;
  model?: string;
  roleId?: string;
  attachments?: Array<{ filename: string; path: string; is_image: boolean }>;
  conversationId?: string;  // Reuse existing, or omit to create new
  title?: string;
}

export interface SendChatResult {
  conversationId: string;
  response: Response;
}

/**
 * Create conversation (if needed) AND send message in one atomic operation.
 * No React state involved — immune to stale closures and race conditions.
 */
export async function sendChatMessage(params: SendChatParams): Promise<SendChatResult> {
  // 1. Create or reuse conversation
  let convId = params.conversationId;
  if (!convId) {
    const conv = await createConversation({
      account_id: params.accountId,
      campaign_id: params.campaignId,
      campaign_name: params.campaignName,
      title: params.title || 'New chat',
    });
    convId = conv.id;
  }

  // 2. Send message immediately — no waiting for React
  const response = await fetch(`/api/conversations/${convId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: params.text,
      account_id: params.accountId,
      campaign_id: params.campaignId,
      model: params.model || 'fable',
      active_role: params.roleId || null,
      attachments: params.attachments || [],
    }),
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }

  return { conversationId: convId, response };
}

/**
 * Tell ChatPanel to display a specific conversation and stream its response.
 */
export function displayConversation(conversationId: string) {
  window.dispatchEvent(new CustomEvent('chat:display', {
    detail: { conversationId },
  }));
}
