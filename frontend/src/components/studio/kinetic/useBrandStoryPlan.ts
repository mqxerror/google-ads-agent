/**
 * useBrandStoryPlan — the Brand Story two-phase flow, extracted from
 * VideoCreator (plan/preview/render).
 *
 * Verbatim logic from VideoCreator:
 *  - planBrandStory       → POST /api/video/premium-reel/storyboard-plan  (@465-503)
 *  - renderPlannedStoryboard → POST /api/video/premium-reel/storyboard-render (@506-545)
 *  - updateScene helper    (@123-125)
 *  - stock search/adopt + AI image gen (@130-207)
 *
 * The render POST reuses the shared consumeStream (passed in) so the SSE
 * contract stays identical. Request payloads are BYTE-IDENTICAL to the
 * legacy calls (plan §7.2, AC D2).
 */

import { useState, useCallback } from 'react';

export type Scene = Record<string, unknown>;

interface UseBrandStoryPlanArgs {
  accountId?: string;
  campaignId?: string | null;
  consumeStream: (res: Response, scriptForLibrary: string, thumb?: string) => Promise<void>;
  setRendering: (b: boolean) => void;
  setStage: (s: string) => void;
  setStageMsg: (s: string) => void;
  setError: (e: string) => void;
}

export function useBrandStoryPlan({
  accountId, campaignId, consumeStream, setRendering, setStage, setStageMsg, setError,
}: UseBrandStoryPlanArgs) {
  // Storyboard preview (Phase 1 result)
  const [plannedScenes, setPlannedScenes] = useState<Scene[] | null>(null);
  const [imageLookup, setImageLookup] = useState<Record<string, string>>({});
  const [planningEta, setPlanningEta] = useState(0);
  const [planning, setPlanning] = useState(false);

  // Per-scene image swapper modal state
  const [swapImageForScene, setSwapImageForScene] = useState<number | null>(null);
  const [swapMode, setSwapMode] = useState<'library' | 'stock' | 'ai'>('library');
  const [stockQuery, setStockQuery] = useState('');
  const [stockMatches, setStockMatches] = useState<Array<Record<string, unknown>>>([]);
  const [stockSearching, setStockSearching] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);

  // Patch one field of one scene immutably (verbatim @123-125)
  const updateScene = useCallback((idx: number, patch: Scene) => {
    setPlannedScenes((prev) => prev ? prev.map((s, i) => i === idx ? { ...s, ...patch } : s) : prev);
  }, []);

  const runStockSearch = useCallback(async (q: string) => {
    if (!q.trim()) { setStockMatches([]); return; }
    setStockSearching(true);
    try {
      const r = await fetch('/api/video/stock/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q.trim(), count: 8 }),
      });
      if (r.ok) {
        const data = await r.json();
        setStockMatches(data.matches || []);
      } else { setStockMatches([]); }
    } catch { setStockMatches([]); }
    finally { setStockSearching(false); }
  }, []);

  const adoptStock = useCallback(async (match: Record<string, unknown>, sceneIdx: number) => {
    try {
      const r = await fetch('/api/video/stock/adopt', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_url: String(match.image_url || ''),
          description: String(match.description || stockQuery),
          provider: String(match.provider || 'stock'),
          photographer: String(match.photographer || ''),
          photographer_url: String(match.photographer_url || ''),
          width: Number(match.width || 0) || null,
          height: Number(match.height || 0) || null,
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      if (!r.ok) return;
      const asset = await r.json();
      updateScene(sceneIdx, { image_filename: asset.filename });
      setImageLookup((prev) => ({ ...prev, [asset.filename]: asset.url }));
      setSwapImageForScene(null);
      setSwapMode('library');
      setStockMatches([]);
      setStockQuery('');
    } catch { /* noop */ }
  }, [accountId, campaignId, stockQuery, updateScene]);

  const generateAiImage = useCallback(async (prompt: string, sceneIdx: number) => {
    if (!prompt.trim()) return;
    setAiGenerating(true);
    try {
      const r = await fetch('/api/video/stock/ai-generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          aspect_ratio: '16:9',
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      if (!r.ok) {
        let detail = ''; try { const j = await r.json(); detail = j?.detail || ''; } catch { /* noop */ }
        setError(`AI generation failed: ${detail || 'check REPLICATE_API_TOKEN'}`);
        return;
      }
      const asset = await r.json();
      updateScene(sceneIdx, { image_filename: asset.filename });
      setImageLookup((prev) => ({ ...prev, [asset.filename]: asset.url }));
      setSwapImageForScene(null);
      setSwapMode('library');
      setAiPrompt('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'AI generation failed');
    } finally {
      setAiGenerating(false);
    }
  }, [accountId, campaignId, updateScene, setError]);

  // ── Phase 1 — POST /api/video/premium-reel/storyboard-plan (verbatim @465-503) ──
  const planBrandStory = useCallback(async (args: {
    brief: string;
    sourceUrl: string;
    targetSeconds: 30 | 60 | 90;
    overrideSceneCount: number | null;
    selectedImages: Set<string>;
    voiceoverScript: string;
    voiceId?: string;
    useBriefVerbatim: boolean;
  }) => {
    if (!args.brief.trim() && !args.sourceUrl.trim() && args.selectedImages.size === 0) return;
    setPlanning(true);
    setError('');
    setPlannedScenes(null);
    setImageLookup({});
    try {
      const res = await fetch('/api/video/premium-reel/storyboard-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief: args.brief.trim(),
          url: args.sourceUrl.trim() || null,
          target_seconds: args.targetSeconds,
          target_scenes: args.overrideSceneCount,
          image_filenames: Array.from(args.selectedImages),
          voiceover_script: args.voiceoverScript.trim(),
          voice_id: args.voiceId || undefined,
          use_brief_verbatim: args.useBriefVerbatim,
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      if (!res.ok) {
        let detail = '';
        try { const j = await res.json(); detail = typeof j?.detail === 'string' ? j.detail : JSON.stringify(j?.detail); } catch { /* noop */ }
        throw new Error(`HTTP ${res.status}${detail ? ` — ${detail}` : ''}`);
      }
      const data = await res.json();
      setPlannedScenes(data.scenes || []);
      setImageLookup(data.image_lookup || {});
      setPlanningEta(data.estimated_render_seconds || 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Storyboard planning failed');
    } finally {
      setPlanning(false);
    }
  }, [accountId, campaignId, setError]);

  // ── Phase 2 — POST /api/video/premium-reel/storyboard-render (verbatim @506-545) ──
  const renderPlannedStoryboard = useCallback(async (args: {
    brief: string;
    targetSeconds: 30 | 60 | 90;
    voiceoverScript: string;
    voiceId?: string;
    musicFilename?: string | null;
  }) => {
    if (!plannedScenes || plannedScenes.length === 0) return;
    setRendering(true);
    setError('');
    setStage('render');
    setStageMsg('Sending storyboard to render…');
    try {
      // Auto-sync audio to scene timing whenever a voice is selected (verbatim).
      const syncAudioToScenes = !!args.voiceId;
      const res = await fetch('/api/video/premium-reel/storyboard-render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenes: plannedScenes,
          voiceover_script: args.voiceoverScript.trim(),
          voice_id: args.voiceId || undefined,
          music_filename: args.musicFilename || undefined,
          sync_audio_to_scenes: syncAudioToScenes,
          quality: 'draft',
          parallel_workers: 2,
          brief: args.brief.trim(),
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      const summary = args.brief.trim() || `Brand Story · ${args.targetSeconds}s · ${plannedScenes.length} scenes`;
      await consumeStream(res, summary, undefined);
      setPlannedScenes(null);
      setImageLookup({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [plannedScenes, accountId, campaignId, consumeStream, setRendering, setStage, setStageMsg, setError]);

  return {
    plannedScenes, setPlannedScenes, imageLookup, setImageLookup, planningEta, planning,
    updateScene,
    // image swap modal
    swapImageForScene, setSwapImageForScene, swapMode, setSwapMode,
    stockQuery, setStockQuery, stockMatches, stockSearching, runStockSearch, adoptStock,
    aiPrompt, setAiPrompt, aiGenerating, generateAiImage,
    // phases
    planBrandStory, renderPlannedStoryboard,
  };
}
