import { useState } from 'react';
import { Settings, Command, Sun, Moon } from 'lucide-react';
import { useAppStore } from '@/stores/appStore';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface HeaderProps {
  onOpenCommandPalette: () => void;
}

export default function Header({ onOpenCommandPalette }: HeaderProps) {
  const { selectedAccountId, setSelectedAccount, setSelectedCampaign, darkMode, toggleDarkMode } = useAppStore();
  const [settingsOpen, setSettingsOpen] = useState(false);

  const currentAccountName = selectedAccountId ? 'Mercan Group' : 'Select account';

  return (
    <header className="h-12 flex items-center justify-between px-4 bg-card border-b border-border shrink-0">
      {/* Left */}
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-foreground tracking-tight">
          Google Ads Manager
        </h1>
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
          <DropdownMenuContent align="center">
            <DropdownMenuItem
              onClick={() => { setSelectedAccount('7178239091'); setSelectedCampaign(null); }}
              className="text-xs"
            >
              Mercan Group Main Account
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
            <DropdownMenuItem onClick={() => window.location.assign('/setup')}>
              Setup Wizard
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
