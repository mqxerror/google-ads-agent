import { create } from 'zustand'
import type { AccountV2 } from '@/types'

interface AppState {
  // V1 (kept)
  selectedAccountId: string | null;
  selectedCampaignId: string | null;
  sidebarCollapsed: boolean;
  chatPanelWidth: number;
  darkMode: boolean;

  // V2 (new)
  connectedAccounts: AccountV2[];
  showDashboard: boolean;

  // Actions
  setSelectedAccount: (id: string | null) => void;
  setSelectedCampaign: (id: string | null) => void;
  toggleSidebar: () => void;
  setChatPanelWidth: (width: number) => void;
  toggleDarkMode: () => void;
  setConnectedAccounts: (accounts: AccountV2[]) => void;
  switchAccount: (id: string) => void;
  setShowDashboard: (show: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedAccountId: null,
  selectedCampaignId: null,
  sidebarCollapsed: false,
  chatPanelWidth: 400,
  darkMode: true,
  connectedAccounts: [],
  showDashboard: false,

  setSelectedAccount: (id) => set({ selectedAccountId: id }),
  setSelectedCampaign: (id) => set({ selectedCampaignId: id }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setChatPanelWidth: (width) => set({ chatPanelWidth: width }),
  toggleDarkMode: () =>
    set((s) => {
      const newDarkMode = !s.darkMode;
      document.documentElement.classList.toggle('light', !newDarkMode);
      return { darkMode: newDarkMode };
    }),
  setConnectedAccounts: (accounts) => set({ connectedAccounts: accounts }),
  switchAccount: (id) => set({
    selectedAccountId: id,
    selectedCampaignId: null,
    showDashboard: false,
  }),
  setShowDashboard: (show) => set({ showDashboard: show }),
}))
