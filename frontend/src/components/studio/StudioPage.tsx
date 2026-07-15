/**
 * StudioPage — the Studio router (Epic A / redesign plan §2.2).
 *
 * Once the whole Studio hub, now a thin dispatcher over the studio fork.
 * ContentArea still renders <StudioPage/> when showStudio is true (the
 * store boolean is untouched — the fork lives INSIDE the studio surface);
 * this component reads the URL and mounts the right sub-studio:
 *
 *   /studio, /studio/c/:assetId   → StudioHome  (chooser + Library/Souls/Presets)
 *   /studio/ai-video*             → AIVideoStudio (Epic B placeholder)
 *   /studio/kinetic*              → KineticStudio (legacy VideoCreator re-home)
 *
 * Kept named StudioPage so existing imports (ContentArea, PMax comment
 * refs) don't break. See research/studio-redesign-plan.md §2.
 */

import { useLocation } from 'react-router-dom';
import StudioHome from './StudioHome';
import AIVideoStudio from './AIVideoStudio';
import KineticStudio from './KineticStudio';

export default function StudioPage() {
  const { pathname } = useLocation();

  if (pathname.startsWith('/studio/ai-video')) return <AIVideoStudio />;
  if (pathname.startsWith('/studio/kinetic')) return <KineticStudio />;
  // /studio and /studio/c/:assetId both land on Home (deep-link asset
  // selection is a Home/Library concern, preserved unchanged).
  return <StudioHome />;
}
