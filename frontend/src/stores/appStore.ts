import { create } from 'zustand'
import type { AccountV2 } from '@/types'

interface AppState {
  // V1 (kept)
  selectedAccountId: string | null;
  selectedCampaignId: string | null;
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
}

const savedDarkMode = localStorage.getItem('darkMode');
const initialDarkMode = savedDarkMode !== null ? savedDarkMode === 'true' : true;
const savedAccountId = localStorage.getItem('selectedAccountId');
const savedCampaignId = localStorage.getItem('selectedCampaignId');
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
  selectedCampaignId: savedCampaignId || null,
  sidebarCollapsed: false,
  chatPanelCollapsed: localStorage.getItem('chatPanelCollapsed') === 'true',
  chatPanelWidth: 400,
  darkMode: initialDarkMode,
  connectedAccounts: [],
  showDashboard: false,
  showStudio: false,
  showChangelog: false,
  showGuidelines: false,

  setSelectedAccount: (id) => {
    if (id) localStorage.setItem('selectedAccountId', id);
    set({ selectedAccountId: id });
  },
  setSelectedCampaign: (id) => {
    persistCampaign(id);
    set({ selectedCampaignId: id, showStudio: false, showChangelog: false, showGuidelines: false });
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
    set({
      selectedAccountId: id,
      selectedCampaignId: null,
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
      selectedCampaignId: show ? null : s.selectedCampaignId,
    };
  }),
  setShowGuidelines: (show) => set((s) => {
    if (show) persistCampaign(null);
    return {
      showGuidelines: show,
      showStudio: show ? false : s.showStudio,
      showChangelog: show ? false : s.showChangelog,
      selectedCampaignId: show ? null : s.selectedCampaignId,
    };
  }),
}))
