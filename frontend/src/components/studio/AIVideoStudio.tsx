/**
 * AIVideoStudio — the composing PAGE for the AI Video Studio workspace
 * (Epic B + the Video Director dock, Epic C4). It owns:
 *   - the project row state (synced to the server via create/patch)
 *   - the accumulated SSE event array + the streamTurn subscription lifecycle
 *   - the audio / brand-avatar selections used by the render payload
 * and threads setters/callbacks down to the rail, canvas and dock. The DB row
 * is the source of truth: a refresh mid-edit loses nothing.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useClientAccountId } from '@/hooks/useClientAccountId';
import { useModelCatalog } from '@/components/video/ModelPicker';
import {
  studioBalance,
  studioAuthStatus,
  createVideoProject,
  draftVideoProject,
  patchVideoProject,
  getVideoProject,
  fetchActiveTurns,
  fetchCampaigns,
  streamTurn,
  stopTurn,
  type Storyboard,
  type StudioAuthStatus,
  type StudioModelInfo,
  type VideoProject,
} from '@/lib/api';
import type { OrchestrationEvent } from '@/types/orchestration';
import { useDebouncedCallback } from './aivideo/shared';
import SetupRail from './aivideo/SetupRail';
import StoryboardCanvas from './aivideo/StoryboardCanvas';
import DirectorDock from './aivideo/DirectorDock';
import ModelGallerySheet from './aivideo/ModelGallerySheet';
import type { AudioState, AvatarState, BriefSourceType } from './aivideo/types';

const DEFAULT_TARGET = 30;
const DEFAULT_ASPECT = '16:9';

export default function AIVideoStudio() {
  const navigate = useNavigate();
  const { projectId } = useParams(); // forward-compat: usually undefined
  const accountId = useClientAccountId();
  const { models: catalog } = useModelCatalog('video');

  // ── credits pill ───────────────────────────────────────────────────
  const [credits, setCredits] = useState<number | null>(null);
  useEffect(() => {
    let cancelled = false;
    const load = () =>
      studioBalance()
        .then((b) => { if (!cancelled) setCredits(b.credits); })
        .catch(() => { /* keep last value */ });
    load();
    const h = window.setInterval(load, 60_000);
    return () => { cancelled = true; window.clearInterval(h); };
  }, []);

  // ── Higgsfield auth pre-flight ─────────────────────────────────────
  // Gate Render behind a live login check so we never click users into a
  // guaranteed failure. Always 200; logged_in=false + error_class="auth"
  // means the CLI is logged out.
  const [authStatus, setAuthStatus] = useState<StudioAuthStatus | null>(null);
  useEffect(() => {
    let cancelled = false;
    studioAuthStatus()
      .then((s) => { if (!cancelled) setAuthStatus(s); })
      .catch(() => { /* leave null → treated as OK; render surfaces real errors */ });
    return () => { cancelled = true; };
  }, []);

  // ── project state ──────────────────────────────────────────────────
  const [project, setProject] = useState<VideoProject | null>(null);
  const [modelId, setModelId] = useState<string>('');
  const [targetSeconds, setTargetSeconds] = useState<number>(DEFAULT_TARGET);
  const [aspect, setAspect] = useState<string>(DEFAULT_ASPECT);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [consultDirector, setConsultDirector] = useState<boolean>(false);
  const [brief, setBrief] = useState<string>('');
  const [briefSourceType, setBriefSourceType] = useState<BriefSourceType>('text');
  const [landingUrl, setLandingUrl] = useState<string>('');
  const [draftError, setDraftError] = useState<string | null>(null);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [audio, setAudio] = useState<AudioState>({
    musicOn: false, musicFilename: null, voOn: false, voiceId: null,
  });
  const [avatar, setAvatar] = useState<AvatarState>({ soulId: null, voiceId: null });

  const modelInfo: StudioModelInfo | undefined = catalog.find((m) => m.id === modelId);

  // Seed a default model once the catalog lands.
  useEffect(() => {
    if (modelId || !catalog.length) return;
    setModelId((catalog.find((m) => m.default) ?? catalog[0]).id);
  }, [catalog, modelId]);

  // ── SSE event array + subscription lifecycle ───────────────────────
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);
  const [turnRunning, setTurnRunning] = useState(false);
  const cursorRef = useRef<number>(0);
  const abortRef = useRef<AbortController | null>(null);
  const activeTurnRef = useRef<string | null>(null);

  const subscribe = useCallback((convId: string, turnId: string, cursor: number) => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    activeTurnRef.current = turnId;
    streamTurn(convId, turnId, cursor, {
      signal: ac.signal,
      onEvent: (ev) => {
        setEvents((prev) => [...prev, ev]);
        cursorRef.current = Math.max(cursorRef.current, ev.seq ?? 0);
        if (ev.type === 'storyboard') {
          setStoryboard(ev.payload as unknown as Storyboard);
        }
        if (ev.type === 'turn_done' || ev.type === 'turn_stopped' || ev.type === 'turn_error') {
          setTurnRunning(false);
        }
      },
    }).catch(() => { /* abort/network — ignore; reconnect covers it */ });
  }, []);

  // Start a NEW turn: clear events, reset cursor, mark running, subscribe @0.
  const startTurn = useCallback((convId: string, turnId: string) => {
    setEvents([]);
    cursorRef.current = 0;
    setTurnRunning(true);
    subscribe(convId, turnId, 0);
  }, [subscribe]);

  // ── hydrate: deep-link OR fresh ────────────────────────────────────
  const hydrateFromRow = useCallback((row: VideoProject) => {
    setProject(row);
    setModelId(row.model_id);
    setTargetSeconds(row.target_seconds);
    setAspect(row.aspect);
    setCampaignId(row.campaign_id);
    setConsultDirector(row.consult_director === 1);
    setBrief(row.brief ?? '');
    setStoryboard(row.storyboard_json);
  }, []);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    getVideoProject(projectId)
      .then((row) => {
        if (cancelled) return;
        hydrateFromRow(row);
        // resume any active turn for this conversation
        return fetchActiveTurns(row.conversation_id).then((turns) => {
          if (cancelled) return;
          const t = turns[0];
          if (t) {
            setEvents([]);
            cursorRef.current = t.cursor ?? 0;
            setTurnRunning(true);
            subscribe(row.conversation_id, t.turn_id, t.cursor ?? 0);
          }
        });
      })
      .catch(() => { /* deep-link miss — stay on empty state */ });
    return () => { cancelled = true; abortRef.current?.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => () => abortRef.current?.abort(), []);

  // ── project CRUD ───────────────────────────────────────────────────
  // Ensure a row exists before a meaningful action; returns the fresh/known row.
  const ensureProject = useCallback(async (): Promise<VideoProject> => {
    if (project) return project;
    let campaignName: string | undefined;
    if (campaignId && accountId) {
      const list = await fetchCampaigns(accountId).catch(() => []);
      campaignName = list.find((c) => c.id === campaignId)?.name;
    }
    const row = await createVideoProject({
      account_id: accountId,
      campaign_id: campaignId,
      campaign_name: campaignName,
      brief,
      model_id: modelId,
      target_seconds: targetSeconds,
      aspect,
    });
    setProject(row);
    // server sets consult_director (1 if campaign_id else 0)
    setConsultDirector(row.consult_director === 1);
    // Make the URL the source of truth: once a row exists, deep-link to it so a
    // refresh at /studio/ai-video/{id} rehydrates from the DB (replace so the
    // bare /studio/ai-video entry stays out of the back-button history).
    navigate(`/studio/ai-video/${row.id}`, { replace: true });
    return row;
  }, [project, campaignId, accountId, brief, modelId, targetSeconds, aspect, navigate]);

  // Debounced patch of scalar edits once a row exists.
  const debouncedPatch = useDebouncedCallback(
    (patch: Parameters<typeof patchVideoProject>[1]) => {
      if (!project) return;
      patchVideoProject(project.id, patch)
        .then((row) => setProject(row))
        .catch(() => { /* transient */ });
    },
    600,
  );

  // Debounced storyboard persist (600ms per brief).
  const debouncedStoryboardPatch = useDebouncedCallback((sb: Storyboard) => {
    if (!project) return;
    patchVideoProject(project.id, { storyboard_json: sb }).catch(() => { /* transient */ });
  }, 600);

  // ── rail callbacks ─────────────────────────────────────────────────
  const onCampaignChange = useCallback((id: string | null) => {
    setCampaignId(id);
    setConsultDirector(!!id); // consult defaults ON when a campaign links
    if (!project) return;
    // Changing to a DIFFERENT non-null campaign spawns a fresh conversation.
    patchVideoProject(project.id, { campaign_id: id })
      .then((row) => {
        setProject(row);
        if (row.conversation_id !== project.conversation_id) {
          // re-read + re-subscribe to any active turn on the new conversation
          fetchActiveTurns(row.conversation_id)
            .then((turns) => {
              const t = turns[0];
              setEvents([]);
              cursorRef.current = 0;
              if (t) { setTurnRunning(true); subscribe(row.conversation_id, t.turn_id, t.cursor ?? 0); }
              else setTurnRunning(false);
            })
            .catch(() => { /* nothing active */ });
        }
      })
      .catch(() => { /* transient */ });
  }, [project, subscribe]);

  const onConsultChange = useCallback((v: boolean) => {
    setConsultDirector(v);
    debouncedPatch({ consult_director: v ? 1 : 0 });
  }, [debouncedPatch]);

  const onTargetChange = useCallback((s: number) => {
    setTargetSeconds(s);
    debouncedPatch({ target_seconds: s });
  }, [debouncedPatch]);

  const onAspectChange = useCallback((a: string) => {
    setAspect(a);
    debouncedPatch({ aspect: a });
  }, [debouncedPatch]);

  const onBriefChange = useCallback((b: string) => {
    setBrief(b);
    debouncedPatch({ brief: b });
  }, [debouncedPatch]);

  // ── model gallery ──────────────────────────────────────────────────
  const [galleryOpen, setGalleryOpen] = useState(false);
  const onPickModel = useCallback((m: StudioModelInfo) => {
    setModelId(m.id);
    // clamp each scene's duration to the new model's legal set
    let clampedSb: Storyboard | null = null;
    if (storyboard) {
      const c = m.constraints;
      const clamp = (d: number): number => {
        if (c.duration_type === 'enum' && c.durations?.length) {
          return c.durations.reduce(
            (best, cur) => (Math.abs(cur - d) < Math.abs(best - d) ? cur : best),
            c.durations[0],
          );
        }
        if (c.duration_type === 'int' && c.max_duration) return Math.min(d, c.max_duration);
        return d;
      };
      clampedSb = { ...storyboard, scenes: storyboard.scenes.map((s) => ({ ...s, duration: clamp(s.duration) })) };
      setStoryboard(clampedSb);
    }
    if (project) {
      patchVideoProject(project.id, {
        model_id: m.id,
        ...(clampedSb ? { storyboard_json: clampedSb } : {}),
      })
        .then((row) => setProject(row))
        .catch(() => { /* transient */ });
    }
  }, [storyboard, project]);

  // ── draft / angle / iterate ────────────────────────────────────────
  const onDraft = useCallback(async () => {
    setDraftError(null);
    try {
      const row = await ensureProject();
      const briefSource =
        briefSourceType === 'campaign'
          ? { type: 'campaign' as const }
          : briefSourceType === 'landing_page'
            ? { type: 'landing_page' as const, url: landingUrl.trim() }
            : undefined; // "text" → omit (legacy default)
      const { turn_id } = await draftVideoProject(row.id, undefined, briefSource); // empty message → concepts
      startTurn(row.conversation_id, turn_id);
    } catch (e) {
      // Surface the API error message inline (e.g. 400: campaign/url missing).
      const raw = e instanceof Error ? e.message : 'Draft failed to start.';
      setDraftError(raw.replace(/^API error \d+:\s*/, '').trim() || 'Draft failed to start.');
    }
  }, [ensureProject, startTurn, briefSourceType, landingUrl]);

  const onPickAngle = useCallback(async (angle: string) => {
    if (!project) return;
    const { turn_id } = await draftVideoProject(project.id, `angle:${angle}`);
    startTurn(project.conversation_id, turn_id);
  }, [project, startTurn]);

  const onSendIteration = useCallback(async (message: string) => {
    if (!project) return;
    const { turn_id } = await draftVideoProject(project.id, message);
    startTurn(project.conversation_id, turn_id);
  }, [project, startTurn]);

  const onStop = useCallback(() => {
    if (!project || !activeTurnRef.current) return;
    stopTurn(project.conversation_id, activeTurnRef.current).catch(() => { /* best effort */ });
    setTurnRunning(false);
  }, [project]);

  // ── storyboard edits from the canvas ───────────────────────────────
  const onStoryboardChange = useCallback((next: Storyboard) => {
    setStoryboard(next);
    debouncedStoryboardPatch(next);
  }, [debouncedStoryboardPatch]);

  const onRendered = useCallback((assetId: string) => {
    if (!project) return;
    patchVideoProject(project.id, { status: 'rendered', asset_id: assetId })
      .then((row) => setProject(row))
      .catch(() => { /* transient */ });
  }, [project]);

  // ── new video / reset ──────────────────────────────────────────────
  // The ONLY explicit reset affordance. Per product owner: the page resets on
  // "New video"/reset and nothing else. Aborts any live stream, drops the URL
  // id (bare /studio/ai-video), and clears every piece of local state back to
  // its first-load default so the workspace is a clean slate.
  const onNewVideo = useCallback(() => {
    abortRef.current?.abort();
    activeTurnRef.current = null;
    cursorRef.current = 0;
    navigate('/studio/ai-video');
    setProject(null);
    setModelId((catalog.find((m) => m.default) ?? catalog[0])?.id ?? '');
    setTargetSeconds(DEFAULT_TARGET);
    setAspect(DEFAULT_ASPECT);
    setCampaignId(null);
    setConsultDirector(false);
    setBrief('');
    setBriefSourceType('text');
    setLandingUrl('');
    setDraftError(null);
    setStoryboard(null);
    setAudio({ musicOn: false, musicFilename: null, voOn: false, voiceId: null });
    setAvatar({ soulId: null, voiceId: null });
    setEvents([]);
    setTurnRunning(false);
  }, [navigate, catalog]);

  // ── dock collapse ──────────────────────────────────────────────────
  const [dockCollapsed, setDockCollapsed] = useState(false);

  const hasStoryboard = !!storyboard && storyboard.scenes.length > 0;

  // Retryable draft-stage timeout (CHANGE 1): the backend emits a structured
  // turn_error with retryable:true + stage:"draft-timeout". When the last
  // turn_error is that shape and no turn is running, the dock offers Retry —
  // which re-fires the exact same draft POST (onDraft, same brief_source).
  const retryableDraftTimeout = !turnRunning && (() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === 'turn_error') {
        const p = events[i].payload as { retryable?: boolean; stage?: string };
        return p.retryable === true && p.stage === 'draft-timeout';
      }
    }
    return false;
  })();

  return (
    <div className="flex h-full flex-col">
      {/* header */}
      <div className="flex items-center gap-3 border-b border-border bg-surface px-5 py-3">
        <button
          onClick={() => navigate('/studio')}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-2 hover:text-text"
        >
          <ArrowLeft className="h-4 w-4" /> Studio
        </button>
        <h1 className="text-sm font-semibold uppercase tracking-wide text-text">AI Video Studio</h1>
        <button
          onClick={onNewVideo}
          className="ml-auto flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-2 hover:text-text"
          title="Start a fresh video project. Clears the workspace and drops the current project from the URL."
        >
          <Plus className="h-3.5 w-3.5" /> New video
        </button>
        <span
          className={cn(
            'rounded border px-2 py-1 font-mono text-[10px]',
            credits === null
              ? 'border-border text-muted-foreground'
              : credits < 50
                ? 'border-danger/40 bg-danger-soft text-danger'
                : credits < 200
                  ? 'border-warning/40 bg-warning-soft text-warning'
                  : 'border-success/30 bg-success-soft text-success',
          )}
          title="Your Higgsfield credit balance. Refreshes every 60s."
        >
          {credits ?? '—'} credits
        </span>
      </div>

      {/* three-zone body */}
      <div className="flex min-h-0 flex-1">
        <SetupRail
          accountId={accountId}
          campaignId={campaignId}
          onCampaignChange={onCampaignChange}
          consultDirector={consultDirector}
          onConsultChange={onConsultChange}
          modelId={modelId}
          modelInfo={modelInfo}
          onOpenGallery={() => setGalleryOpen(true)}
          targetSeconds={targetSeconds}
          onTargetChange={onTargetChange}
          aspect={aspect}
          onAspectChange={onAspectChange}
          audio={audio}
          onAudioChange={(patch) => setAudio((a) => ({ ...a, ...patch }))}
          avatar={avatar}
          onAvatarChange={(patch) => setAvatar((a) => ({ ...a, ...patch }))}
          brief={brief}
          onBriefChange={onBriefChange}
          briefSourceType={briefSourceType}
          onBriefSourceTypeChange={setBriefSourceType}
          landingUrl={landingUrl}
          onLandingUrlChange={setLandingUrl}
          draftError={draftError}
          hasStoryboard={hasStoryboard}
          drafting={turnRunning && !hasStoryboard}
          onDraft={onDraft}
        />

        {hasStoryboard && storyboard ? (
          <StoryboardCanvas
            storyboard={storyboard}
            onStoryboardChange={onStoryboardChange}
            accountId={accountId}
            campaignId={campaignId}
            projectModelId={modelId}
            modelInfo={modelInfo}
            catalog={catalog}
            aspect={aspect}
            targetSeconds={targetSeconds}
            audio={audio}
            avatar={avatar}
            authStatus={authStatus}
            onRendered={onRendered}
          />
        ) : (
          <div className="flex min-w-0 flex-1 items-center justify-center px-6">
            <div className="max-w-[360px] text-center">
              <p className="text-sm font-medium text-text">No storyboard yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Write a brief on the left and draft with the Director. The storyboard lands here.
              </p>
            </div>
          </div>
        )}

        <DirectorDock
          events={events}
          turnRunning={turnRunning}
          collapsed={dockCollapsed}
          onToggleCollapse={() => setDockCollapsed((c) => !c)}
          onPickAngle={onPickAngle}
          onSend={onSendIteration}
          onStop={onStop}
          retryableDraftTimeout={retryableDraftTimeout}
          onRetryDraft={onDraft}
        />
      </div>

      <ModelGallerySheet
        open={galleryOpen}
        currentId={modelId}
        targetSeconds={targetSeconds}
        onClose={() => setGalleryOpen(false)}
        onPick={onPickModel}
      />
    </div>
  );
}
