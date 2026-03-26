import { Megaphone, FileText } from 'lucide-react';

interface ContextBadgeProps {
  campaignName: string | null;
  guidelinesLoaded: boolean;
}

export default function ContextBadge({ campaignName, guidelinesLoaded }: ContextBadgeProps) {
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs flex-wrap">
      {campaignName && (
        <span className="inline-flex items-center gap-1 bg-secondary rounded-full px-2.5 py-0.5 text-foreground">
          <Megaphone className="h-3 w-3" />
          {campaignName}
        </span>
      )}
      {guidelinesLoaded && (
        <span className="inline-flex items-center gap-1 bg-secondary rounded-full px-2.5 py-0.5 text-foreground">
          <span className="w-1.5 h-1.5 rounded-full bg-status-enabled" />
          <FileText className="h-3 w-3" />
          Guidelines loaded
        </span>
      )}
    </div>
  );
}
