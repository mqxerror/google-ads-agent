/**
 * Shared prop types for the AI Video Studio workspace. The page (AIVideoStudio)
 * owns all project + audio + avatar state and threads setters down to the rail,
 * canvas and dock. Keeping the shapes here avoids a web of inline prop types.
 */

import type { StudioModelInfo } from '@/lib/api';

/** Which source the Director drafts from in the empty-state card. */
export type BriefSourceType = 'text' | 'campaign' | 'landing_page';

/** Audio selections chosen in the rail, consumed by the render payload. */
export interface AudioState {
  musicOn: boolean;
  musicFilename: string | null;
  voOn: boolean;
  voiceId: string | null;
}

/** Brand avatar selection (soul) chosen in the rail. */
export interface AvatarState {
  soulId: string | null;
  voiceId: string | null;
}

/** Everything the rail needs from the page. */
export interface RailControls {
  accountId: string;
  campaignId: string | null;
  onCampaignChange: (id: string | null) => void;
  consultDirector: boolean;
  onConsultChange: (v: boolean) => void;
  modelId: string;
  modelInfo: StudioModelInfo | undefined;
  onOpenGallery: () => void;
  targetSeconds: number;
  onTargetChange: (s: number) => void;
  aspect: string;
  onAspectChange: (a: string) => void;
  audio: AudioState;
  onAudioChange: (patch: Partial<AudioState>) => void;
  avatar: AvatarState;
  onAvatarChange: (patch: Partial<AvatarState>) => void;
  brief: string;
  onBriefChange: (b: string) => void;
  /** Draft-source selector: which context the Director reads. */
  briefSourceType: BriefSourceType;
  onBriefSourceTypeChange: (t: BriefSourceType) => void;
  landingUrl: string;
  onLandingUrlChange: (u: string) => void;
  /** Inline error from a failed draft (e.g. 400: campaign/url missing). */
  draftError: string | null;
  hasStoryboard: boolean;
  drafting: boolean;
  onDraft: () => void;
}
