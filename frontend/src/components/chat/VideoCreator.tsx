import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { Film, X, Loader2, Sparkles, AlertTriangle, Camera, Upload, Image as ImageIcon, Wand2, Link as LinkIcon, Folder } from 'lucide-react';
import { cn } from '@/lib/utils';
import { sanitizeScript } from '@/lib/scriptSanitizer';

interface VideoCreatorProps {
  open: boolean;
  onClose: () => void;
  onVideoReady: (url: string, script: string, thumbnail?: string) => void;
  initialScript?: string;
  accountId?: string;
  campaignId?: string | null;
}

interface AvatarOption {
  avatar_id: string;
  name: string;
  preview_image_url?: string;
}

interface VoiceOption {
  voice_id: string;
  name: string;
  labels?: Record<string, string>;
}

type Aspect = '16:9' | '9:16' | '1:1';
type Mode = 'avatar-snap' | 'brand-reel' | 'premium-reel';
type PremiumSubMode = 'single' | 'storyboard';

const ASPECT_DIMS: Record<Aspect, { width: number; height: number }> = {
  '16:9': { width: 1280, height: 720 },
  '9:16': { width: 720, height: 1280 },
  '1:1':  { width: 1080, height: 1080 },
};

// Brand Reel renders bigger by default since it's pure motion graphics
const REEL_DIMS: Record<Aspect, { width: number; height: number }> = {
  '16:9': { width: 1920, height: 1080 },
  '9:16': { width: 1080, height: 1920 },
  '1:1':  { width: 1080, height: 1080 },
};

interface LibraryImage {
  id: string;
  filename: string;
  url: string;
  source: string;
  width?: number;
  height?: number;
}

const WORDS_PER_SEC = 2.5;

export default function VideoCreator({ open, onClose, onVideoReady, initialScript, accountId, campaignId }: VideoCreatorProps) {
  const [mode, setMode] = useState<Mode>('avatar-snap');

  // ─── Shared state ───
  const [aspect, setAspect] = useState<Aspect>('16:9');
  const [rendering, setRendering] = useState(false);
  const [stage, setStage] = useState<string>('');
  const [stageMsg, setStageMsg] = useState<string>('');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string>('');

  // ─── Avatar Snap state ───
  const [script, setScript] = useState(initialScript ?? '');
  const [avatars, setAvatars] = useState<AvatarOption[]>([]);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [avatarId, setAvatarId] = useState<string>('');
  const [voiceId, setVoiceId] = useState<string>('');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [talkingPhotoId, setTalkingPhotoId] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);

  // ─── Brand Reel state ───
  const [headline, setHeadline] = useState('');
  const [subhead, setSubhead] = useState('');
  const [statValue, setStatValue] = useState('');
  const [statLabel, setStatLabel] = useState('');
  const [cta, setCta] = useState('Book a free consultation');
  const [voiceoverScript, setVoiceoverScript] = useState('');
  const [brollUrl, setBrollUrl] = useState<string | null>(null);
  const [brollFilename, setBrollFilename] = useState<string | null>(null);
  const [showBrollPicker, setShowBrollPicker] = useState(false);
  const [libraryImages, setLibraryImages] = useState<LibraryImage[]>([]);
  const [libraryLoading, setLibraryLoading] = useState(false);
  const [reelDuration, setReelDuration] = useState<15 | 30>(15);
  // Scene auto-fill brief + state
  const [brief, setBrief] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [autoFilling, setAutoFilling] = useState(false);
  const [autoFillError, setAutoFillError] = useState('');

  // ─── Brand Story (Premium Reel storyboard) ───
  const [premiumSubMode, setPremiumSubMode] = useState<PremiumSubMode>('single');
  const [targetSeconds, setTargetSeconds] = useState<30 | 60 | 90>(60);
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [showStoryboardPicker, setShowStoryboardPicker] = useState(false);
  // When true, the brief text is used VERBATIM as scene captions (no Director
  // rewriting). For legal/regulated copy where the exact wording cannot be
  // paraphrased.
  const [useBriefVerbatim, setUseBriefVerbatim] = useState(false);
  // User can override the recommended scene count (null = auto from duration).
  const [overrideSceneCount, setOverrideSceneCount] = useState<number | null>(null);
  // Storyboard preview (Phase 1 result, shown before render)
  const [plannedScenes, setPlannedScenes] = useState<Array<Record<string, unknown>> | null>(null);
  const [imageLookup, setImageLookup] = useState<Record<string, string>>({});
  const [planningEta, setPlanningEta] = useState(0);
  const [planning, setPlanning] = useState(false);
  // Per-scene image swapper modal — when set, opens the image picker and applies the choice to scene index N
  const [swapImageForScene, setSwapImageForScene] = useState<number | null>(null);
  // Image picker modal mode: 'library' | 'stock' | 'ai'
  const [swapMode, setSwapMode] = useState<'library' | 'stock' | 'ai'>('library');
  const [stockQuery, setStockQuery] = useState('');
  const [stockMatches, setStockMatches] = useState<Array<Record<string, unknown>>>([]);
  const [stockSearching, setStockSearching] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);

  // Helper — patch one field of one scene immutably (used by all editors below)
  const updateScene = useCallback((idx: number, patch: Record<string, unknown>) => {
    setPlannedScenes((prev) => prev ? prev.map((s, i) => i === idx ? { ...s, ...patch } : s) : prev);
  }, []);

  // Helper — detect "logo" library images so we can flag them in pickers
  const isLogoFilename = (name: string) => /(^|[^a-z])logo([^a-z]|$)/i.test(name);

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
      } else {
        setStockMatches([]);
      }
    } catch {
      setStockMatches([]);
    } finally {
      setStockSearching(false);
    }
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
    } catch {}
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
        let detail = ''; try { const j = await r.json(); detail = j?.detail || ''; } catch {}
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
  }, [accountId, campaignId, updateScene]);

  // Music bed (royalty-free). Picked from the user's audio library. Plays under VO if present, else solo at -6dB.
  const [musicUrl, setMusicUrl] = useState<string | null>(null);
  const [musicFilename, setMusicFilename] = useState<string | null>(null);
  const [showMusicPicker, setShowMusicPicker] = useState(false);
  const [libraryAudio, setLibraryAudio] = useState<Array<{ id: string; filename: string; url: string; size_bytes?: number | null }>>([]);
  const [audioLoading, setAudioLoading] = useState(false);
  const loadLibraryAudio = useCallback(async () => {
    if (!accountId) { setLibraryAudio([]); return; }
    setAudioLoading(true);
    try {
      const qs = new URLSearchParams({ account_id: accountId, asset_type: 'audio', limit: '60' });
      const r = await fetch(`/api/assets?${qs}`);
      if (r.ok) setLibraryAudio(await r.json());
    } catch {} finally { setAudioLoading(false); }
  }, [accountId]);

  // (updateScene + isLogoFilename moved earlier in the file so they're declared
  // before the stock/AI callbacks that depend on them.)

  // Receive script from parent (Studio's script generator)
  useEffect(() => {
    if (initialScript !== undefined) setScript(initialScript);
  }, [initialScript]);

  // Elapsed timer while rendering
  useEffect(() => {
    if (!rendering) { setElapsed(0); return; }
    const t0 = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    return () => clearInterval(id);
  }, [rendering]);

  // Sanitized preview of what will actually be spoken
  const { spoken, hadStructure } = useMemo(() => sanitizeScript(script), [script]);
  const spokenWordCount = spoken.trim().split(/\s+/).filter(Boolean).length;
  const spokenEstSeconds = Math.ceil(spokenWordCount / WORDS_PER_SEC);
  const wordCount = script.trim().split(/\s+/).filter(Boolean).length;
  const estSeconds = Math.ceil(wordCount / WORDS_PER_SEC);

  // Load avatar + voice options when the panel opens
  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const [av, vo] = await Promise.all([
          fetch('/api/video/avatars?limit=30').then(r => r.ok ? r.json() : []),
          fetch('/api/video/voices').then(r => r.ok ? r.json() : []),
        ]);
        setAvatars(av);
        setVoices(vo);
        if (av[0] && !avatarId) setAvatarId(av[0].avatar_id);
        const sarah = vo.find((v: VoiceOption) => v.name === 'Sarah');
        if (sarah && !voiceId) setVoiceId(sarah.voice_id);
        else if (vo[0] && !voiceId) setVoiceId(vo[0].voice_id);
      } catch {}
    })();
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── B-roll picker: load uploaded library images on demand ───
  const loadLibraryImages = useCallback(async () => {
    if (!accountId) { setLibraryImages([]); return; }
    setLibraryLoading(true);
    try {
      const qs = new URLSearchParams({ account_id: accountId, asset_type: 'image', limit: '60' });
      // Default to uploaded — that's what the user actually wants for brand b-roll.
      // They can also switch to "all" via the picker UI.
      qs.set('source', 'uploaded');
      const r = await fetch(`/api/assets?${qs}`);
      if (r.ok) setLibraryImages(await r.json());
    } catch {} finally { setLibraryLoading(false); }
  }, [accountId]);

  useEffect(() => {
    if (showBrollPicker || showStoryboardPicker || swapImageForScene !== null) loadLibraryImages();
  }, [showBrollPicker, showStoryboardPicker, swapImageForScene, loadLibraryImages]);

  useEffect(() => {
    if (showMusicPicker) loadLibraryAudio();
  }, [showMusicPicker, loadLibraryAudio]);

  // When the swap modal opens on the Stock tab with a pre-filled query, auto-run the search
  useEffect(() => {
    if (swapImageForScene !== null && swapMode === 'stock' && stockQuery.trim() && stockMatches.length === 0) {
      runStockSearch(stockQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [swapImageForScene, swapMode]);

  // ─── Photo upload handler ───
  const handlePhotoChange = useCallback(async (file: File | null) => {
    setPhotoFile(file);
    setTalkingPhotoId(null);
    if (!file) return;
    setPhotoUploading(true);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch('/api/video/talking-photo', { method: 'POST', body: fd });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`Upload failed: ${r.status} — ${txt.slice(0, 200)}`);
      }
      const data = await r.json();
      if (data.talking_photo_id) {
        setTalkingPhotoId(data.talking_photo_id);
      } else {
        throw new Error('No talking_photo_id in response');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'photo upload failed');
      setPhotoFile(null);
    } finally {
      setPhotoUploading(false);
    }
  }, []);

  // ─── Avatar Snap render ───
  const renderAvatarSnap = useCallback(async () => {
    const toSpeak = spoken || script.trim();
    if (!toSpeak) return;
    setRendering(true);
    setError('');
    setStage('tts');
    setStageMsg('Starting…');

    const dims = ASPECT_DIMS[aspect];
    const useTalkingPhoto = !!talkingPhotoId;
    try {
      const res = await fetch('/api/video/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: toSpeak,
          voice_id: voiceId || undefined,
          avatar_id: useTalkingPhoto ? talkingPhotoId : (avatarId || undefined),
          character_type: useTalkingPhoto ? 'talking_photo' : 'avatar',
          width: dims.width,
          height: dims.height,
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      await consumeStream(res, toSpeak, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [script, spoken, voiceId, avatarId, talkingPhotoId, aspect, accountId, campaignId]);

  // ─── Brand Reel: auto-fill all scenes from a brief + campaign context ───
  const autoFillScenes = useCallback(async () => {
    setAutoFilling(true);
    setAutoFillError('');
    try {
      const r = await fetch('/api/video/brand-reel/generate-scenes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief: brief.trim(),
          url: sourceUrl.trim() || null,
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      const data = await r.json();
      if (!r.ok) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : `HTTP ${r.status}`);
      }
      // Fill every field — overwrites any prior content, which is the expected
      // behavior of an "auto-fill" button (user can edit afterward).
      if (typeof data.headline === 'string') setHeadline(data.headline);
      if (typeof data.subhead === 'string') setSubhead(data.subhead);
      if (typeof data.stat_value === 'string') setStatValue(data.stat_value);
      if (typeof data.stat_label === 'string') setStatLabel(data.stat_label);
      if (typeof data.cta === 'string' && data.cta) setCta(data.cta);
      if (typeof data.voiceover_script === 'string') setVoiceoverScript(data.voiceover_script);
    } catch (e) {
      setAutoFillError(e instanceof Error ? e.message : 'auto-fill failed');
    } finally {
      setAutoFilling(false);
    }
  }, [brief, sourceUrl, accountId, campaignId]);

  // ─── Brand Reel render ───
  const renderBrandReel = useCallback(async () => {
    if (!headline.trim()) return;
    setRendering(true);
    setError('');
    setStage('scene1');
    setStageMsg('Starting…');

    const dims = REEL_DIMS[aspect];
    const summary = [headline.trim(), subhead.trim(), cta.trim()].filter(Boolean).join(' — ');
    try {
      const res = await fetch('/api/video/brand-reel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: headline.trim(),
          subhead: subhead.trim(),
          stat_value: statValue.trim(),
          stat_label: statLabel.trim(),
          cta: cta.trim(),
          voiceover_script: voiceoverScript.trim(),
          b_roll_url: brollUrl,
          voice_id: voiceId || undefined,
          width: dims.width,
          height: dims.height,
          duration_s: reelDuration,
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      await consumeStream(res, summary, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [headline, subhead, statValue, statLabel, cta, voiceoverScript, brollUrl, voiceId, aspect, reelDuration, accountId, campaignId]);

  // ─── Premium Reel render (Hyperframes — kinetic typography via HTML+GSAP+Chrome) ───
  const renderPremiumReel = useCallback(async () => {
    if (!headline.trim()) return;
    setRendering(true);
    setError('');
    setStage('scene1');
    setStageMsg('Starting Hyperframes render (60-90s)…');

    const summary = [headline.trim(), subhead.trim(), cta.trim()].filter(Boolean).join(' — ');
    try {
      const res = await fetch('/api/video/premium-reel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: headline.trim(),
          subhead: subhead.trim(),
          stat_value: statValue.trim(),
          stat_label: statLabel.trim(),
          cta: cta.trim(),
          voiceover_script: voiceoverScript.trim(),
          voice_id: voiceId || undefined,
          music_filename: musicFilename || undefined,
          quality: 'draft',  // expose later if user wants 'standard' or 'high'
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      await consumeStream(res, summary, undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [headline, subhead, statValue, statLabel, cta, voiceoverScript, voiceId, musicFilename, accountId, campaignId]);

  // ─── Brand Story Phase 1 — Director writes storyboard, returns it for preview ───
  const planBrandStory = useCallback(async () => {
    if (!brief.trim() && !sourceUrl.trim() && selectedImages.size === 0) return;
    setPlanning(true);
    setError('');
    setPlannedScenes(null);
    setImageLookup({});

    try {
      const res = await fetch('/api/video/premium-reel/storyboard-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brief: brief.trim(),
          url: sourceUrl.trim() || null,
          target_seconds: targetSeconds,
          target_scenes: overrideSceneCount,           // null = auto, else user override
          image_filenames: Array.from(selectedImages),
          voiceover_script: voiceoverScript.trim(),
          voice_id: voiceId || undefined,
          use_brief_verbatim: useBriefVerbatim,
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      if (!res.ok) {
        let detail = '';
        try { const j = await res.json(); detail = typeof j?.detail === 'string' ? j.detail : JSON.stringify(j?.detail); } catch {}
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
  }, [brief, sourceUrl, targetSeconds, overrideSceneCount, selectedImages, voiceoverScript, voiceId, useBriefVerbatim, accountId, campaignId]);

  // ─── Brand Story Phase 2 — render the approved storyboard ───
  const renderPlannedStoryboard = useCallback(async () => {
    if (!plannedScenes || plannedScenes.length === 0) return;
    setRendering(true);
    setError('');
    setStage('render');
    setStageMsg('Sending storyboard to render…');

    try {
      // Auto-sync audio to scene timing whenever a voice is selected. The
      // backend uses each scene's caption/headline/cta as the speak-text
      // (verbatim mode just makes that explicit via _speak_text). This way
      // creative-mode scenes also get per-scene TTS instead of silent video,
      // and the spoken word always matches what's on screen.
      const syncAudioToScenes = !!voiceId;
      const res = await fetch('/api/video/premium-reel/storyboard-render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenes: plannedScenes,
          voiceover_script: voiceoverScript.trim(),
          voice_id: voiceId || undefined,
          music_filename: musicFilename || undefined,
          sync_audio_to_scenes: syncAudioToScenes,
          quality: 'draft',
          parallel_workers: 2,
          brief: brief.trim(),
          account_id: accountId,
          campaign_id: campaignId,
        }),
      });
      const summary = brief.trim() || `Brand Story · ${targetSeconds}s · ${plannedScenes.length} scenes`;
      await consumeStream(res, summary, undefined);
      // Reset preview after render kicks off (success will close panel via consumeStream)
      setPlannedScenes(null);
      setImageLookup({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Render failed');
      setRendering(false);
    }
  }, [plannedScenes, voiceoverScript, voiceId, musicFilename, useBriefVerbatim, brief, targetSeconds, accountId, campaignId]);

  // Shared SSE consumer — reads the {status, done, error} stream both endpoints emit
  const consumeStream = useCallback(async (res: Response, scriptForLibrary: string, thumb?: string) => {
    if (!res.ok) {
      // Try to surface the FastAPI `detail` so the user sees what actually went wrong
      let detail = '';
      try {
        const j = await res.clone().json();
        detail = typeof j?.detail === 'string' ? j.detail : JSON.stringify(j?.detail ?? j);
      } catch {
        try { detail = await res.text(); } catch {}
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
            onVideoReady(evt.public_url, scriptForLibrary, evt.thumbnail_url || thumb);
            // Reset both forms so the panel is fresh on reopen
            setScript('');
            setHeadline(''); setSubhead(''); setStatValue(''); setStatLabel('');
            setVoiceoverScript('');
            setPhotoFile(null); setTalkingPhotoId(null);
            setRendering(false);
            onClose();
            return;
          } else if (evt.type === 'error') {
            setError(evt.message || 'Render failed');
            setRendering(false);
            return;
          }
        } catch {}
      }
    }
  }, [onClose, onVideoReady]);

  // For Brand Story we have a 2-step flow: planBrandStory (Phase 1) → preview → renderPlannedStoryboard (Phase 2).
  // The main button triggers Phase 1 unless a storyboard is already planned, in which case Phase 2.
  const handleRender = mode === 'avatar-snap' ? renderAvatarSnap
    : mode === 'premium-reel' && premiumSubMode === 'storyboard'
      ? (plannedScenes ? renderPlannedStoryboard : planBrandStory)
      : mode === 'premium-reel' ? renderPremiumReel
      : renderBrandReel;
  const canRender = mode === 'avatar-snap'
    ? !!(spoken || script.trim()) && !rendering && !photoUploading
    : (mode === 'premium-reel' && premiumSubMode === 'storyboard')
      ? (plannedScenes
          ? !rendering
          : (!!brief.trim() || !!sourceUrl.trim() || selectedImages.size > 0) && !rendering && !planning)
      : !!headline.trim() && !rendering;

  if (!open) return null;

  return (
    <div className="px-2 pt-1 pb-2 border-t border-border bg-secondary/10">
      {/* Header + close */}
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-medium text-pink-400 flex items-center gap-1">
          <Film className="h-3 w-3" />
          Video Ad Creator
        </span>
        <button onClick={onClose} className="p-0.5 text-muted-foreground hover:text-foreground" disabled={rendering}>
          <X className="h-3 w-3" />
        </button>
      </div>

      {/* Mode toggle — Avatar Snap (talking head) / Brand Reel (fast) / Premium Reel (kinetic) */}
      <div className="grid grid-cols-3 gap-1 mb-2 p-0.5 bg-background border border-border rounded">
        <button
          onClick={() => setMode('avatar-snap')}
          disabled={rendering}
          className={cn(
            'flex flex-col items-center justify-center gap-0.5 px-1.5 py-1.5 rounded text-[11px] font-medium transition-colors',
            mode === 'avatar-snap'
              ? 'bg-pink-500/20 text-pink-300 border border-pink-500/40'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-1"><Camera className="h-3 w-3" />Avatar Snap</span>
          <span className="text-[9px] text-muted-foreground/70">talking head</span>
        </button>
        <button
          onClick={() => setMode('brand-reel')}
          disabled={rendering}
          className={cn(
            'flex flex-col items-center justify-center gap-0.5 px-1.5 py-1.5 rounded text-[11px] font-medium transition-colors',
            mode === 'brand-reel'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-1"><Wand2 className="h-3 w-3" />Brand Reel</span>
          <span className="text-[9px] text-muted-foreground/70">fast · ~10s render</span>
        </button>
        <button
          onClick={() => setMode('premium-reel')}
          disabled={rendering}
          className={cn(
            'flex flex-col items-center justify-center gap-0.5 px-1.5 py-1.5 rounded text-[11px] font-medium transition-colors',
            mode === 'premium-reel'
              ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40'
              : 'text-muted-foreground hover:text-foreground'
          )}
        >
          <span className="flex items-center gap-1"><Sparkles className="h-3 w-3" />Premium Reel</span>
          <span className="text-[9px] text-muted-foreground/70">kinetic · ~80s render</span>
        </button>
      </div>

      {/* ── AVATAR SNAP form ── */}
      {mode === 'avatar-snap' && (
        <>
          <textarea
            value={script}
            onChange={(e) => setScript(e.target.value)}
            disabled={rendering}
            placeholder="Paste or write the script. Structured Script Generator output (HOOK/SCRIPT/CTA) is auto-extracted — only spoken lines go to the voice."
            className="w-full min-h-[70px] text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring resize-y disabled:opacity-60"
          />

          {hadStructure && spoken && (
            <div className="mt-1.5 bg-emerald-500/5 border border-emerald-500/20 rounded px-2 py-1.5 text-[10px]">
              <div className="text-emerald-400 font-medium mb-0.5 flex items-center gap-1">
                <Sparkles className="h-2.5 w-2.5" /> Will speak ({spokenWordCount} words ≈ {spokenEstSeconds}s):
              </div>
              <div className="text-foreground/90 italic leading-relaxed">"{spoken}"</div>
            </div>
          )}
          {hadStructure && !spoken && (
            <div className="mt-1.5 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-1.5 text-[10px] text-amber-300 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> Couldn't extract a spoken script from the structured block.
            </div>
          )}

          {/* Photo upload — turns the avatar into a talking-photo of the uploaded face */}
          <div className="mt-1.5 flex items-center gap-2 text-[10px]">
            <input
              ref={photoInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => handlePhotoChange(e.target.files?.[0] ?? null)}
              className="hidden"
              disabled={rendering}
            />
            {!photoFile ? (
              <button
                onClick={() => photoInputRef.current?.click()}
                disabled={rendering || photoUploading}
                className="flex items-center gap-1 px-2 py-1 rounded border border-dashed border-border hover:border-pink-500/40 text-muted-foreground hover:text-pink-300 disabled:opacity-50"
                title="Upload a face photo to use as the talking avatar"
              >
                <Upload className="h-3 w-3" />
                Use a photo as avatar
              </button>
            ) : (
              <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-pink-500/10 border border-pink-500/30 text-pink-300">
                {photoUploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ImageIcon className="h-3 w-3" />}
                <span className="truncate max-w-[160px]">{photoFile.name}</span>
                {talkingPhotoId && <span className="text-[9px] text-emerald-400">✓ ready</span>}
                <button
                  onClick={() => { setPhotoFile(null); setTalkingPhotoId(null); }}
                  disabled={rendering || photoUploading}
                  className="ml-1 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </div>
            )}
            <span className="text-muted-foreground">{wordCount} words ≈ {estSeconds}s</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-1.5 text-[10px]">
            <div className="flex items-center gap-0.5 border border-border rounded overflow-hidden">
              {(['16:9', '9:16', '1:1'] as Aspect[]).map((a) => (
                <button
                  key={a}
                  onClick={() => setAspect(a)}
                  disabled={rendering}
                  className={cn(
                    'px-1.5 py-0.5 text-[10px] transition-colors',
                    aspect === a ? 'bg-pink-500/20 text-pink-400' : 'text-muted-foreground hover:bg-secondary/50'
                  )}
                >
                  {a}
                </button>
              ))}
            </div>

            {voices.length > 0 && (
              <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} disabled={rendering}
                      className="bg-background border border-border rounded px-1.5 py-0.5 text-[10px]" title="Voice">
                {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
              </select>
            )}

            {/* Hide the stock-avatar dropdown when a photo is uploaded */}
            {!talkingPhotoId && avatars.length > 0 && (
              <select value={avatarId} onChange={(e) => setAvatarId(e.target.value)} disabled={rendering}
                      className="bg-background border border-border rounded px-1.5 py-0.5 text-[10px] max-w-[160px]" title="Stock avatar">
                {avatars.map((a) => <option key={a.avatar_id} value={a.avatar_id}>{a.name}</option>)}
              </select>
            )}

            <button
              onClick={renderAvatarSnap}
              disabled={!canRender}
              className="ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-pink-500/20 text-pink-400 hover:bg-pink-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {rendering ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
              {rendering ? 'Rendering…' : 'Render Video'}
            </button>
          </div>
        </>
      )}

      {/* Premium Reel sub-toggle: Single (3 scenes) vs Brand Story (N scenes from images) */}
      {mode === 'premium-reel' && (
        <div className="grid grid-cols-2 gap-1 mb-2 p-0.5 bg-background border border-violet-500/30 rounded">
          <button
            onClick={() => setPremiumSubMode('single')}
            disabled={rendering}
            className={cn(
              'flex flex-col items-center justify-center gap-0.5 px-1.5 py-1 rounded text-[10px] font-medium transition-colors',
              premiumSubMode === 'single'
                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <span>Single Reel</span>
            <span className="text-[9px] text-muted-foreground/70">3 scenes · 12s · ~80s render</span>
          </button>
          <button
            onClick={() => setPremiumSubMode('storyboard')}
            disabled={rendering}
            className={cn(
              'flex flex-col items-center justify-center gap-0.5 px-1.5 py-1 rounded text-[10px] font-medium transition-colors',
              premiumSubMode === 'storyboard'
                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <span>Brand Story</span>
            <span className="text-[9px] text-muted-foreground/70">N scenes · ~60s · 2-4 min render</span>
          </button>
        </div>
      )}

      {/* ── BRAND REEL + PREMIUM REEL/single share the scene-field form ── */}
      {(mode === 'brand-reel' || (mode === 'premium-reel' && premiumSubMode === 'single')) && (
        <div className="space-y-1.5">
          {/* Auto-fill row — brief + URL + button. ANY input is enough; even with no
              brief/URL/campaign, the brand prompt still produces a valid Mercan-flavoured
              reel. URL takes precedence — agent reads the page and anchors copy in real
              claims. Works without ever creating a campaign. */}
          <div className="space-y-1 p-1.5 bg-amber-500/5 border border-amber-500/30 rounded">
            <div className="flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-amber-300 shrink-0 ml-0.5" />
              <input
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                disabled={rendering || autoFilling}
                placeholder={campaignId ? "Brief — optional if a campaign is selected" : "Brief (e.g. 'Greece GV for UK retirees') — optional if a URL is set"}
                className="flex-1 text-[11px] bg-transparent focus:outline-none placeholder:text-muted-foreground/70"
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); autoFillScenes(); } }}
              />
              <button
                onClick={autoFillScenes}
                disabled={rendering || autoFilling}
                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
                title="Generate all 4 scenes from the brief, URL, and/or campaign context"
              >
                {autoFilling ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                {autoFilling ? 'Generating…' : 'Auto-fill scenes'}
              </button>
            </div>
            <div className="flex items-center gap-1.5">
              <LinkIcon className="h-3 w-3 text-amber-300/70 shrink-0 ml-0.5" />
              <input
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                disabled={rendering || autoFilling}
                placeholder="(Optional) URL — landing page or article. Agent reads it and anchors the copy in real claims."
                className="flex-1 text-[11px] bg-transparent focus:outline-none placeholder:text-muted-foreground/60"
              />
              {sourceUrl && (
                <button
                  onClick={() => setSourceUrl('')}
                  disabled={rendering || autoFilling}
                  className="text-muted-foreground hover:text-foreground"
                  title="Clear URL"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>
          {autoFillError && (
            <div className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/30 rounded px-2 py-1 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3 shrink-0" /> {autoFillError}
            </div>
          )}

          <input
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            disabled={rendering || autoFilling}
            placeholder="Headline (Scene 1) — e.g. 'Greece Golden Visa'"
            className="w-full text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-60"
          />
          <input
            value={subhead}
            onChange={(e) => setSubhead(e.target.value)}
            disabled={rendering}
            placeholder="Subhead (Scene 2 overlay) — e.g. 'EU residency through real estate'"
            className="w-full text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-60"
          />
          <div className="grid grid-cols-2 gap-1.5">
            <input
              value={statValue}
              onChange={(e) => setStatValue(e.target.value)}
              disabled={rendering}
              placeholder="Stat (e.g. 'EUR 250K')"
              className="text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-60"
            />
            <input
              value={statLabel}
              onChange={(e) => setStatLabel(e.target.value)}
              disabled={rendering}
              placeholder="Stat label (e.g. 'minimum investment')"
              className="text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-60"
            />
          </div>
          <input
            value={cta}
            onChange={(e) => setCta(e.target.value)}
            disabled={rendering}
            placeholder="CTA (Scene 4) — e.g. 'Book a free consultation'"
            className="w-full text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring disabled:opacity-60"
          />
          <textarea
            value={voiceoverScript}
            onChange={(e) => setVoiceoverScript(e.target.value)}
            disabled={rendering}
            placeholder="(Optional) Voiceover script — leave empty for a silent reel"
            className="w-full min-h-[50px] text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring resize-y disabled:opacity-60"
          />

          <div className="flex flex-wrap items-center gap-2 text-[10px]">
            {/* Aspect, duration, b-roll picker — all only relevant for Brand Reel.
                Premium Reel templates are fixed 1920×1080 12s in v1. */}
            {mode === 'brand-reel' && (
              <div className="flex items-center gap-0.5 border border-border rounded overflow-hidden">
                {(['16:9', '9:16', '1:1'] as Aspect[]).map((a) => (
                  <button
                    key={a}
                    onClick={() => setAspect(a)}
                    disabled={rendering}
                    className={cn(
                      'px-1.5 py-0.5 text-[10px] transition-colors',
                      aspect === a ? 'bg-amber-500/20 text-amber-300' : 'text-muted-foreground hover:bg-secondary/50'
                    )}
                  >
                    {a}
                  </button>
                ))}
              </div>
            )}

            {mode === 'brand-reel' && (
              <div className="flex items-center gap-0.5 border border-border rounded overflow-hidden">
                {[15, 30].map((d) => (
                  <button
                    key={d}
                    onClick={() => setReelDuration(d as 15 | 30)}
                    disabled={rendering}
                    className={cn(
                      'px-2 py-0.5 text-[10px] transition-colors',
                      reelDuration === d ? 'bg-amber-500/20 text-amber-300' : 'text-muted-foreground hover:bg-secondary/50'
                    )}
                  >
                    {d}s
                  </button>
                ))}
              </div>
            )}

            {mode === 'premium-reel' && (
              <span className="px-1.5 py-0.5 text-[10px] text-violet-300 bg-violet-500/10 border border-violet-500/30 rounded">
                1920×1080 · 12s · GSAP kinetic
              </span>
            )}

            {/* B-roll image picker — Brand Reel only */}
            {mode === 'brand-reel' && (brollUrl ? (
              <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px]">
                <ImageIcon className="h-2.5 w-2.5" />
                <span className="truncate max-w-[140px]">{brollFilename || 'b-roll'}</span>
                <button
                  onClick={() => { setBrollUrl(null); setBrollFilename(null); }}
                  disabled={rendering}
                  className="ml-1 text-muted-foreground hover:text-foreground"
                  title="Remove b-roll"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowBrollPicker(true)}
                disabled={rendering}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border border-dashed border-border hover:border-amber-500/40 text-muted-foreground hover:text-amber-300"
                title="Pick a b-roll image from your library"
              >
                <Folder className="h-2.5 w-2.5" />
                Pick b-roll
              </button>
            ))}

            {/* Voice dropdown — always visible for premium/brand reel so user knows they can add VO */}
            {voices.length > 0 && (
              <select
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                disabled={rendering}
                className={cn(
                  'bg-background border rounded px-1.5 py-0.5 text-[10px]',
                  voiceoverScript.trim() ? 'border-violet-500/40 text-violet-200' : 'border-border text-muted-foreground'
                )}
                title={voiceoverScript.trim() ? 'Voiceover voice' : 'Add a voiceover script above to enable'}
              >
                {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>🎙 {v.name}</option>)}
              </select>
            )}

            {/* Music bed picker */}
            {(mode === 'premium-reel' || mode === 'brand-reel') && (musicFilename ? (
              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                🎵 <span className="truncate max-w-[100px]">{musicFilename}</span>
                <button onClick={() => { setMusicUrl(null); setMusicFilename(null); }} disabled={rendering}
                        className="ml-0.5 text-muted-foreground hover:text-foreground" title="Remove music"><X className="h-2.5 w-2.5" /></button>
              </span>
            ) : (
              <button
                onClick={() => setShowMusicPicker(true)}
                disabled={rendering}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border border-dashed border-border hover:border-emerald-500/40 text-muted-foreground hover:text-emerald-300"
                title="Pick royalty-free music from your library"
              >
                🎵 Music
              </button>
            ))}

            <button
              onClick={handleRender}
              disabled={!canRender}
              className={cn(
                'ml-auto flex items-center gap-1 px-2 py-0.5 rounded text-[10px] disabled:opacity-50 disabled:cursor-not-allowed',
                mode === 'premium-reel'
                  ? 'bg-violet-500/20 text-violet-300 hover:bg-violet-500/30'
                  : 'bg-amber-500/20 text-amber-300 hover:bg-amber-500/30'
              )}
            >
              {rendering ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
              {rendering ? 'Rendering…' : (mode === 'premium-reel' ? 'Render Premium' : 'Render Reel')}
            </button>
          </div>
        </div>
      )}

      {/* ── BRAND STORY form — N-scene storyboard from images + brief ── */}
      {mode === 'premium-reel' && premiumSubMode === 'storyboard' && (
        <div className="space-y-1.5">
          {/* Script-handling mode toggle — Director rewrite vs verbatim (legal) */}
          <div className="flex items-center gap-1 p-0.5 border border-border rounded text-[10px]">
            <button
              onClick={() => setUseBriefVerbatim(false)}
              disabled={rendering || planning}
              className={cn(
                'flex-1 px-2 py-1 rounded transition-colors',
                !useBriefVerbatim ? 'bg-violet-500/20 text-violet-300' : 'text-muted-foreground hover:bg-secondary/50'
              )}
              title="Director writes captions, picks images, and structures the story"
            >
              ✨ Creative — let the agent write captions
            </button>
            <button
              onClick={() => setUseBriefVerbatim(true)}
              disabled={rendering || planning}
              className={cn(
                'flex-1 px-2 py-1 rounded transition-colors',
                useBriefVerbatim ? 'bg-amber-500/20 text-amber-300' : 'text-muted-foreground hover:bg-secondary/50'
              )}
              title="Use the brief text verbatim — no rewriting. For legal/regulated copy."
            >
              🔒 Verbatim — use my script as-is
            </button>
          </div>

          <textarea
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            disabled={rendering}
            placeholder={useBriefVerbatim
              ? 'Paste your script verbatim — every sentence becomes a scene caption, exactly as written.'
              : "Brief — what's the story? e.g. 'Mercan Group brand video — 37 years, 4,100 families, hotel investment immigration'"}
            className="w-full min-h-[60px] text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring resize-y disabled:opacity-60"
          />

          <div className="flex items-center gap-1.5">
            <LinkIcon className="h-3 w-3 text-violet-300/70 shrink-0 ml-0.5" />
            <input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              disabled={rendering}
              placeholder="(Optional) URL — landing page or article. Director reads it for real claims."
              className="flex-1 text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring placeholder:text-muted-foreground/60"
            />
          </div>

          {/* Image multi-select trigger */}
          <button
            onClick={() => setShowStoryboardPicker(true)}
            disabled={rendering}
            className={cn(
              'w-full flex items-center justify-between px-2.5 py-2 rounded text-[11px] border transition-colors',
              selectedImages.size > 0
                ? 'bg-violet-500/10 border-violet-500/40 text-violet-300'
                : 'border-dashed border-border text-muted-foreground hover:border-violet-500/40 hover:text-violet-300'
            )}
          >
            <span className="flex items-center gap-1.5">
              <Folder className="h-3.5 w-3.5" />
              {selectedImages.size > 0
                ? `${selectedImages.size} image${selectedImages.size === 1 ? '' : 's'} selected for b-roll`
                : 'Pick library images for b-roll scenes (multi-select)'}
            </span>
            <span className="text-[10px] text-muted-foreground/70">tap to {selectedImages.size > 0 ? 'edit' : 'pick'}</span>
          </button>

          <textarea
            value={voiceoverScript}
            onChange={(e) => setVoiceoverScript(e.target.value)}
            disabled={rendering}
            placeholder="(Optional) Voiceover script — leave empty for a silent reel"
            className="w-full min-h-[50px] text-[11px] bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring resize-y disabled:opacity-60"
          />

          <div className="flex flex-wrap items-center gap-2 text-[10px]">
            {/* Target duration toggle */}
            <div className="flex items-center gap-0.5 border border-border rounded overflow-hidden">
              {([30, 60, 90] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setTargetSeconds(s)}
                  disabled={rendering}
                  className={cn(
                    'px-2 py-0.5 text-[10px] transition-colors',
                    targetSeconds === s ? 'bg-violet-500/20 text-violet-300' : 'text-muted-foreground hover:bg-secondary/50'
                  )}
                >
                  {s}s
                </button>
              ))}
            </div>

            {/* Scene count — recommended is shown as placeholder, user can override.
                Click ↺ to reset to recommended. */}
            {(() => {
              const recommended = Math.max(3, Math.round(targetSeconds / 4.6));
              const showing = overrideSceneCount ?? recommended;
              const isOverride = overrideSceneCount !== null && overrideSceneCount !== recommended;
              return (
                <div className="flex items-center gap-0.5 px-1 py-0.5 text-[10px] text-violet-300/90 bg-violet-500/10 border border-violet-500/30 rounded">
                  <button
                    onClick={() => setOverrideSceneCount(Math.max(3, showing - 1))}
                    disabled={rendering || planning}
                    className="w-4 text-violet-300/60 hover:text-violet-200 disabled:opacity-40"
                    title="Fewer scenes"
                  >−</button>
                  <input
                    type="number"
                    min={3} max={40}
                    value={showing}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      setOverrideSceneCount(Number.isFinite(v) && v >= 3 ? v : null);
                    }}
                    disabled={rendering || planning}
                    className="w-7 bg-transparent text-center text-[10px] border-0 focus:outline-none"
                    title="Number of scenes to render"
                  />
                  <button
                    onClick={() => setOverrideSceneCount(Math.min(40, showing + 1))}
                    disabled={rendering || planning}
                    className="w-4 text-violet-300/60 hover:text-violet-200 disabled:opacity-40"
                    title="More scenes"
                  >+</button>
                  <span className="text-[9px] text-violet-300/60 ml-0.5">scenes</span>
                  {isOverride ? (
                    <button
                      onClick={() => setOverrideSceneCount(null)}
                      disabled={rendering || planning}
                      className="text-[9px] text-amber-300/80 hover:text-amber-200 ml-1"
                      title={`Reset to recommended (${recommended})`}
                    >↺ {recommended}</button>
                  ) : (
                    <span className="text-[9px] text-violet-300/40 ml-1" title="Recommended">★</span>
                  )}
                </div>
              );
            })()}

            {voices.length > 0 && (
              <select
                value={voiceId}
                onChange={(e) => setVoiceId(e.target.value)}
                disabled={rendering}
                className={cn(
                  'bg-background border rounded px-1.5 py-0.5 text-[10px]',
                  voiceoverScript.trim() ? 'border-violet-500/40 text-violet-200' : 'border-border text-muted-foreground'
                )}
                title={voiceoverScript.trim() ? 'Voiceover voice' : 'Add a voiceover script above to enable'}
              >
                {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>🎙 {v.name}</option>)}
              </select>
            )}

            {/* Music bed picker — same as Premium Reel single */}
            {musicFilename ? (
              <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                🎵 <span className="truncate max-w-[100px]">{musicFilename}</span>
                <button onClick={() => { setMusicUrl(null); setMusicFilename(null); }} disabled={rendering}
                        className="ml-0.5 text-muted-foreground hover:text-foreground" title="Remove music"><X className="h-2.5 w-2.5" /></button>
              </span>
            ) : (
              <button
                onClick={() => setShowMusicPicker(true)}
                disabled={rendering}
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] border border-dashed border-border hover:border-emerald-500/40 text-muted-foreground hover:text-emerald-300"
                title="Pick royalty-free music from your library"
              >
                🎵 Music
              </button>
            )}

            <button
              onClick={handleRender}
              disabled={!canRender}
              className="ml-auto flex items-center gap-1 px-3 py-1 rounded text-[11px] bg-violet-500/20 text-violet-300 hover:bg-violet-500/30 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {(planning || rendering) ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
              {planning ? 'Planning storyboard…'
                : rendering ? 'Rendering…'
                : plannedScenes ? `Render ${plannedScenes.length} scenes`
                : 'Plan storyboard'}
            </button>
          </div>

          <div className="text-[10px] text-muted-foreground italic">
            {plannedScenes
              ? `Review the scenes below — about ${Math.ceil((planningEta || 0) / 60)} min to render.`
              : 'Step 1: plan the storyboard (~30s). Then preview the scenes before the long render.'}
          </div>

          {/* ─── Storyboard preview — compact editable list ─── */}
          {plannedScenes && plannedScenes.length > 0 && !rendering && (
            <div className="mt-2 border border-violet-500/30 rounded-lg overflow-hidden bg-violet-500/5">
              <div className="px-2.5 py-1.5 border-b border-violet-500/20 flex items-center justify-between">
                <span className="text-[10px] font-medium text-violet-300">
                  Storyboard · {plannedScenes.length} scenes · click any field to edit
                </span>
                <button
                  onClick={planBrandStory}
                  disabled={planning}
                  className="text-[10px] text-muted-foreground hover:text-violet-300 underline-offset-2 hover:underline disabled:opacity-50"
                  title="Re-roll the storyboard with a different layout"
                >
                  ↻ regenerate
                </button>
              </div>
              {/* Compact list — every scene is a single row. Thumb = 48×27 (broll
                  only). Caption/text on a single line. Animation pickers are
                  inline tiny dropdowns. Hover to reveal scene-label, delete. */}
              <div className="max-h-[60vh] overflow-y-auto divide-y divide-violet-500/10">
                {plannedScenes.map((s, i) => {
                  const t = String(s.type || 'scene');
                  const fn = String(s.image_filename || '');
                  const thumb = fn ? imageLookup[fn] : null;
                  const typeColor =
                    t === 'logo' ? 'bg-amber-500/40 text-amber-100'
                    : t === 'hero' ? 'bg-violet-500/30 text-violet-200'
                    : t === 'cta' ? 'bg-amber-500/30 text-amber-200'
                    : t === 'stat' ? 'bg-emerald-500/30 text-emerald-200'
                    : 'bg-sky-500/20 text-sky-200';
                  return (
                    <div key={i} className="px-1.5 py-1 hover:bg-violet-500/5 group">
                      {/* Top row: # · type · thumb · primary text · pickers · delete */}
                      <div className="flex items-center gap-1.5">
                        {/* Number + type — single column, very compact */}
                        <div className="shrink-0 flex items-center gap-1 w-14">
                          <span className="text-[9px] font-mono text-muted-foreground/50">{String(i + 1).padStart(2, '0')}</span>
                          <span className={cn('text-[7.5px] px-1 py-px rounded uppercase tracking-wider', typeColor)}>{t}</span>
                        </div>

                        {/* Thumbnail (broll: real image OR ⚠ needs-image placeholder) */}
                        <div className="shrink-0 w-12">
                          {t === 'broll' ? (
                            <button
                              onClick={() => {
                                // Pre-seed the stock tab with Director's search query if present
                                const q = String(s.image_search_query || s.caption || '');
                                setStockQuery(q);
                                setSwapMode(thumb ? 'library' : 'stock');
                                setSwapImageForScene(i);
                              }}
                              className={cn(
                                'relative w-12 h-7 rounded overflow-hidden border block transition-colors',
                                thumb
                                  ? 'bg-black/40 border-border hover:border-violet-500/60'
                                  : 'bg-amber-500/10 border-amber-500/40 hover:border-amber-500/80 animate-pulse'
                              )}
                              title={thumb
                                ? `Click to swap · ${fn}`
                                : `⚠ Needs image — click to pick (search query: "${String(s.image_search_query || '')}")`}
                            >
                              {thumb
                                ? <img src={thumb} alt="" className="w-full h-full object-cover" />
                                : <span className="text-[10px] flex items-center justify-center w-full h-full text-amber-300">⚠</span>}
                              {fn && isLogoFilename(fn) && (
                                <span className="absolute top-0 right-0 text-[6px] px-0.5 bg-amber-500/90 text-black rounded-bl leading-none">L</span>
                              )}
                            </button>
                          ) : (
                            <div className="w-12 h-7 rounded bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                              <span className="text-[12px] opacity-60">
                                {t === 'logo' ? '🪪' : t === 'hero' ? '✨' : t === 'cta' ? '🎯' : '📊'}
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Primary editable text — one line */}
                        <div className="flex-1 min-w-0">
                          {t === 'hero' && (
                            <input
                              value={String(s.headline || '')}
                              onChange={(e) => updateScene(i, { headline: e.target.value })}
                              placeholder="Hero headline"
                              className="w-full text-[11px] font-semibold bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none py-0.5 truncate"
                            />
                          )}
                          {t === 'broll' && (
                            <input
                              value={String(s.caption || '')}
                              onChange={(e) => updateScene(i, { caption: e.target.value })}
                              placeholder="Caption"
                              className="w-full text-[11px] bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none py-0.5 truncate"
                            />
                          )}
                          {t === 'logo' && (
                            <input
                              value={String(s.brand_name || '')}
                              onChange={(e) => updateScene(i, { brand_name: e.target.value })}
                              placeholder="Brand name"
                              className="w-full text-[11px] font-semibold bg-transparent border-b border-transparent hover:border-amber-500/30 focus:border-amber-500/60 focus:outline-none py-0.5 truncate"
                            />
                          )}
                          {t === 'stat' && (
                            <div className="flex gap-1.5 items-baseline">
                              <input
                                value={String(s.stat_value || '')}
                                onChange={(e) => updateScene(i, { stat_value: e.target.value })}
                                placeholder="#"
                                className="w-16 text-[12px] font-bold bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none py-0.5"
                              />
                              <input
                                value={String(s.stat_label || '')}
                                onChange={(e) => updateScene(i, { stat_label: e.target.value })}
                                placeholder="Label"
                                className="flex-1 min-w-0 text-[11px] bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none py-0.5 truncate"
                              />
                            </div>
                          )}
                          {t === 'cta' && (
                            <input
                              value={String(s.cta || '')}
                              onChange={(e) => updateScene(i, { cta: e.target.value })}
                              placeholder="Call to action"
                              className="w-full text-[11px] font-semibold bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none py-0.5 truncate"
                            />
                          )}
                        </div>

                        {/* Inline animation pickers — broll only, very tight */}
                        {t === 'broll' && (
                          <>
                            <select
                              value={String(s.composition || 'fullbleed')}
                              onChange={(e) => updateScene(i, { composition: e.target.value })}
                              className="shrink-0 text-[9px] bg-transparent border border-violet-500/20 rounded px-1 py-0.5 text-muted-foreground hover:border-violet-500/40 focus:border-violet-500/60 focus:outline-none"
                              title="Layout composition"
                            >
                              <option value="fullbleed">▦ full</option>
                              <option value="letterbox">▭ letterbox</option>
                              <option value="split">⊟ split</option>
                              <option value="lowerthird">⎯ lower⅓</option>
                            </select>
                            <select
                              value={String(s.motion || 'kenburns-zoom-in')}
                              onChange={(e) => updateScene(i, { motion: e.target.value })}
                              className="shrink-0 text-[9px] bg-transparent border border-violet-500/20 rounded px-1 py-0.5 text-muted-foreground hover:border-violet-500/40 focus:border-violet-500/60 focus:outline-none"
                              title="Camera motion"
                            >
                              <option value="kenburns-zoom-in">📷 zoom in</option>
                              <option value="kenburns-zoom-out">📷 zoom out</option>
                              <option value="pan-left">↤ pan L→R</option>
                              <option value="pan-right">↦ pan R→L</option>
                              <option value="dolly-in">→ dolly</option>
                              <option value="parallax-tilt">⤺ parallax</option>
                            </select>
                            <select
                              value={String(s.text_treatment || 'blur-stagger')}
                              onChange={(e) => updateScene(i, { text_treatment: e.target.value })}
                              className="shrink-0 text-[9px] bg-transparent border border-violet-500/20 rounded px-1 py-0.5 text-muted-foreground hover:border-violet-500/40 focus:border-violet-500/60 focus:outline-none"
                              title="Text reveal animation"
                            >
                              <option value="blur-stagger">✦ blur</option>
                              <option value="slide-up">↑ slide</option>
                              <option value="scale-bounce">◯ bounce</option>
                              <option value="typewriter">⌨ typer</option>
                              <option value="scale-bounce-chars">⌘ chars</option>
                              <option value="mask-reveal">▭ mask</option>
                            </select>
                          </>
                        )}

                        {/* Delete */}
                        <button
                          onClick={() => setPlannedScenes((prev) => prev ? prev.filter((_, j) => j !== i) : prev)}
                          className="shrink-0 w-4 h-4 flex items-center justify-center rounded text-muted-foreground/40 hover:text-red-400 hover:bg-red-500/10 text-[14px] leading-none"
                          title="Remove scene"
                        >
                          ×
                        </button>
                      </div>

                      {/* Optional secondary fields — only shown when there's a value
                          OR the row is hovered. Keeps the default state ultra-compact. */}
                      {t === 'broll' && (s.scene_label || false) ? (
                        <input
                          value={String(s.scene_label || '')}
                          onChange={(e) => updateScene(i, { scene_label: e.target.value })}
                          placeholder="Scene label (location)"
                          className="w-full text-[9px] uppercase tracking-wider text-muted-foreground bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none mt-0.5 ml-[120px] truncate"
                        />
                      ) : null}
                      {(t === 'logo' || t === 'cta') && (s.tagline || false) ? (
                        <input
                          value={String(s.tagline || '')}
                          onChange={(e) => updateScene(i, { tagline: e.target.value })}
                          placeholder="Tagline"
                          className="w-full text-[9px] uppercase tracking-wider text-muted-foreground bg-transparent border-b border-transparent hover:border-amber-500/30 focus:border-amber-500/60 focus:outline-none mt-0.5 ml-[120px] truncate"
                        />
                      ) : null}
                      {/* Per-scene instruction note — Director picks this up on regenerate */}
                      <input
                        value={String(s.instructions || '')}
                        onChange={(e) => updateScene(i, { instructions: e.target.value })}
                        placeholder="✎ Instructions (optional — e.g. 'use Portugal flag', 'punch this number')"
                        className={cn(
                          'w-full text-[9px] italic text-muted-foreground/70 bg-transparent border-b border-transparent hover:border-violet-500/30 focus:border-violet-500/60 focus:outline-none mt-0.5 ml-[120px] truncate',
                          s.instructions ? 'opacity-100 text-violet-300/80' : 'opacity-0 group-hover:opacity-100 transition-opacity'
                        )}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Per-scene image swap modal — Library / Stock / AI tabs */}
          {swapImageForScene !== null && (
            <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setSwapImageForScene(null)}>
              <div className="bg-card border border-violet-500/30 rounded-lg w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                  <span className="text-sm font-medium">Image for scene {swapImageForScene + 1}</span>
                  <button onClick={() => setSwapImageForScene(null)} className="text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
                </div>

                {/* Tabs */}
                <div className="flex items-center gap-0.5 px-3 pt-2 border-b border-border">
                  {([
                    { k: 'library', label: '📁 My library', count: libraryImages.length },
                    { k: 'stock',   label: '🌐 Stock photo', count: null },
                    { k: 'ai',      label: '🪄 AI generate', count: null },
                  ] as const).map((tab) => (
                    <button
                      key={tab.k}
                      onClick={() => setSwapMode(tab.k)}
                      className={cn(
                        'px-3 py-1.5 text-[11px] rounded-t border-b-2 transition-colors',
                        swapMode === tab.k
                          ? 'border-violet-500 text-violet-300 bg-violet-500/10'
                          : 'border-transparent text-muted-foreground hover:text-foreground'
                      )}
                    >
                      {tab.label}{tab.count !== null && tab.count > 0 ? ` · ${tab.count}` : ''}
                    </button>
                  ))}
                </div>

                <div className="flex-1 overflow-y-auto p-3">
                  {/* LIBRARY tab */}
                  {swapMode === 'library' && (
                    libraryImages.length === 0 ? (
                      <div className="text-xs text-muted-foreground py-8 text-center">
                        No uploaded images yet. Try the Stock or AI tab.
                      </div>
                    ) : (
                      <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                        {libraryImages.map((img) => {
                          const stored = (img.url || '').split('/').pop() || img.filename;
                          const logo = isLogoFilename(img.filename);
                          return (
                            <button
                              key={img.id}
                              onClick={() => {
                                updateScene(swapImageForScene, { image_filename: stored });
                                setImageLookup((prev) => ({ ...prev, [stored]: img.url }));
                                setSwapImageForScene(null);
                              }}
                              className="group aspect-video rounded overflow-hidden border border-border hover:border-violet-500/60 bg-black relative text-left"
                              title={img.filename}
                            >
                              <img src={img.url} alt={img.filename} className="w-full h-full object-cover" />
                              {logo && (
                                <span className="absolute top-1 right-1 text-[8px] px-1 py-0.5 bg-amber-500/90 text-black rounded">LOGO</span>
                              )}
                              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-1.5 py-1">
                                <span className="text-[9px] text-white truncate block">{img.filename}</span>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )
                  )}

                  {/* STOCK tab */}
                  {swapMode === 'stock' && (
                    <div className="space-y-2">
                      <div className="flex gap-1.5">
                        <input
                          value={stockQuery}
                          onChange={(e) => setStockQuery(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') runStockSearch(stockQuery); }}
                          placeholder="Search stock photos (e.g. luxury hotel exterior, family arriving airport)"
                          className="flex-1 text-xs bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring"
                        />
                        <button
                          onClick={() => runStockSearch(stockQuery)}
                          disabled={stockSearching || !stockQuery.trim()}
                          className="px-3 py-1.5 text-xs bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 rounded disabled:opacity-50"
                        >
                          {stockSearching ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Search'}
                        </button>
                      </div>
                      {stockMatches.length === 0 && !stockSearching ? (
                        <div className="text-[10px] text-muted-foreground py-6 text-center">
                          Searches Unsplash + Pexels (free). Add UNSPLASH_ACCESS_KEY and/or PEXELS_API_KEY to .env if no results show.
                        </div>
                      ) : (
                        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                          {stockMatches.map((m, mi) => (
                            <button
                              key={mi}
                              onClick={() => adoptStock(m, swapImageForScene)}
                              className="group aspect-video rounded overflow-hidden border border-border hover:border-emerald-500/60 bg-black relative text-left"
                              title={String(m.description || '')}
                            >
                              <img src={String(m.thumb_url || m.image_url)} alt="" className="w-full h-full object-cover" />
                              <span className="absolute top-1 left-1 text-[7px] px-1 py-0.5 bg-emerald-500/90 text-black rounded uppercase tracking-wider">{String(m.provider || 'stock')}</span>
                              {m.photographer ? (
                                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent px-1.5 py-1">
                                  <span className="text-[8px] text-white/80 truncate block">© {String(m.photographer)}</span>
                                </div>
                              ) : null}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* AI tab */}
                  {swapMode === 'ai' && (
                    <div className="space-y-2">
                      <textarea
                        value={aiPrompt}
                        onChange={(e) => setAiPrompt(e.target.value)}
                        placeholder="Describe the image you want — be specific about subject, lighting, lens, mood. Example: 'modern boutique hotel exterior at golden hour, mediterranean coast, cinematic wide shot, warm light, shallow depth of field'"
                        className="w-full min-h-[90px] text-xs bg-background border border-border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-ring resize-y"
                      />
                      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                        <span>Replicate FLUX-schnell · ~$0.003 · ~3 sec · 1920×1080 16:9</span>
                        <button
                          onClick={() => generateAiImage(aiPrompt, swapImageForScene)}
                          disabled={aiGenerating || !aiPrompt.trim()}
                          className="px-3 py-1 text-xs bg-violet-500/20 text-violet-300 hover:bg-violet-500/30 rounded disabled:opacity-50 flex items-center gap-1"
                        >
                          {aiGenerating ? <Loader2 className="h-3 w-3 animate-spin" /> : '🪄'} Generate
                        </button>
                      </div>
                      <div className="text-[10px] text-muted-foreground italic border-t border-border pt-2">
                        Add REPLICATE_API_TOKEN to .env to enable. Get one free at replicate.com.
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Music bed picker modal */}
          {showMusicPicker && (
            <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setShowMusicPicker(false)}>
              <div className="bg-card border border-emerald-500/30 rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                  <span className="text-sm font-medium flex items-center gap-1.5">🎵 Pick a music bed</span>
                  <button onClick={() => setShowMusicPicker(false)} className="text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                  {audioLoading ? (
                    <div className="text-xs text-muted-foreground py-8 text-center flex items-center justify-center gap-2">
                      <Loader2 className="h-3 w-3 animate-spin" /> loading audio…
                    </div>
                  ) : libraryAudio.length === 0 ? (
                    <div className="text-xs text-muted-foreground py-8 text-center">
                      No audio in your library yet.<br />
                      Upload .mp3 or .wav files in Studio (look for &quot;Upload&quot;), then they&apos;ll show here.
                    </div>
                  ) : (
                    libraryAudio.map((a) => {
                      const stored = (a.url || '').split('/').pop() || a.filename;
                      const sizeKb = a.size_bytes ? Math.round(a.size_bytes / 1024) : null;
                      return (
                        <div
                          key={a.id}
                          className="flex items-center gap-2 p-2 rounded border border-border hover:border-emerald-500/40 bg-card/40 hover:bg-emerald-500/5 transition-colors"
                        >
                          <button
                            onClick={() => {
                              setMusicUrl(a.url);
                              setMusicFilename(a.filename);
                              setShowMusicPicker(false);
                            }}
                            className="text-left flex-1 min-w-0"
                            title={a.filename}
                          >
                            <div className="text-[11px] font-medium truncate">{a.filename}</div>
                            {sizeKb && <div className="text-[9px] text-muted-foreground">{sizeKb} KB</div>}
                          </button>
                          <audio src={a.url} controls className="h-7 w-48" />
                        </div>
                      );
                    })
                  )}
                </div>
                <div className="border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
                  Music plays under VO at -18 dB if a voiceover is set, otherwise solo at -6 dB. Fades in 1s, out 1.5s.
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Storyboard image multi-picker modal */}
      {showStoryboardPicker && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setShowStoryboardPicker(false)}>
          <div className="bg-card border border-violet-500/30 rounded-lg w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-sm font-medium flex items-center gap-1.5">
                <Folder className="h-4 w-4 text-violet-300" />
                Pick images for the Brand Story
                <span className="text-[10px] text-muted-foreground ml-1">click to toggle · Director assigns each to a scene</span>
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-violet-300">{selectedImages.size} selected</span>
                <button onClick={() => setShowStoryboardPicker(false)} className="p-1 text-muted-foreground hover:text-foreground">
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {libraryLoading ? (
                <div className="text-xs text-muted-foreground flex items-center gap-1.5 py-8 justify-center">
                  <Loader2 className="h-3 w-3 animate-spin" /> loading library…
                </div>
              ) : libraryImages.length === 0 ? (
                <div className="text-xs text-muted-foreground py-8 text-center">
                  No uploaded images in your library yet. Upload some in Studio first.
                </div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-5 gap-2">
                  {libraryImages.map((img) => {
                    const isSelected = selectedImages.has(img.filename);
                    return (
                      <button
                        key={img.id}
                        onClick={() => {
                          setSelectedImages(prev => {
                            const next = new Set(prev);
                            if (next.has(img.filename)) next.delete(img.filename);
                            else next.add(img.filename);
                            return next;
                          });
                        }}
                        className={cn(
                          'group aspect-video rounded overflow-hidden border-2 bg-black relative text-left transition-all',
                          isSelected
                            ? 'border-violet-400 ring-2 ring-violet-500/40'
                            : 'border-border hover:border-violet-500/50'
                        )}
                        title={img.filename}
                      >
                        <img src={img.url} alt={img.filename} className="w-full h-full object-cover" />
                        {isSelected && (
                          <div className="absolute inset-0 bg-violet-500/20 flex items-center justify-center">
                            <div className="bg-violet-500 text-white rounded-full w-7 h-7 flex items-center justify-center text-xs font-bold shadow-lg">
                              ✓
                            </div>
                          </div>
                        )}
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <span className="text-[9px] text-white truncate block">{img.filename}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="border-t border-border px-3 py-2 flex items-center justify-between text-[10px]">
              <button
                onClick={() => setSelectedImages(new Set())}
                className="text-muted-foreground hover:text-foreground"
              >
                Clear selection
              </button>
              <button
                onClick={() => setShowStoryboardPicker(false)}
                className="px-3 py-1 rounded bg-violet-500/20 text-violet-300 hover:bg-violet-500/30"
              >
                Done · {selectedImages.size} selected
              </button>
            </div>
          </div>
        </div>
      )}

      {/* B-roll picker modal — shows uploaded images from the local library */}
      {showBrollPicker && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setShowBrollPicker(false)}>
          <div className="bg-card border border-border rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-sm font-medium flex items-center gap-1.5">
                <Folder className="h-4 w-4 text-amber-300" />
                Pick a b-roll image
                <span className="text-[10px] text-muted-foreground ml-1">from your local library</span>
              </span>
              <button onClick={() => setShowBrollPicker(false)} className="p-1 text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              {libraryLoading ? (
                <div className="text-xs text-muted-foreground flex items-center gap-1.5 py-8 justify-center">
                  <Loader2 className="h-3 w-3 animate-spin" /> loading library…
                </div>
              ) : libraryImages.length === 0 ? (
                <div className="text-xs text-muted-foreground py-8 text-center">
                  No uploaded images in your library yet.<br />
                  Upload some in Studio first, then come back here.
                </div>
              ) : (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                  {libraryImages.map((img) => (
                    <button
                      key={img.id}
                      onClick={() => {
                        setBrollUrl(img.url);
                        setBrollFilename(img.filename);
                        setShowBrollPicker(false);
                      }}
                      className="group aspect-video rounded overflow-hidden border border-border hover:border-amber-500/50 bg-black relative text-left"
                      title={img.filename}
                    >
                      <img src={img.url} alt={img.filename} className="w-full h-full object-cover" />
                      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 py-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <span className="text-[9px] text-white truncate block">{img.filename}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="border-t border-border px-3 py-2 flex items-center justify-between text-[10px] text-muted-foreground">
              <span>{libraryImages.length} image{libraryImages.length === 1 ? '' : 's'}</span>
              <button
                onClick={() => { setBrollUrl(null); setBrollFilename(null); setShowBrollPicker(false); }}
                className="text-muted-foreground hover:text-foreground"
              >
                Use brand gradient instead (no image)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Status bar — shared across modes */}
      {(rendering || error) && (
        <div className={cn(
          'mt-1.5 text-[10px] rounded px-2 py-1.5 flex items-center gap-2',
          error ? 'bg-red-500/10 text-red-400' : 'bg-secondary/30 text-muted-foreground'
        )}>
          {rendering && !error && (
            <Loader2 className={cn('h-3 w-3 animate-spin shrink-0',
              mode === 'brand-reel' ? 'text-amber-400'
              : mode === 'premium-reel' ? 'text-violet-400'
              : 'text-pink-400')} />
          )}
          {error ? (
            <span>⚠ {error}</span>
          ) : (
            <>
              <span className={cn('font-medium uppercase tracking-wide',
                mode === 'brand-reel' ? 'text-amber-400'
                : mode === 'premium-reel' ? 'text-violet-400'
                : 'text-pink-400')}>{stage}</span>
              <span className="flex-1">{stageMsg}</span>
              <span className="text-muted-foreground tabular-nums">{elapsed}s</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}
