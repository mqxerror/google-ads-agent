import { useEffect, useRef } from 'react';
import { useNavigate, type NavigateFunction } from 'react-router-dom';
import { useAppStore } from '@/stores/appStore';

/**
 * useKeyboardNav (Dashboard v2.1, C3) — Gmail-style two-key chords for the
 * three navigation moves plus Esc-to-home.
 *
 *   g h  → go home           (no campaign selected, every takeover panel off)
 *   g c  → open last campaign (no-op when there is no last campaign)
 *   g p  → Plans             (open last campaign if needed, then its Plans tab)
 *   Esc  → go home           (only on a campaign page, no modal/input focused)
 *
 * SAFETY (the whole reason single keys are NOT bound): the handler ignores
 * every chord when the user is typing (input / textarea / contenteditable /
 * select) or when a dialog/modal is open. Only the `g`-prefixed chords and a
 * guarded Esc fire — so the chat composer never eats a keystroke as a shortcut.
 *
 * Mount ONCE, high in the tree (App.tsx MainLayout). Reads the store via
 * getState() so it never re-subscribes / re-binds on every render.
 */

/** True when a keystroke belongs to text entry or an open modal — never a chord. */
function isTypingOrModal(): boolean {
  const el = document.activeElement as HTMLElement | null;
  if (el) {
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (el.isContentEditable) return true;
  }
  // Any open Radix / cmdk dialog or menu — the palette, dropdowns, confirm
  // sheets all mark themselves with these attributes.
  if (
    document.querySelector(
      '[role="dialog"],[role="alertdialog"],[data-state="open"][role="menu"],[cmdk-root]',
    )
  ) {
    return true;
  }
  return false;
}

/** Home = no campaign selected AND every takeover panel/page off. The
 *  navigate('/') is load-bearing: from inside /studio the campaign is already
 *  null, so clearing it wouldn't move the URL — only the route change leaves the
 *  Studio surface (and the two-way URL⇆showStudio bridge closes it). */
function goHome(navigate: NavigateFunction) {
  navigate('/');
  const s = useAppStore.getState();
  s.setSelectedCampaign(null);
  s.setShowDashboard(false);
  s.setShowStudio(false);
  s.setShowChangelog(false);
  s.setShowGuidelines(false);
  s.setShowConversations(false);
}

/** Open the last campaign the operator viewed (memory-only id). No-op if none. */
function goLastCampaign(): boolean {
  const s = useAppStore.getState();
  if (!s.lastCampaignId) return false;
  s.setSelectedCampaign(s.lastCampaignId);
  return true;
}

/** Plans lives as a tab inside a campaign page, opened via the existing
 *  `plans:open-tab` event — so ensure a campaign is selected first, then
 *  dispatch (deferred a tick so CampaignTabs is mounted to catch it). Mirrors
 *  AgentActivity's Upcoming-row idiom. */
function goPlans() {
  const s = useAppStore.getState();
  if (!s.selectedCampaignId) {
    if (!goLastCampaign()) return; // nothing to open Plans on
  }
  setTimeout(() => window.dispatchEvent(new CustomEvent('plans:open-tab')), 0);
}

export function useKeyboardNav() {
  // Timestamp of the last `g` press. A chord only completes if the second key
  // lands within the window; a lone `g` harmlessly expires.
  const gAt = useRef(0);
  const CHORD_MS = 1000;
  // react-router's navigate is referentially stable, so listing it as a dep
  // keeps the mount-once contract while giving the handler a live navigator.
  const navigate = useNavigate();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Never intercept while typing, inside a modal, or on a modified key
      // (Cmd/Ctrl/Alt combos belong to other bindings like the palette's Cmd+K).
      if (isTypingOrModal()) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // Esc on a campaign page → home. Guarded by isTypingOrModal above, so a
      // focused input or open modal keeps Esc for its own dismiss.
      if (e.key === 'Escape') {
        if (useAppStore.getState().selectedCampaignId) {
          e.preventDefault();
          goHome(navigate);
        }
        return;
      }

      const now = Date.now();
      const key = e.key.toLowerCase();

      // First half of a chord.
      if (key === 'g') {
        gAt.current = now;
        return;
      }

      // Second half — only counts if a `g` was pressed recently.
      if (now - gAt.current > CHORD_MS) return;

      if (key === 'h') {
        e.preventDefault();
        gAt.current = 0;
        goHome(navigate);
      } else if (key === 'c') {
        e.preventDefault();
        gAt.current = 0;
        goLastCampaign();
      } else if (key === 'p') {
        e.preventDefault();
        gAt.current = 0;
        goPlans();
      } else {
        // Any other key breaks the chord.
        gAt.current = 0;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [navigate]);
}
