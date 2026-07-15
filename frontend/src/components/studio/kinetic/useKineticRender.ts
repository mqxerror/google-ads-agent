/**
 * useKineticRender — the shared SSE render hook for every Kinetic lane.
 *
 * Extracted VERBATIM from the legacy VideoCreator (src/components/chat/
 * VideoCreator.tsx): the `consumeStream` SSE consumer (@548-595) plus the
 * three single-shot render callbacks — avatar-snap (@327-357), brand-reel
 * (@394-428), premium-reel single (@431-462). The request payloads are
 * BYTE-IDENTICAL to the legacy calls so the backend sees exactly what it
 * saw before (plan §7.2, AC D1). Backend is zero-change for Kinetic.
 *
 * The SSE stream shape is unchanged: {type:'status', stage, message} /
 * {type:'done', public_url, thumbnail_url} / {type:'error', message}.
 */

import { useState, useCallback, useEffect, useRef } from 'react';

export type Aspect = '16:9' | '9:16' | '1:1';

// Dims — identical to VideoCreator's ASPECT_DIMS / REEL_DIMS tables.
export const ASPECT_DIMS: Record<Aspect, { width: number; height: number }> = {
  '16:9': { width: 1280, height: 720 },
  '9:16': { width: 720, height: 1280 },
  '1:1':  { width: 1080, height: 1080 },
};

// Brand Reel + Premium Reel render bigger — pure motion graphics.
export const REEL_DIMS: Record<Aspect, { width: number; height: number }> = {
  '16:9': { width: 1920, height: 1080 },
  '9:16': { width: 1080, height: 1920 },
  '1:1':  { width: 1080, height: 1080 },
};

export interface RenderResult {
  url: string;
  script: string;
  thumbnail?: string;
}

export interface KineticRenderState {
  rendering: boolean;
  stage: string;
  stageMsg: string;
  elapsed: number;
  error: string;
  setError: (e: string) => void;
}

export interface UseKineticRenderArgs {
  onVideoReady: (r: RenderResult) => void;
}

/**
 * Shared render state + the three single-shot render POSTs and the SSE
 * consumer. Each render fn returns a promise that resolves after the stream
 * closes (done/error). On `done` it calls onVideoReady with the final asset.
 */
export function useKineticRender({ onVideoReady }: UseKineticRenderArgs) {
  const [rendering, setRendering] = useState(false);
  const [stage, setStage] = useState('');
  const [stageMsg, setStageMsg] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');

  // Elapsed timer while rendering (verbatim from VideoCreator @234-239)
  useEffect(() => {
    if (!rendering) { setElapsed(0); return; }
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(id);
  }, [rendering]);

  const onVideoReadyRef = useRef(onVideoReady);
  onVideoReadyRef.current = onVideoReady;

  // Shared SSE consumer — reads the {type, stage, message, public_url,
  // thumbnail_url, done, error} stream all render endpoints emit.
  // Verbatim logic from VideoCreator.consumeStream (@548-595).
  const consumeStream = useCallback(async (res: Response, scriptForLibrary: string, thumb?: string) => {
    if (!res.ok) {
      let detail = '';
      try {
        const j = await res.clone().json();
        detail = typeof j?.detail === 'string' ? j.detail : JSON.stringify(j?.detail ?? j);
      } catch {
        try { detail = await res.text(); } catch { /* noop */ }
      }
      throw new Error(`HTTP ${res.status}${detail ? ` — ${detail}` : ''}`);
    }
    const reader = res.body?.getReader();
    if (!reader) throw new Error('No response body');
    const decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split('\n');
      buf = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const evt = JSON.parse(line.slice(6));
          if (evt.type === 'status') {
            setStage(evt.stage || '');
            setStageMsg(evt.message || '');
          } else if (evt.type === 'done') {
            onVideoReadyRef.current({
              url: evt.public_url,
              script: scriptForLibrary,
              thumbnail: evt.thumbnail_url || thumb,
            });
            setRendering(false);
            return;
          } else if (evt.type === 'error') {
            setError(evt.message || 'Render failed');
            setRendering(false);
            return;
          }
        } catch { /* ignore partial lines */ }
      }
    }
  }, []);

  // ── Avatar Snap render — POST /api/video/generate (verbatim @327-357) ──
  const renderAvatarSnap = useCallback(async (args: {
    script: string;          // sanitized-spoken text
    voiceId?: string;
    avatarId?: string;
    talkingPhotoId?: string | null;
    aspect: Aspect;
    accountId?: string;
    campaignId?: string | null;
    soulId?: string | null;  // Brand Avatar picker — supplies a consistent face soul_id
  }) => {
    const toSpeak = args.script.trim();
    if (!toSpeak) return;
    setRendering(true);
    setError('');
    setStage('tts');
    setStageMsg('Starting…');
    const dims = ASPECT_DIMS[args.aspect];
    const useTalkingPhoto = !!args.talkingPhotoId;
    try {
      const res = await fetch('/api/video/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: toSpeak,
          voice_id: args.voiceId || undefined,
          avatar_id: useTalkingPhoto ? args.talkingPhotoId : (args.avatarId || undefined),
          character_type: useTalkingPhoto ? 'talking_photo' : 'avatar',
          width: dims.width,
          height: dims.height,
          account_id: args.accountId,
          campaign_id: args.campaignId,
          // §13 default: Brand Avatar's soul_id stamps a consistent face for
          // the presenter render. The pipeline stays still→motion→TTS bed
          // (non-lipsync); soul_id only supplies identity. Additive field —
          // the backend ignores it until AVATAR_SPEAK_MODEL (a lipsync model)
          // ships. See backend/app/services/video_director.py AVATAR_SPEAK_MODEL.
          soul_id: args.soulId || undefined,
        }),
      });
      await consumeStream(res, toSpeak, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [consumeStream]);

  // ── Brand Reel render — POST /api/video/brand-reel (verbatim @394-428) ──
  const renderBrandReel = useCallback(async (args: {
    headline: string;
    subhead: string;
    statValue: string;
    statLabel: string;
    cta: string;
    voiceoverScript: string;
    brollUrl: string | null;
    voiceId?: string;
    aspect: Aspect;
    reelDuration: 15 | 30;
    accountId?: string;
    campaignId?: string | null;
  }) => {
    if (!args.headline.trim()) return;
    setRendering(true);
    setError('');
    setStage('scene1');
    setStageMsg('Starting…');
    const dims = REEL_DIMS[args.aspect];
    const summary = [args.headline.trim(), args.subhead.trim(), args.cta.trim()].filter(Boolean).join(' — ');
    try {
      const res = await fetch('/api/video/brand-reel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: args.headline.trim(),
          subhead: args.subhead.trim(),
          stat_value: args.statValue.trim(),
          stat_label: args.statLabel.trim(),
          cta: args.cta.trim(),
          voiceover_script: args.voiceoverScript.trim(),
          b_roll_url: args.brollUrl,
          voice_id: args.voiceId || undefined,
          width: dims.width,
          height: dims.height,
          duration_s: args.reelDuration,
          account_id: args.accountId,
          campaign_id: args.campaignId,
        }),
      });
      await consumeStream(res, summary, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [consumeStream]);

  // ── Premium Reel single — POST /api/video/premium-reel (verbatim @431-462) ──
  const renderPremiumReel = useCallback(async (args: {
    headline: string;
    subhead: string;
    statValue: string;
    statLabel: string;
    cta: string;
    voiceoverScript: string;
    voiceId?: string;
    musicFilename?: string | null;
    accountId?: string;
    campaignId?: string | null;
  }) => {
    if (!args.headline.trim()) return;
    setRendering(true);
    setError('');
    setStage('scene1');
    setStageMsg('Starting Hyperframes render (60-90s)…');
    const summary = [args.headline.trim(), args.subhead.trim(), args.cta.trim()].filter(Boolean).join(' — ');
    try {
      const res = await fetch('/api/video/premium-reel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: args.headline.trim(),
          subhead: args.subhead.trim(),
          stat_value: args.statValue.trim(),
          stat_label: args.statLabel.trim(),
          cta: args.cta.trim(),
          voiceover_script: args.voiceoverScript.trim(),
          voice_id: args.voiceId || undefined,
          music_filename: args.musicFilename || undefined,
          quality: 'draft',
          account_id: args.accountId,
          campaign_id: args.campaignId,
        }),
      });
      await consumeStream(res, summary, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [consumeStream]);

  return {
    // state
    rendering, stage, stageMsg, elapsed, error, setError,
    // renders
    renderAvatarSnap, renderBrandReel, renderPremiumReel,
    // low-level (Brand Story render reuses this directly)
    consumeStream, setRendering, setStage, setStageMsg,
  };
}
