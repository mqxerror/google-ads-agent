import { create } from 'zustand'

interface AppState {
  selectedAccountId: string | null;
  selectedCampaignId: string | null;
  sidebarCollapsed: boolean;
  chatPanelWidth: number;
  darkMode: boolean;
  setSelectedAccount: (id: string | null) => void;
  setSelectedCampaign: (id: string | null) => void;
  toggleSidebar: () => void;
  setChatPanelWidth: (width: number) => void;
  toggleDarkMode: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  selectedAccountId: null,
  selectedCampaignId: null,
  sidebarCollapsed: false,
  chatPanelWidth: 400,
  darkMode: true,
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
}))
