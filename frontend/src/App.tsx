import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from '@/components/ui/tooltip';
import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';
import ContentArea from '@/components/layout/ContentArea';
import ChatPanel from '@/components/layout/ChatPanel';
import CommandPalette from '@/components/CommandPalette';
import SetupWizard from '@/components/setup/SetupWizard';
import AgencyDashboard from '@/components/dashboard/AgencyDashboard';
import SettingsPage from '@/components/settings/SettingsPage';
import { useAppStore } from '@/stores/appStore';
import { fetchAccountsV2 } from '@/lib/api';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

function MainLayout() {
  const [commandOpen, setCommandOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const {
    selectedAccountId,
    showDashboard,
    connectedAccounts,
    setConnectedAccounts,
    switchAccount,
    setShowDashboard,
  } = useAppStore();

  // Load connected accounts on mount and auto-select
  useEffect(() => {
    fetchAccountsV2().then((accounts) => {
      setConnectedAccounts(accounts);
      if (accounts.length === 0) {
        // No accounts — show setup
        window.location.assign('/setup');
      } else if (accounts.length === 1) {
        // Single account — select it directly
        switchAccount(accounts[0].id);
      } else {
        // Multiple accounts — show dashboard
        setShowDashboard(true);
      }
    }).catch(() => {
      // API unavailable — show setup
    });
  }, [setConnectedAccounts, switchAccount, setShowDashboard]);

  const showingDashboard = showDashboard || (!selectedAccountId && connectedAccounts.length > 1);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setShowSettings(true)}
      />
      {showSettings ? (
        <SettingsPage onClose={() => setShowSettings(false)} />
      ) : showingDashboard ? (
        <AgencyDashboard />
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          <ContentArea />
          <ChatPanel />
        </div>
      )}
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}

function AppRoot() {
  const navigate = useNavigate();

  useEffect(() => {
    fetchAccountsV2().then((accounts) => {
      if (accounts.length === 0) {
        navigate('/setup');
      }
    }).catch(() => {
      // Backend not ready yet, stay on main
    });
  }, [navigate]);

  return <MainLayout />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Routes>
          <Route path="/" element={<AppRoot />} />
          <Route path="/setup" element={<SetupWizard />} />
        </Routes>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
