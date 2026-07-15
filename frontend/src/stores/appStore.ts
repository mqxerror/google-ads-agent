import { create } from 'zustand'
import type { AccountV2 } from '@/types'

interface AppState {
  // V1 (kept)
  selectedAccountId: string | null;
  selectedCampaignId: string | null;
  /** Dashboard v2.1 (C2): the LAST campaign the operator viewed — MEMORY ONLY,
   *  it does NOT drive the view on app open (home is the default route now).
   *  Powers the home "Continue where you left off →" affordance. */
  lastCampaignId: string | null;
  sidebarCollapsed: boolean;
  chatPanelCollapsed: boolean;
  chatPanelWidth: number;
  darkMode: boolean;

  // V2 (new)
  connectedAccounts: AccountV2[];
  showDashboard: boolean;
  showStudio: boolean;
  showChangelog: boolean;
  showGuidelines: boolean;

  // Homepage v2 (Epic 13, Story 13.5)
  // The date-range window (in days) that drives the home KPI cards +
  // campaigns section. 7d default, persisted so the operator's window
  // survives reloads. Other pages don't read this.
  homeRangeDays: number;
  // Conversation Map moved off the home to its own routed page. This
  // toggle takes over the content area the same way showStudio does.
  showConversations: boolean;

  // Actions
  setSelectedAccount: (id: string | null) => void;
  setSelectedCampaign: (id: string | null) => void;
  toggleSidebar: () => void;
  toggleChatPanel: () => void;
  setChatPanelWidth: (width: number) => void;
  toggleDarkMode: () => void;
  setConnectedAccounts: (accounts: AccountV2[]) => void;
  switchAccount: (id: string) => void;
  setShowDashboard: (show: boolean) => void;
  setShowStudio: (show: boolean) => void;
  setShowChangelog: (show: boolean) => void;
  setShowGuidelines: (show: boolean) => void;
  setHomeRangeDays: (days: number) => void;
  setShowConversations: (show: boolean) => void;
}

const savedDarkMode = localStorage.getItem('darkMode');
const initialDarkMode = savedDarkMode !== null ? savedDarkMode === 'true' : true;
const savedAccountId = localStorage.getItem('selectedAccountId');
// Dashboard v2.1 (C2): the app no longer HIJACKS open into the last campaign.
// The persisted id is read as "last campaign" MEMORY (for the home "Continue
// where you left off" card), NOT as the initial view — selectedCampaignId
// starts null so `/` is always the default surface. (Before: the app reopened
// into whatever campaign was last selected — the home-access friction the plan
// calls out at appStore.ts:49,68.)
const savedCampaignId = localStorage.getItem('selectedCampaignId');
// Home date-range window (days). Default 7; only 7 / 14 / 30 are offered.
const savedHomeRange = parseInt(localStorage.getItem('homeRangeDays') || '', 10);
const initialHomeRange = [7, 14, 30].includes(savedHomeRange) ? savedHomeRange : 7;
// Apply on load before React renders
if (!initialDarkMode) document.documentElement.classList.add('light');

// Tiny helper so every path that mutates selectedCampaignId keeps localStorage
// in sync. Without persistence, opening the app the next day starts with
// selectedCampaignId=null, the chat panel happily accepts a message, and that
// message is born in an unbound conversation — the agent then has no campaign
// to load chronicle/decisions/role-notes from and looks like it "forgot".
const persistCampaign = (id: string | null) => {
  if (id) localStorage.setItem('selectedCampaignId', id);
  else localStorage.removeItem('selectedCampaignId');
};

export const useAppStore = create<AppState>((set) => ({
  selectedAccountId: savedAccountId || null,
  // C2: start on home, NOT the last campaign. The saved id lives on as
  // lastCampaignId for the "Continue where you left off" affordance only.
  selectedCampaignId: null,
  lastCampaignId: savedCampaignId || null,
  sidebarCollapsed: false,
  chatPanelCollapsed: localStorage.getItem('chatPanelCollapsed') === 'true',
  chatPanelWidth: 400,
  darkMode: initialDarkMode,
  connectedAccounts: [],
  showDashboard: false,
  showStudio: false,
  showChangelog: false,
  showGuidelines: false,
  homeRangeDays: initialHomeRange,
  showConversations: false,

  setSelectedAccount: (id) => {
    if (id) localStorage.setItem('selectedAccountId', id);
    set({ selectedAccountId: id });
  },
  setSelectedCampaign: (id) => {
    persistCampaign(id);
    // Selecting a campaign records it as the "last campaign" memory too, so the
    // home "Continue where you left off" card points at the right one next time.
    // (Clearing to null keeps the previous memory — don't forget it on close.)
    set((s) => ({
      selectedCampaignId: id,
      lastCampaignId: id ?? s.lastCampaignId,
      showStudio: false, showChangelog: false, showGuidelines: false, showConversations: false,
    }));
  },
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleChatPanel: () => set((s) => {
    const next = !s.chatPanelCollapsed;
    localStorage.setItem('chatPanelCollapsed', String(next));
    return { chatPanelCollapsed: next };
  }),
  setChatPanelWidth: (width) => set({ chatPanelWidth: width }),
  toggleDarkMode: () =>
    set((s) => {
      const newDarkMode = !s.darkMode;
      localStorage.setItem('darkMode', String(newDarkMode));
      document.documentElement.classList.toggle('light', !newDarkMode);
      return { darkMode: newDarkMode };
    }),
  setConnectedAccounts: (accounts) => set({ connectedAccounts: accounts }),
  switchAccount: (id) => {
    localStorage.setItem('selectedAccountId', id);
    persistCampaign(null);
    // A different account's last-campaign memory doesn't apply — clear it.
    set({
      selectedAccountId: id,
      selectedCampaignId: null,
      lastCampaignId: null,
      showDashboard: false,
    });
  },
  setShowDashboard: (show) => set({ showDashboard: show }),
  setShowStudio: (show) => set((s) => {
    if (show) persistCampaign(null);
    return {
      showStudio: show,
      showChangelog: show ? false : s.showChangelog,
      showGuidelines: show ? false : s.showGuidelines,
      showConversations: show ? false : s.showConversations,
      // Clear campaign selection when opening the studio so it takes over the view
      selectedCampaignId: show ? null : s.selectedCampaignId,
    };
  }),
  setShowChangelog: (show) => set((s) => {
    if (show) persistCampaign(null);
    return {
      showChangelog: show,
      showStudio: show ? false : s.showStudio,
      showGuidelines: show ? false : s.showGuidelines,
      showConversations: show ? false : s.showConversations,
      selectedCampaignId: show ? null : s.selectedCampaignId,
    };
  }),
  setShowGuidelines: (show) => set((s) => {
    if (show) persistCampaign(null);
    return {
      showGuidelines: show,
      showStudio: show ? false : s.showStudio,
      showChangelog: show ? false : s.showChangelog,
      showConversations: show ? false : s.showConversations,
      selectedCampaignId: show ? null : s.selectedCampaignId,
    };
  }),
  setHomeRangeDays: (days) => {
    localStorage.setItem('homeRangeDays', String(days));
    set({ homeRangeDays: days });
  },
  setShowConversations: (show) => set((s) => {
    if (show) persistCampaign(null);
    return {
      showConversations: show,
      showStudio: show ? false : s.showStudio,
      showChangelog: show ? false : s.showChangelog,
      showGuidelines: show ? false : s.showGuidelines,
      selectedCampaignId: show ? null : s.selectedCampaignId,
    };
  }),
}))
