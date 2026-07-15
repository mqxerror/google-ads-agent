/**
 * HomeChatDock — summoned chat for the home page (Epic 13, Story 13.5).
 *
 * Design brief §2: on the HOME page the chat is NOT a parked right rail.
 * A floating button (bottom-right) and ⌘K open the EXISTING ChatPanel as
 * an overlay drawer; closing dismisses it. Campaign pages keep their rail
 * (this component is only mounted on home).
 *
 * We REUSE ChatPanel unchanged — it's rendered inside a fixed right-side
 * drawer with a scrim. ChatPanel owns its own width/resize/full-screen;
 * the drawer just controls mount + visibility. ⌘K toggles the drawer here
 * (on home, CommandPalette's ⌘K is disabled so the two don't fight).
 */

import { useState, useEffect, useCallback } from 'react';
import { MessageSquare, X } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
import ChatPanel from './ChatPanel';

export default function HomeChatDock() {
  const [open, setOpen] = useState(false);
  const { chatPanelCollapsed, toggleChatPanel } = useAppStore();

  const openDrawer = useCallback(() => {
    // The drawer should always open with the chat visible — if the user
    // previously collapsed the rail (persisted), expand it so the drawer
    // isn't just ChatPanel's thin reopener strip.
    if (chatPanelCollapsed) toggleChatPanel();
    setOpen(true);
  }, [chatPanelCollapsed, toggleChatPanel]);

  // ⌘K / Ctrl-K summons the chat on the home page.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (open) {
          setOpen(false);
        } else {
          openDrawer();
        }
      }
      if (e.key === 'Escape' && open) setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, openDrawer]);

  // Programmatic summon — e.g. the fix-list strip's "Review in chat" opens the
  // drawer AND pre-seeds the composer with the finding. We open first, then
  // hand the seed text to the (now-mounting) ChatPanel via its `chat:send`
  // listener on the next tick so it lands in the streaming path.
  useEffect(() => {
    const handler = (e: Event) => {
      const seed = (e as CustomEvent<{ text?: string; roleId?: string; model?: string }>).detail;
      openDrawer();
      if (seed?.text) {
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent('chat:send', { detail: seed }));
        }, 120);
      }
    };
    window.addEventListener('home-chat:open', handler as EventListener);
    return () => window.removeEventListener('home-chat:open', handler as EventListener);
  }, [openDrawer]);

  return (
    <>
      {/* Floating summon button — hidden while the drawer is open. */}
      {!open && (
        <button
          onClick={openDrawer}
          className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-on-accent transition-transform hover:scale-105"
          style={{ boxShadow: 'var(--shadow-elevated)' }}
          title="Chat with the agent (⌘K)"
          aria-label="Open chat"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
      )}

      {/* Drawer + scrim */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="relative flex h-full">
            {/* Close affordance sits just left of the panel edge. */}
            <button
              onClick={() => setOpen(false)}
              className="absolute -left-10 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-card text-muted-foreground transition-colors hover:text-foreground"
              style={{ boxShadow: 'var(--shadow-resting)' }}
              title="Close chat (Esc)"
              aria-label="Close chat"
            >
              <X className="h-4 w-4" />
            </button>
            <ChatPanel />
          </div>
        </div>
      )}
    </>
  );
}
