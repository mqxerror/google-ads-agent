/**
 * PresenterLane — "talking avatar · HeyGen".
 * Hits POST /api/video/generate (via useKineticRender.renderAvatarSnap).
 *
 * Three steps (plan §7.2):
 *   Step 1 — Write the script (ScriptGenerator folded in) → sanitized-spoken preview
 *   Step 2 — Avatar / photo + voice   (+ the Brand Avatar picker)
 *   Step 3 — Render
 *
 * Brand Avatar picker (§13 default: presenter lane → Kinetic Studio):
 *   GET /api/studio/brand-avatars?account_id= lists reusable avatars.
 *   Selecting one stamps its soul_id + voice_id into the presenter render.
 *   The presenter pipeline stays still→motion→TTS bed (NON-lipsync) — the
 *   avatar only supplies a consistent face soul_id + voice_id. No training
 *   UI here (SoulCreator owns that); empty state deep-links /studio#souls.
 *   Lipsync seam: backend/app/services/video_director.py AVATAR_SPEAK_MODEL.
 */

import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { Loader2, Upload, ImageIcon, X, AlertTriangle, UserRound } from 'lucide-react';
import { cn } from '@/lib/utils';
import { sanitizeScript } from '@/lib/scriptSanitizer';
import { LaneLabel, RenderButton, StatusStrip } from './KineticShared';
import { useKineticRender, type Aspect } from './useKineticRender';
import { useAvatarVoiceOptions } from './useKineticLibrary';
import ScriptGenerator from '../ScriptGenerator';

const WORDS_PER_SEC = 2.5;

interface BrandAvatar {
  id: string;
  account_id: string;
  name: string;
  soul_id: string | null;
  voice_id: string | null;
  style_notes: string;
  created_at: string;
}

interface Props {
  accountId?: string;
  campaignId?: string | null;
  campaignName?: string | null;
  onVideoReady: (url: string, script: string, thumb?: string) => void;
  onGoToSouls: () => void;   // deep-link to /studio#souls
}

export default function PresenterLane({ accountId, campaignId, campaignName, onVideoReady, onGoToSouls }: Props) {
  const render = useKineticRender({ onVideoReady: (r) => onVideoReady(r.url, r.script, r.thumbnail) });
  const { avatars, voices, avatarId, setAvatarId, voiceId, setVoiceId } = useAvatarVoiceOptions(true);

  const [script, setScript] = useState('');
  const [aspect, setAspect] = useState<Aspect>('16:9');

  // Photo upload → talking photo
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [talkingPhotoId, setTalkingPhotoId] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);

  // Brand Avatar picker
  const [brandAvatars, setBrandAvatars] = useState<BrandAvatar[]>([]);
  const [selectedBrandAvatarId, setSelectedBrandAvatarId] = useState<string>('');

  useEffect(() => {
    if (!accountId) { setBrandAvatars([]); return; }
    (async () => {
      try {
        const r = await fetch(`/api/studio/brand-avatars?account_id=${encodeURIComponent(accountId)}`);
        if (r.ok) setBrandAvatars(await r.json());
      } catch { /* noop */ }
    })();
  }, [accountId]);

  const selectedBrandAvatar = useMemo(
    () => brandAvatars.find((a) => a.id === selectedBrandAvatarId) || null,
    [brandAvatars, selectedBrandAvatarId],
  );

  // When a Brand Avatar is picked, stamp its voice_id into the voice select too.
  useEffect(() => {
    if (selectedBrandAvatar?.voice_id) setVoiceId(selectedBrandAvatar.voice_id);
  }, [selectedBrandAvatar]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sanitized-spoken preview (verbatim @242-246)
  const { spoken, hadStructure } = useMemo(() => sanitizeScript(script), [script]);
  const spokenWordCount = spoken.trim().split(/\s+/).filter(Boolean).length;
  const spokenEstSeconds = Math.ceil(spokenWordCount / WORDS_PER_SEC);
  const wordCount = script.trim().split(/\s+/).filter(Boolean).length;
  const estSeconds = Math.ceil(wordCount / WORDS_PER_SEC);

  // Photo upload handler (verbatim @298-324)
  const handlePhotoChange = useCallback(async (file: File | null) => {
    setPhotoFile(file);
    setTalkingPhotoId(null);
    if (!file) return;
    setPhotoUploading(true);
    render.setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const r = await fetch('/api/video/talking-photo', { method: 'POST', body: fd });
      if (!r.ok) {
        const txt = await r.text();
        throw new Error(`Upload failed: ${r.status} — ${txt.slice(0, 200)}`);
      }
      const data = await r.json();
      if (data.talking_photo_id) setTalkingPhotoId(data.talking_photo_id);
      else throw new Error('No talking_photo_id in response');
    } catch (e) {
      render.setError(e instanceof Error ? e.message : 'photo upload failed');
      setPhotoFile(null);
    } finally {
      setPhotoUploading(false);
    }
  }, [render]);

  const canRender = !!(spoken || script.trim()) && !render.rendering && !photoUploading;

  const doRender = () => render.renderAvatarSnap({
    script: spoken || script.trim(),
    voiceId, avatarId, talkingPhotoId, aspect, accountId, campaignId,
    // Brand Avatar supplies a consistent face soul_id (non-lipsync pipeline).
    soulId: selectedBrandAvatar?.soul_id || null,
  });

  return (
    <div className="space-y-5 max-w-[880px]">
      {/* ── STEP 1 — Write the script ── */}
      <section>
        <LaneLabel>Step 1 · Write the script</LaneLabel>
        <ScriptGenerator
          accountId={accountId}
          campaignId={campaignId}
          campaignName={campaignName}
          onUseScript={(block) => setScript(block)}
        />

        <div className="mt-3">
          <textarea
            value={script}
            onChange={(e) => setScript(e.target.value)}
            disabled={render.rendering}
            placeholder="Paste or write the script. Structured Script Generator output (HOOK/SCRIPT/CTA) is auto-extracted, only spoken lines go to the voice."
            className="w-full min-h-[80px] text-[13px] bg-surface-2 border border-border rounded-md px-2.5 py-1.5 text-text placeholder:text-muted-foreground/70 focus:outline-none focus:border-accent resize-y disabled:opacity-60"
          />
          {hadStructure && spoken && (
            <div className="mt-2 bg-accent-soft border border-accent/20 rounded-md px-2.5 py-2 text-[11px]">
              <div className="text-accent font-medium mb-0.5">Will speak ({spokenWordCount} words ≈ {spokenEstSeconds}s):</div>
              <div className="text-text/90 italic leading-relaxed">"{spoken}"</div>
            </div>
          )}
          {hadStructure && !spoken && (
            <div className="mt-2 bg-warning-soft border border-warning/30 rounded-md px-2.5 py-2 text-[11px] text-warning flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5" /> Could not extract a spoken script from the structured block.
            </div>
          )}
        </div>
      </section>

      {/* ── STEP 2 — Avatar and voice ── */}
      <section>
        <LaneLabel>Step 2 · Avatar and voice</LaneLabel>

        {/* Brand Avatar picker */}
        <div className="mb-3">
          {brandAvatars.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] text-muted-foreground inline-flex items-center gap-1"><UserRound className="h-3.5 w-3.5" /> Brand Avatars</span>
              <button
                onClick={() => setSelectedBrandAvatarId('')}
                className={cn('px-2.5 py-1 rounded-md text-[11px] border transition-colors', !selectedBrandAvatarId ? 'bg-accent-soft border-accent text-accent' : 'border-border text-muted-foreground hover:border-accent/50')}
              >
                None
              </button>
              {brandAvatars.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setSelectedBrandAvatarId(a.id)}
                  className={cn('px-2.5 py-1 rounded-md text-[11px] border transition-colors', selectedBrandAvatarId === a.id ? 'bg-accent-soft border-accent text-accent' : 'border-border text-muted-foreground hover:border-accent/50')}
                  title={a.style_notes || a.name}
                >
                  {a.name}
                </button>
              ))}
              {selectedBrandAvatar && (
                <span className="text-[10px] text-muted-foreground font-mono">
                  soul {selectedBrandAvatar.soul_id ? 'stamped' : 'none'} · voice {selectedBrandAvatar.voice_id ? 'set' : 'default'}
                </span>
              )}
            </div>
          ) : (
            <div className="text-[11px] text-muted-foreground">
              No Brand Avatars yet.{' '}
              <button onClick={onGoToSouls} className="text-accent hover:text-accent-hover underline-offset-2 hover:underline">Train a Brand Avatar in Souls</button>
              {' '}for a consistent face and voice across videos.
            </div>
          )}
        </div>

        {/* Photo upload */}
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <input
            ref={photoInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => handlePhotoChange(e.target.files?.[0] ?? null)}
            className="hidden"
            disabled={render.rendering}
          />
          {!photoFile ? (
            <button
              onClick={() => photoInputRef.current?.click()}
              disabled={render.rendering || photoUploading}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-dashed border-border hover:border-accent text-muted-foreground hover:text-accent disabled:opacity-50 transition-colors"
              title="Upload a face photo to use as the talking avatar"
            >
              <Upload className="h-3.5 w-3.5" /> Use a photo as avatar
            </button>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-accent-soft border border-accent text-accent">
              {photoUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />}
              <span className="truncate max-w-[160px]">{photoFile.name}</span>
              {talkingPhotoId && <span className="text-[10px] text-success">ready</span>}
              <button onClick={() => { setPhotoFile(null); setTalkingPhotoId(null); }} disabled={render.rendering || photoUploading} className="ml-1 text-muted-foreground hover:text-text"><X className="h-3 w-3" /></button>
            </div>
          )}

          {/* Aspect */}
          <div className="flex items-center gap-0.5 border border-border rounded-md overflow-hidden">
            {(['16:9', '9:16', '1:1'] as Aspect[]).map((a) => (
              <button
                key={a}
                onClick={() => setAspect(a)}
                disabled={render.rendering}
                className={cn('px-2 py-1 transition-colors', aspect === a ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:bg-surface-2')}
              >{a}</button>
            ))}
          </div>

          {/* Voice */}
          {voices.length > 0 && (
            <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} disabled={render.rendering} className="bg-surface-2 border border-border rounded-md px-2 py-1 text-text" title="Voice">
              {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
            </select>
          )}

          {/* Stock avatar (hidden when a photo is uploaded) */}
          {!talkingPhotoId && avatars.length > 0 && (
            <select value={avatarId} onChange={(e) => setAvatarId(e.target.value)} disabled={render.rendering} className="bg-surface-2 border border-border rounded-md px-2 py-1 text-text max-w-[160px]" title="Stock avatar">
              {avatars.map((a) => <option key={a.avatar_id} value={a.avatar_id}>{a.name}</option>)}
            </select>
          )}

          <span className="text-muted-foreground font-mono">{wordCount} words ≈ {estSeconds}s</span>
        </div>
      </section>

      {/* ── STEP 3 — Render ── */}
      <section>
        <LaneLabel>Step 3 · Render</LaneLabel>
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-muted-foreground font-mono">talking avatar · HeyGen</span>
          <RenderButton onClick={doRender} disabled={!canRender} busy={render.rendering} label={render.rendering ? 'Rendering…' : 'Render video'} />
        </div>
        <StatusStrip rendering={render.rendering} error={render.error} stage={render.stage} stageMsg={render.stageMsg} elapsed={render.elapsed} />
      </section>
    </div>
  );
}
