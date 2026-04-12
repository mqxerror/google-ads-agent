import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Settings, Command, Sun, Moon, Plus, LayoutDashboard, Trash2, Home } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
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
}

export default function Header({ onOpenCommandPalette, onOpenSettings }: HeaderProps) {
  const {
    selectedAccountId,
    selectedCampaignId,
    setSelectedCampaign,
    connectedAccounts,
    setConnectedAccounts,
    switchAccount,
    setShowDashboard,
    darkMode,
    toggleDarkMode,
  } = useAppStore();
  const [settingsOpen, setSettingsOpen] = useState(false);

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
          className="text-xs text-muted-foreground gap-1"
          onClick={onOpenCommandPalette}
        >
          <Command className="h-3 w-3" />
          <span>K</span>
        </Button>
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
