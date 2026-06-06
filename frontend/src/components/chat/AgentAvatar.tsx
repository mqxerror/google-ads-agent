import { cn } from '@/lib/utils';
import { type AgentProfile, getAgentProfile } from '@/lib/agentProfiles';

interface AgentAvatarProps {
  roleId?: string;
  profile?: AgentProfile;
  size?: 'sm' | 'md' | 'lg';
  showStatus?: boolean;
  isWorking?: boolean;
}

const SIZES = {
  sm: 'w-6 h-6 text-[9px]',
  md: 'w-8 h-8 text-[10px]',
  lg: 'w-10 h-10 text-xs',
};

export default function AgentAvatar({ roleId, profile, size = 'md', showStatus, isWorking }: AgentAvatarProps) {
  const agent = profile || getAgentProfile(roleId);

  return (
    <div className="relative shrink-0">
      <div
        className={cn(
          'rounded-full flex items-center justify-center font-semibold border',
          SIZES[size],
        )}
        style={{
          backgroundColor: agent.bgColor,
          borderColor: agent.borderColor,
          color: agent.color,
          boxShadow: 'var(--shadow-resting)',
        }}
        title={`${agent.name} — ${agent.title}`}
      >
        {agent.initials}
      </div>
      {showStatus && (
        <span
          className={cn(
            'absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-surface',
            isWorking ? 'studio-pulse bg-accent' : 'bg-success',
          )}
        />
      )}
    </div>
  );
}
