/**
 * KineticStudio — the recomposed Kinetic Studio (Epic D / plan §7).
 *
 * Replaces the Epic A shim (which mounted the legacy VideoCreator). This
 * is now a full-page content-area takeover with THREE LANES as top tabs,
 * each in a spacious two-column BRIEF / PREVIEW flow (plan §7.1):
 *
 *   Brand Reel   → POST /api/video/brand-reel            (Pillow + ffmpeg)
 *   Premium Reel → POST /api/video/premium-reel + …/storyboard-plan|render (Hyperframes GSAP)
 *   Presenter    → POST /api/video/generate              (HeyGen talking avatar)
 *
 * The recomposition extracts VideoCreator's render logic into hooks
 * (useKineticRender, useBrandStoryPlan) and lane components under
 * ./kinetic/. VideoCreator.tsx is INTENTIONALLY KEPT (ChatInput.tsx still
 * mounts it for the in-chat video creator) — the plan's §9.3 "delete
 * VideoCreator" is NOT executed this pass, because deleting it would break
 * the chat mount. See the report for the plan-vs-reality note. This studio
 * no longer imports VideoCreator; the render payloads it sends are
 * byte-identical to the legacy component's (AC D1).
 *
 * Backend is zero-change for Kinetic (§7.2): same endpoints, same SSE
 * consumer. Design: DESIGN.md light-mode tokens only, no banned colors,
 * verbatim-lock uses the warning token, storyboard cards use §3.3 language.
 *
 * The `:lane` route param pre-selects a tab (brand-reel / premium-reel /
 * presenter). See research/studio-redesign-plan.md §7.
 */

import { useCallback, useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { ASSETS_QUERY_KEY } from './AssetLibrary';
import BrandReelLane from './kinetic/BrandReelLane';
import PremiumReelLane from './kinetic/PremiumReelLane';
import PresenterLane from './kinetic/PresenterLane';

type LaneKey = 'brand-reel' | 'premium-reel' | 'presenter';

const LANES: { key: LaneKey; label: string; engine: string }[] = [
  { key: 'brand-reel', label: 'Brand Reel', engine: 'fast local render · Pillow + ffmpeg' },
  { key: 'premium-reel', label: 'Premium Reel', engine: 'kinetic typography · Hyperframes GSAP' },
  { key: 'presenter', label: 'Presenter', engine: 'talking avatar · HeyGen' },
];

export default function KineticStudio() {
  const accountId = useClientAccountId();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { lane: laneParam } = useParams<{ lane?: string }>();

  const initialLane: LaneKey =
    laneParam === 'premium-reel' || laneParam === 'presenter' ? laneParam
    : 'brand-reel';
  const [lane, setLane] = useState<LaneKey>(initialLane);
  useEffect(() => {
    if (laneParam === 'brand-reel' || laneParam === 'premium-reel' || laneParam === 'presenter') {
      setLane(laneParam);
    }
  }, [laneParam]);

  const refreshAssets = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: [ASSETS_QUERY_KEY] });
  }, [queryClient]);

  const backToStudio = useCallback(() => navigate('/studio'), [navigate]);
  const goToSouls = useCallback(() => navigate('/studio#souls'), [navigate]);

  const onVideoReady = useCallback(() => { refreshAssets(); }, [refreshAssets]);

  const active = LANES.find((l) => l.key === lane)!;

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-1">
        <button
          onClick={backToStudio}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-text px-2 py-1 rounded-md transition-colors"
          title="Back to Studio Home"
        >
          <ArrowLeft className="h-4 w-4" /> Studio
        </button>
        <h1 className="text-xl font-semibold uppercase tracking-wide text-text">Kinetic Studio</h1>
      </div>
      <p className="text-xs text-muted-foreground mb-4 ml-[3.4rem]">
        motion graphics and typography, renders locally, no credits
      </p>

      {/* Lane tabs */}
      <div className="flex items-center gap-1 mb-1 border-b border-border">
        {LANES.map((l) => (
          <button
            key={l.key}
            onClick={() => setLane(l.key)}
            className={cn(
              'px-3.5 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors',
              lane === l.key ? 'border-accent text-accent' : 'border-transparent text-muted-foreground hover:text-text',
            )}
          >
            {l.label}
          </button>
        ))}
      </div>
      <p className="text-[11px] text-muted-foreground font-mono mb-5">{active.engine}</p>

      {/* Active lane */}
      <div>
        {lane === 'brand-reel' && (
          <BrandReelLane accountId={accountId} campaignId={null} onVideoReady={onVideoReady} />
        )}
        {lane === 'premium-reel' && (
          <PremiumReelLane accountId={accountId} campaignId={null} onVideoReady={onVideoReady} />
        )}
        {lane === 'presenter' && (
          <PresenterLane accountId={accountId} campaignId={null} campaignName={null} onVideoReady={onVideoReady} onGoToSouls={goToSouls} />
        )}
      </div>
    </div>
  );
}
