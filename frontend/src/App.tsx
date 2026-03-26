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
import { useAppStore } from '@/stores/appStore';

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
  const { setSelectedAccount } = useAppStore();

  // Auto-select the client account on mount
  useEffect(() => {
    setSelectedAccount('7178239091');
  }, [setSelectedAccount]);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header onOpenCommandPalette={() => setCommandOpen(true)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <ContentArea />
        <ChatPanel />
      </div>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}

function SetupRedirect() {
  const navigate = useNavigate();

  useEffect(() => {
    // In production, check /api/setup/status and redirect if not configured.
    // For now, always show the main app.
    // Uncomment the following to enable setup check:
    // fetchSetupStatus().then(s => { if (!s.configured) navigate('/setup'); }).catch(() => {});
    void navigate;
  }, [navigate]);

  return <MainLayout />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Routes>
          <Route path="/" element={<SetupRedirect />} />
          <Route path="/setup" element={<SetupWizard />} />
        </Routes>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
