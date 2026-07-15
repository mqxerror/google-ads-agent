/**
 * StoryboardCanvas — the fluid center column. Renders the SceneCard list plus a
 * footer cost gate. Scene edits debounce up to the page's persist; the cost
 * total debounces a videoEngineEstimate call; Render fires videoEngineRender
 * (Appendix-B payload) and polls videoEngineRenderStatus every 3s. No live
 * Higgsfield call is made here beyond the button-wired render.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Plus, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  videoEngineEstimate,
  videoEngineRender,
  videoEngineRenderStatus,
  type Storyboard,
  type StoryboardScene,
  type StudioAuthStatus,
  type StudioModelInfo,
  type VideoEngineSegment,
} from '@/lib/api';
import { useClipMath } from '@/components/studio/useClipMath';
import { isSoulCapable, useDebouncedCallback } from './shared';
import SceneCard from './SceneCard';
import type { AudioState, AvatarState } from './types';

const MAX_SCENES = 8;

interface StoryboardCanvasProps {
  storyboard: Storyboard;
  onStoryboardChange: (next: Storyboard) => void;
  accountId: string;
  campaignId: string | null;
  projectModelId: string;
  modelInfo: StudioModelInfo | undefined;
  catalog: StudioModelInfo[];
  aspect: string;
  targetSeconds: number;
  audio: AudioState;
  avatar: AvatarState;
  /** Higgsfield CLI login pre-flight; null = unknown (treated as OK). */
  authStatus: StudioAuthStatus | null;
  onRendered: (assetId: string) => void;
}

export default function StoryboardCanvas({
  storyboard,
  onStoryboardChange,
  accountId,
  campaignId,
  projectModelId,
  modelInfo,
  catalog,
  aspect,
  targetSeconds,
  audio,
  avatar,
  authStatus,
  onRendered,
}: StoryboardCanvasProps) {
  // Auth dead → block render; never click users into a guaranteed failure.
  const authDead = authStatus?.logged_in === false;
  const scenes = storyboard.scenes;
  const { clampDuration } = useClipMath(modelInfo, targetSeconds);

  // ── cost estimate (debounced) ──────────────────────────────────────
  // 'idle' before the first result, 'ok' with a real number, 'failed' when the
  // estimate call errored. We NEVER render a literal 0 from a failed estimate —
  // failure shows "Cost estimate unavailable" and the button drops the number.
  const [estimate, setEstimate] = useState<{ total: number; unknown: number } | null>(null);
  const [costState, setCostState] = useState<'idle' | 'ok' | 'failed'>('idle');
  const runEstimate = useDebouncedCallback((sb: Storyboard) => {
    if (!sb.scenes.length) {
      setEstimate(null);
      setCostState('idle');
      return;
    }
    videoEngineEstimate({
      scenes: sb.scenes.map((s) => ({
        prompt: s.visual_prompt,
        model: s.model ?? projectModelId,
        duration: s.duration,
      })),
      aspect,
      target_seconds: targetSeconds,
      model_id: projectModelId,
    })
      .then((r) => { setEstimate({ total: r.total_credits, unknown: r.unknown_count }); setCostState('ok'); })
      .catch(() => { setEstimate(null); setCostState('failed'); });
  }, 500);

  useEffect(() => {
    runEstimate(storyboard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyboard, aspect, targetSeconds, projectModelId]);

  // Numeric label ONLY when we have a real estimate; else null (never "0").
  const totalLabel = useMemo<string | null>(() => {
    if (costState !== 'ok' || !estimate) return null;
    return estimate.unknown > 0 ? `${estimate.total}+` : `${estimate.total}`;
  }, [costState, estimate]);

  // ── scene mutations ────────────────────────────────────────────────
  function patchScene(idx: number, patch: Partial<StoryboardScene>) {
    const next = { ...storyboard, scenes: scenes.map((s, i) => (i === idx ? { ...s, ...patch } : s)) };
    onStoryboardChange(next);
  }
  function deleteScene(idx: number) {
    const next = {
      ...storyboard,
      scenes: scenes.filter((_, i) => i !== idx).map((s, i) => ({ ...s, n: i + 1 })),
    };
    onStoryboardChange(next);
  }
  function moveScene(idx: number, dir: -1 | 1) {
    const j = idx + dir;
    if (j < 0 || j >= scenes.length) return;
    const arr = [...scenes];
    const [row] = arr.splice(idx, 1);
    arr.splice(j, 0, row);
    onStoryboardChange({ ...storyboard, scenes: arr.map((s, i) => ({ ...s, n: i + 1 })) });
  }
  function addScene() {
    if (scenes.length >= MAX_SCENES) return;
    const dur = clampDuration(modelInfo?.constraints.durations?.[0] ?? 6);
    const newScene: StoryboardScene = {
      n: scenes.length + 1,
      duration: dur,
      visual_prompt: '',
      vo_line: '',
    };
    onStoryboardChange({ ...storyboard, scenes: [...scenes, newScene] });
  }

  // ── render + poll ──────────────────────────────────────────────────
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobMsg, setJobMsg] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [renderedAssetId, setRenderedAssetId] = useState<string | null>(null);

  async function handleRender() {
    if (authDead) return; // pre-flight: CLI logged out, don't even try
    setJobError(null);
    setRenderedAssetId(null);
    // Appendix B — segment timeline (per-scene speak stays empty; whole-track VO).
    const segments: VideoEngineSegment[] = scenes.map((s) => {
      const seg: VideoEngineSegment = {
        engine: 'higgsfield',
        prompt: s.visual_prompt,
        model: s.model ?? projectModelId,
        duration: s.duration,
        speak: '',
      };
      // thread soul into soul-capable segments where relevant
      const segModel = catalog.find((m) => m.id === (s.model ?? projectModelId));
      if (avatar.soulId && isSoulCapable(segModel)) seg.soul_id = avatar.soulId;
      return seg;
    });
    try {
      const { job_id } = await videoEngineRender({
        account_id: accountId,
        segments,
        voice_id: audio.voOn ? audio.voiceId ?? undefined : undefined,
        music_filename: audio.musicOn ? audio.musicFilename ?? undefined : undefined,
        voiceover_script: audio.voOn ? storyboard.vo_full : undefined,
        aspect,
        campaign_id: campaignId ?? undefined,
        quality: 'draft',
      });
      setJobId(job_id);
      setJobMsg('Starting render...');
    } catch (e) {
      setJobError(e instanceof Error ? e.message : 'render failed to start');
    }
  }

  // poll — mirrors StudioPanel lines 495-525 (20-min guard, 3s tick)
  const onRenderedRef = useRef(onRendered);
  onRenderedRef.current = onRendered;
  useEffect(() => {
    if (!jobId) return;
    const startedAt = Date.now();
    let cancelled = false;
    const handle = window.setInterval(async () => {
      if (cancelled) return;
      if (Date.now() - startedAt > 20 * 60_000) {
        setJobId(null);
        setJobMsg(null);
        setJobError('Render timed out after 20 minutes - check the Library; it may still finish.');
        return;
      }
      try {
        const job = await videoEngineRenderStatus(jobId);
        if (cancelled) return;
        if (job.status === 'done' && job.asset_id) {
          setJobId(null);
          setJobMsg(null);
          setRenderedAssetId(job.asset_id);
          onRenderedRef.current(job.asset_id);
        } else if (job.status === 'error') {
          setJobId(null);
          setJobMsg(null);
          setJobError(job.message || 'render failed');
        } else if (job.message || job.stage) {
          setJobMsg(job.message || job.stage || null);
        }
      } catch {
        // a 404 after the job window means the job record is gone
        if (cancelled) return;
        setJobId(null);
        setJobMsg(null);
        setJobError('job lost - check the Library');
      }
    }, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(handle);
    };
  }, [jobId]);

  const rendering = !!jobId;

  return (
    <div className="flex min-w-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto px-6 py-6">
        <div className="mx-auto max-w-[760px] space-y-3">
          <div className="flex items-center gap-2">
            <p className="label-section">Storyboard</p>
            <span className="font-mono text-[11px] text-subtle">
              {scenes.length} / {MAX_SCENES} scenes
            </span>
          </div>

          {scenes.map((s, i) => (
            <SceneCard
              key={`${s.n}-${i}`}
              scene={s}
              index={i}
              total={scenes.length}
              projectModelId={projectModelId}
              catalog={catalog}
              rendering={rendering}
              posterUrl={null}
              onChange={(patch) => patchScene(i, patch)}
              onDelete={() => deleteScene(i)}
              onMove={(dir) => moveScene(i, dir)}
            />
          ))}

          {scenes.length < MAX_SCENES && (
            <button
              onClick={addScene}
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border py-2.5 text-xs text-muted-foreground transition-colors hover:bg-surface-2"
            >
              <Plus className="h-3.5 w-3.5" /> Add scene
            </button>
          )}

          {renderedAssetId && (
            <div className="space-y-2 rounded-lg border border-border bg-card p-3">
              <p className="text-xs font-medium text-success">Render complete</p>
              <Link
                to={`/studio/c/${renderedAssetId}`}
                className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
              >
                Open in Library <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* progress strip */}
      {(jobMsg || jobError) && (
        <div
          className={cn(
            'border-t border-border px-6 py-2 text-[11px]',
            jobError ? 'bg-danger-soft text-danger' : 'bg-surface-2 text-muted-foreground',
          )}
        >
          {jobError ?? jobMsg}
        </div>
      )}

      {/* auth pre-flight banner — CLI logged out, render is disabled */}
      {authDead && (
        <div className="border-t border-warning/40 bg-warning-soft px-6 py-2.5 text-[11px] text-warning">
          Higgsfield CLI is not logged in on this Mac. Run{' '}
          <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[10.5px] text-text">
            higgsfield auth login
          </code>{' '}
          in Terminal, then retry.
        </div>
      )}

      {/* footer cost gate */}
      <div className="flex items-center gap-3 border-t border-border bg-surface px-6 py-3">
        <span className="font-mono text-xs text-muted-foreground">
          {costState === 'failed'
            ? 'Cost estimate unavailable'
            : totalLabel === null
              ? 'Estimated cost: ... credits'
              : `Estimated cost: ${totalLabel} credits`}
        </span>
        <button
          onClick={handleRender}
          disabled={rendering || scenes.length === 0 || authDead}
          className="ml-auto rounded border border-strong bg-accent px-4 py-2 text-xs font-medium text-on-accent transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {rendering
            ? 'Rendering...'
            : totalLabel === null
              ? 'Render video'
              : `Render video - burns ~${totalLabel} credits`}
        </button>
      </div>
    </div>
  );
}
