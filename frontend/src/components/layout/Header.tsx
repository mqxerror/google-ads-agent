import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Settings, Command, Sun, Moon, Plus, LayoutDashboard, Trash2, Home, Brain, Film, ScrollText, BookOpen, GitBranch } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
import { cn } from '@/lib/utils';
import { fetchAccountsV2, removeAccount } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface HeaderProps {
  onOpenCommandPalette: () => void;
  onOpenSettings?: () => void;
  onOpenIntelligence?: () => void;
  intelligenceActive?: boolean;
}

export default function Header({ onOpenCommandPalette, onOpenSettings, onOpenIntelligence, intelligenceActive }: HeaderProps) {
  const {
    selectedAccountId,
    selectedCampaignId,
    setSelectedCampaign,
    connectedAccounts,
    setConnectedAccounts,
    switchAccount,
    setShowDashboard,
    showStudio,
    showChangelog,
    setShowChangelog,
    showGuidelines,
    setShowGuidelines,
    showConversations,
    setShowConversations,
    darkMode,
    toggleDarkMode,
  } = useAppStore();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const navigate = useNavigate();

  // Fetch V2 accounts and sync to store
  const { refetch } = useQuery({
    queryKey: ['accounts-v2'],
    queryFn: async () => {
      const accounts = await fetchAccountsV2();
      setConnectedAccounts(accounts);
      return accounts;
    },
    staleTime: 60_000,
  });

  const currentAccount = connectedAccounts.find((a) => a.id === selectedAccountId);
  // Show the account name, falling back to the first connected account's name
  const currentAccountName = currentAccount?.name
    || connectedAccounts[0]?.name
    || (selectedAccountId ? `Account ${selectedAccountId}` : 'Select account');

  const handleRemoveAccount = async (accountId: string) => {
    if (!confirm(`Remove account ${accountId} and all its data?`)) return;
    await removeAccount(accountId);
    refetch();
    if (selectedAccountId === accountId) {
      setShowDashboard(true);
    }
  };

  return (
    <header className="h-12 flex items-center justify-between px-4 bg-card border-b border-border shrink-0">
      {/* Left */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setShowDashboard(true)}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity"
        >
          <h1 className="text-sm font-semibold text-foreground tracking-tight">
            Google Ads Agent
          </h1>
        </button>
        {selectedCampaignId && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground gap-1"
            onClick={() => { setSelectedCampaign(null); setShowDashboard(false); }}
          >
            <Home className="h-3 w-3" />
            Home
          </Button>
        )}
        {connectedAccounts.length > 1 && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground gap-1"
            onClick={() => setShowDashboard(true)}
          >
            <LayoutDashboard className="h-3 w-3" />
            Dashboard
          </Button>
        )}
      </div>

      {/* Center - Account selector */}
      <div className="flex items-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="text-xs gap-2">
              <span className="text-muted-foreground">Account:</span>
              <span>{currentAccountName}</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" className="w-64">
            {connectedAccounts.map((acct) => (
              <DropdownMenuItem
                key={acct.id}
                onClick={() => switchAccount(acct.id)}
                className="text-xs flex justify-between items-center"
              >
                <span className={acct.id === selectedAccountId ? 'font-medium' : ''}>
                  {acct.name}
                </span>
                <span className="text-muted-foreground text-[10px]">{acct.id}</span>
              </DropdownMenuItem>
            ))}
            {connectedAccounts.length > 0 && <DropdownMenuSeparator />}
            <DropdownMenuItem
              onClick={() => window.location.assign('/setup')}
              className="text-xs gap-2"
            >
              <Plus className="h-3 w-3" />
              Add Account
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Right */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'text-xs gap-1',
            showConversations ? 'bg-accent-soft text-accent hover:bg-accent-soft hover:text-accent' : 'text-muted-foreground'
          )}
          onClick={() => setShowConversations(!showConversations)}
          title="Conversations — the full conversation map"
        >
          <GitBranch className="h-3 w-3" />
          Conversations
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'text-xs gap-1',
            showStudio ? 'bg-accent-soft text-accent hover:bg-accent-soft hover:text-accent' : 'text-muted-foreground'
          )}
          onClick={() => navigate(showStudio ? '/' : '/studio')}
          title="Ad Studio — generate and manage creative"
        >
          <Film className="h-3 w-3" />
          Studio
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'text-xs gap-1',
            showGuidelines ? 'bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 hover:text-amber-300' : 'text-muted-foreground'
          )}
          onClick={() => setShowGuidelines(!showGuidelines)}
          title="Guidelines — view + suggest edits to account rules"
        >
          <BookOpen className="h-3 w-3" />
          Guidelines
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            'text-xs gap-1',
            showChangelog ? 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 hover:text-emerald-300' : 'text-muted-foreground'
          )}
          onClick={() => setShowChangelog(!showChangelog)}
          title="Changelog — what's new and what's fixed"
        >
          <ScrollText className="h-3 w-3" />
          Changelog
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground gap-1"
          onClick={onOpenCommandPalette}
        >
          <Command className="h-3 w-3" />
          <span>K</span>
        </Button>
        {onOpenIntelligence && (
          <Button variant="ghost" size="icon" className={cn("h-8 w-8", intelligenceActive && "bg-primary/10")} onClick={onOpenIntelligence} title={intelligenceActive ? "Back to campaigns" : "Agent Intelligence"}>
            <Brain className={cn("h-4 w-4", intelligenceActive ? "text-primary" : "text-muted-foreground")} />
          </Button>
        )}
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleDarkMode}>
          {darkMode ? <Sun className="h-4 w-4 text-muted-foreground" /> : <Moon className="h-4 w-4 text-muted-foreground" />}
        </Button>
        <DropdownMenu open={settingsOpen} onOpenChange={setSettingsOpen}>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <Settings className="h-4 w-4 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {onOpenSettings && (
              <DropdownMenuItem onClick={() => { setSettingsOpen(false); onOpenSettings(); }}>
                <Settings className="h-3 w-3 mr-2" />
                Settings
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => window.location.assign('/setup')}>
              <Plus className="h-3 w-3 mr-2" />
              Add Account
            </DropdownMenuItem>
            {selectedAccountId && (
              <DropdownMenuItem
                onClick={() => handleRemoveAccount(selectedAccountId)}
                className="text-destructive"
              >
                <Trash2 className="h-3 w-3 mr-2" />
                Remove Current Account
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
