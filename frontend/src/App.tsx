import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from '@/components/ui/tooltip';
import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';
import ContentArea from '@/components/layout/ContentArea';
import ChatPanel from '@/components/layout/ChatPanel';
import HomeChatDock from '@/components/layout/HomeChatDock';
import CommandPalette from '@/components/CommandPalette';
import SetupWizard from '@/components/setup/SetupWizard';
import AgencyDashboard from '@/components/dashboard/AgencyDashboard';
import SettingsPage from '@/components/settings/SettingsPage';
import AgentIntelligence from '@/pages/AgentIntelligence';
import { useAppStore } from '@/stores/appStore';
import { useKeyboardNav } from '@/hooks/useKeyboardNav';
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
  const [showIntelligence, setShowIntelligence] = useState(false);
  useKeyboardNav(); // C3: g h / g c / g p chords + Esc-to-home (guarded while typing)
  const {
    selectedAccountId,
    showDashboard,
    showStudio,
    showChangelog,
    showGuidelines,
    showConversations,
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
        // Single account — always ensure it's selected
        const current = useAppStore.getState().selectedAccountId;
        if (current !== accounts[0].id) switchAccount(accounts[0].id);
      } else {
        // Multiple accounts — show dashboard if no account selected
        const current = useAppStore.getState().selectedAccountId;
        if (!current) setShowDashboard(true);
      }
    }).catch(() => {
      // API unavailable — show setup
    });
  }, [setConnectedAccounts, switchAccount, setShowDashboard]);

  // Close intelligence/settings when user selects a campaign from sidebar
  const selectedCampaignId = useAppStore((s) => s.selectedCampaignId);
  useEffect(() => {
    if (selectedCampaignId) {
      setShowIntelligence(false);
      setShowSettings(false);
    }
  }, [selectedCampaignId]);

  // URL → showStudio bridge. `/studio` and `/studio/c/:assetId` both
  // open the Studio overlay (same shape as the /c/:conversationId
  // route → ChatPanel sync). Pushing to either URL out-of-band (e.g.
  // pasting a /studio/c/<id> link) opens the Studio with that asset
  // selected. Closing the Studio (its onClose) navigates back to "/".
  const location = useLocation();
  const navigate = useNavigate();
  const setShowStudio = useAppStore((s) => s.setShowStudio);
  useEffect(() => {
    if (location.pathname.startsWith('/studio')) setShowStudio(true);
  }, [location.pathname, setShowStudio]);

  // C2: campaign as a real route. Two-way URL sync, same shape as /studio + /c.
  //   URL → store: landing on /campaign/:id (deep-link, refresh, browser-back)
  //     selects that campaign so the deep-link is shareable and refresh keeps
  //     you where you are.
  //   store → URL: selecting a campaign pushes /campaign/:id; going home pushes
  //     /. So browser-back FROM a campaign lands on home (the plan's PART 4.1).
  // Both guarded to avoid navigation loops (only act on a genuine mismatch), and
  // scoped so the studio / chat / setup routes are never hijacked.
  const setSelectedCampaign = useAppStore((s) => s.setSelectedCampaign);
  // URL → store. Landing on /campaign/:id selects it; landing on "/" (incl.
  // browser-back from a campaign) CLEARS the selection so home is truly home —
  // this is what makes back-from-campaign land on the command center, not
  // bounce straight back to the campaign. Scoped to the two managed paths only.
  useEffect(() => {
    const m = /^\/campaign\/([^/]+)$/.exec(location.pathname);
    if (m) {
      if (m[1] !== selectedCampaignId) setSelectedCampaign(m[1]);
    } else if (location.pathname === '/' && selectedCampaignId) {
      setSelectedCampaign(null);
    }
  }, [location.pathname, selectedCampaignId, setSelectedCampaign]);
  // store → URL. Selecting a campaign while on a managed path pushes
  // /campaign/:id (shareable, refresh-safe). Home selection is reflected as "/".
  // Only touches the campaign<->home URL pair; never stomps /studio, /c, /setup.
  useEffect(() => {
    const onCampaignRoute = location.pathname.startsWith('/campaign/');
    const onManagedRoute = onCampaignRoute || location.pathname === '/';
    if (!onManagedRoute) return;
    if (selectedCampaignId && location.pathname !== `/campaign/${selectedCampaignId}`) {
      navigate(`/campaign/${selectedCampaignId}`);
    } else if (!selectedCampaignId && onCampaignRoute) {
      // Selection cleared while still on a campaign URL (e.g. the `g h` chord
      // or the Home rail) → reflect home in the URL. Not triggered by
      // browser-back (that already put us on "/"), so no bounce-back loop.
      navigate('/');
    }
  }, [selectedCampaignId, location.pathname, navigate]);

  const showingDashboard = showDashboard || (!selectedAccountId && connectedAccounts.length > 1);

  // Home = the command-center surface (Story 13.5): no campaign selected
  // and none of the takeover pages / panels active. Only here does the
  // chat become a summoned drawer and the sidebar collapse to an icon
  // rail. Campaign + all other routes keep the parked rail + full tree.
  const isHome =
    !showingDashboard &&
    !showIntelligence &&
    !showSettings &&
    !selectedCampaignId &&
    !showStudio &&
    !showChangelog &&
    !showGuidelines &&
    !showConversations;

  // Studio surface (Epic 12): reclaim the full viewport for the storyboard
  // canvas + Video Director dock. It reuses home's "bare chrome" exactly —
  // sidebar → icon rail (campaign tree stays reachable as the flyout), and
  // the campaign chat becomes the summoned HomeChatDock drawer instead of a
  // parked ChatPanel rail. Derived straight from the URL (not the `showStudio`
  // store bool, which only flips in a post-mount effect) so a deep-link into
  // /studio/* lands already-collapsed on the FIRST render — no flash-then-collapse.
  const isStudio = location.pathname.startsWith('/studio');
  // `bareChrome` = the single flag the three chrome gates below key off. Home
  // and studio both want it; every other surface keeps the parked rail + tree.
  const bareChrome = isHome || isStudio;

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setShowSettings(true)}
        onOpenIntelligence={() => {
          const next = !showIntelligence;
          setShowIntelligence(next);
          setShowSettings(false);
          // When opening intelligence, go to home (no campaign selected)
          if (next) {
            useAppStore.getState().setSelectedCampaign(null);
            useAppStore.getState().setShowDashboard(false);
          }
        }}
        intelligenceActive={showIntelligence}
      />
      {showingDashboard ? (
        <AgencyDashboard />
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <Sidebar isHome={isHome} bare={bareChrome} />
          {showIntelligence ? (
            <div className="flex-1 overflow-y-auto">
              <AgentIntelligence onClose={() => setShowIntelligence(false)} />
            </div>
          ) : showSettings ? (
            <SettingsPage onClose={() => setShowSettings(false)} />
          ) : (
            <>
              <ContentArea />
              {/* Home + Studio summon the chat as a drawer (floating button +
                  ⌘K) so it never eats surface width; every other surface keeps
                  the always-open right rail. */}
              {bareChrome ? <HomeChatDock /> : <ChatPanel />}
            </>
          )}
        </div>
      )}
      {/* On home + studio, ⌘K opens the chat drawer (HomeChatDock owns it), so
          the campaign-search palette's ⌘K stands down to avoid a double-bind. */}
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} disableHotkey={bareChrome} />
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
          {/* Direct conversation links — `/c/:id` opens that exact chat.
              ChatPanel reads the param from useParams and loads it on
              mount; useEffect also pushes the current conversationId
              back into the URL so refresh / share / browser-back all
              keep the chat in sync with what the user sees. */}
          <Route path="/c/:conversationId" element={<AppRoot />} />
          {/* Studio deep-links — `/studio` opens the asset library;
              `/studio/c/:assetId` opens it with that asset selected.
              Same shape as /c/:id for chat. StudioPage reads useParams
              to highlight + scroll-to the asset; navigate-on-click
              keeps the URL in sync (refresh / share / bookmark work). */}
          <Route path="/studio" element={<AppRoot />} />
          <Route path="/studio/c/:assetId" element={<AppRoot />} />
          {/* Studio fork (Epic A) — the door cards on Home open full-page
              sub-studios. Same shape as the /studio pair: all render
              <AppRoot/>, and the `startsWith('/studio')` bridge above
              already flips showStudio for them, so no bridge change is
              needed. StudioRouter (StudioPage.tsx) reads useLocation and
              renders the right sub-studio (Home / AI Video / Kinetic). */}
          <Route path="/studio/ai-video" element={<AppRoot />} />
          <Route path="/studio/ai-video/:projectId" element={<AppRoot />} />
          <Route path="/studio/kinetic" element={<AppRoot />} />
          <Route path="/studio/kinetic/:lane" element={<AppRoot />} />
          {/* Campaign deep-links (C2) — `/campaign/:id` opens that campaign.
              MainLayout's URL<->store bridge selects it on mount (shareable,
              refresh-safe) and pushes the URL when a campaign is selected, so
              browser-back from a campaign lands on home. */}
          <Route path="/campaign/:campaignId" element={<AppRoot />} />
          <Route path="/setup" element={<SetupWizard />} />
        </Routes>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
