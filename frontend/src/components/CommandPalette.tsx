import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Command } from 'cmdk';
import { useAppStore } from '@/stores/appStore';
import type { Campaign } from '@/types';

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const { setSelectedCampaign, setSelectedAccount } = useAppStore();
  const queryClient = useQueryClient();

  // Get campaigns from TanStack Query cache
  const campaigns = (queryClient.getQueryData<Campaign[]>(['campaigns', '7178239091']) ?? []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      <div className="absolute inset-0 bg-black/60" onClick={() => onOpenChange(false)} />
      <div className="relative w-full max-w-lg">
        <Command className="bg-card border border-border rounded-lg shadow-2xl overflow-hidden" label="Command Palette">
          <Command.Input
            placeholder="Search campaigns..."
            className="w-full px-4 py-3 text-sm text-foreground bg-transparent border-b border-border outline-none placeholder:text-muted-foreground"
          />
          <Command.List className="max-h-[300px] overflow-y-auto p-2">
            <Command.Empty className="px-4 py-6 text-sm text-muted-foreground text-center">
              No campaigns found.
            </Command.Empty>
            <Command.Group
              heading="Campaigns"
              className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:text-muted-foreground"
            >
              {campaigns.map((campaign) => {
                const statusDot =
                  campaign.status === 'ENABLED' ? 'bg-status-enabled'
                    : campaign.status === 'PAUSED' ? 'bg-status-paused'
                    : 'bg-status-removed';
                return (
                  <Command.Item
                    key={campaign.id}
                    value={campaign.name}
                    onSelect={() => {
                      setSelectedCampaign(campaign.id);
                      setSelectedAccount('7178239091');
                      onOpenChange(false);
                    }}
                    className="flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer text-sm text-foreground data-[selected=true]:bg-secondary transition-colors"
                  >
                    <span className={`w-2 h-2 rounded-full shrink-0 ${statusDot}`} />
                    <div className="flex-1 min-w-0">
                      <div className="truncate">{campaign.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {campaign.status} &middot; Mercan Group
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">{campaign.channelType}</span>
                  </Command.Item>
                );
              })}
            </Command.Group>
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
