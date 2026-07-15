/**
 * BrandReelLane — "fast local render · Pillow + ffmpeg".
 * Hits POST /api/video/brand-reel (via useKineticRender.renderBrandReel).
 *
 * Recomposes the legacy VideoCreator brand-reel branch (@359-428, form
 * @809-1028) into the spacious two-column BRIEF / PREVIEW layout (plan
 * §7.1). Every raw color is a DESIGN.md token. Payload is byte-identical
 * to the legacy renderBrandReel (AC D1).
 */

import { useState, useCallback, useEffect } from 'react';
import { Loader2, Link as LinkIcon, X, AlertTriangle, ImageIcon, Folder, Music } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Field, LaneLabel, RenderButton, StatusStrip, BrollPickerModal, MusicPickerModal } from './KineticShared';
import { TypePreview } from './TypePreview';
import { useKineticRender, type Aspect } from './useKineticRender';
import { useLibraryImages, useLibraryAudio, useAvatarVoiceOptions } from './useKineticLibrary';

interface Props {
  accountId?: string;
  campaignId?: string | null;
  onVideoReady: (url: string, script: string, thumb?: string) => void;
}

export default function BrandReelLane({ accountId, campaignId, onVideoReady }: Props) {
  const render = useKineticRender({ onVideoReady: (r) => onVideoReady(r.url, r.script, r.thumbnail) });
  const { voices, voiceId, setVoiceId } = useAvatarVoiceOptions(true);
  const libImages = useLibraryImages(accountId);
  const libAudio = useLibraryAudio(accountId);

  // Fields (verbatim state from VideoCreator brand-reel)
  const [headline, setHeadline] = useState('');
  const [subhead, setSubhead] = useState('');
  const [statValue, setStatValue] = useState('');
  const [statLabel, setStatLabel] = useState('');
  const [cta, setCta] = useState('Book a free consultation');
  const [voiceoverScript, setVoiceoverScript] = useState('');
  const [aspect, setAspect] = useState<Aspect>('16:9');
  const [reelDuration, setReelDuration] = useState<15 | 30>(15);
  const [brollUrl, setBrollUrl] = useState<string | null>(null);
  const [brollFilename, setBrollFilename] = useState<string | null>(null);
  const [musicFilename, setMusicFilename] = useState<string | null>(null);

  // Auto-fill brief + URL
  const [brief, setBrief] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [autoFilling, setAutoFilling] = useState(false);
  const [autoFillError, setAutoFillError] = useState('');

  // Pickers
  const [showBroll, setShowBroll] = useState(false);
  const [showMusic, setShowMusic] = useState(false);
  useEffect(() => { if (showBroll) libImages.load(); }, [showBroll]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (showMusic) libAudio.load(); }, [showMusic]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-fill scenes — POST /api/video/brand-reel/generate-scenes (verbatim @360-391)
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
      if (!r.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `HTTP ${r.status}`);
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

  const canRender = !!headline.trim() && !render.rendering;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ── BRIEF (left) ── */}
      <div className="space-y-3">
        <LaneLabel>Brief</LaneLabel>

        {/* Auto-fill card */}
        <div className="space-y-2 p-3 bg-surface-2 border border-border rounded-lg">
          <div className="flex items-center gap-2">
            <input
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              disabled={render.rendering || autoFilling}
              placeholder={campaignId ? 'Brief, optional if a campaign is selected' : "Brief (e.g. 'Greece GV for UK retirees'), optional if a URL is set"}
              className="flex-1 text-[13px] bg-transparent text-text focus:outline-none placeholder:text-muted-foreground/70"
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); autoFillScenes(); } }}
            />
            <button
              onClick={autoFillScenes}
              disabled={render.rendering || autoFilling}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] bg-accent-soft text-accent hover:bg-accent-soft/80 disabled:opacity-50"
              title="Generate all scenes from the brief, URL, and/or campaign context"
            >
              {autoFilling ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              {autoFilling ? 'Generating…' : 'Auto-fill'}
            </button>
          </div>
          <div className="flex items-center gap-2">
            <LinkIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              disabled={render.rendering || autoFilling}
              placeholder="(Optional) URL, landing page or article. The agent reads it and anchors copy in real claims."
              className="flex-1 text-[13px] bg-transparent text-text focus:outline-none placeholder:text-muted-foreground/60"
            />
            {sourceUrl && (
              <button onClick={() => setSourceUrl('')} className="text-muted-foreground hover:text-text" title="Clear URL">
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
        {autoFillError && (
          <div className="text-[11px] text-danger bg-danger-soft border border-danger/30 rounded-md px-2.5 py-1.5 flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {autoFillError}
          </div>
        )}

        {/* Fields */}
        <Field value={headline} onChange={setHeadline} disabled={render.rendering || autoFilling} placeholder="Headline (Scene 1), e.g. 'Greece Golden Visa'" />
        <Field value={subhead} onChange={setSubhead} disabled={render.rendering} placeholder="Subhead (Scene 2 overlay), e.g. 'EU residency through real estate'" />
        <div className="grid grid-cols-2 gap-2">
          <Field value={statValue} onChange={setStatValue} disabled={render.rendering} placeholder="Stat (e.g. 'EUR 250K')" />
          <Field value={statLabel} onChange={setStatLabel} disabled={render.rendering} placeholder="Stat label (e.g. 'minimum investment')" />
        </div>
        <Field value={cta} onChange={setCta} disabled={render.rendering} placeholder="CTA (Scene 4), e.g. 'Book a free consultation'" />
        <Field value={voiceoverScript} onChange={setVoiceoverScript} disabled={render.rendering} multiline minH="min-h-[52px]" placeholder="(Optional) Voiceover script, leave empty for a silent reel" />
      </div>

      {/* ── PREVIEW (right) ── */}
      <div className="space-y-3">
        <TypePreview headline={headline} subhead={subhead} cta={cta} statValue={statValue} statLabel={statLabel} aspect={aspect} />

        {/* Controls: aspect / duration / b-roll / voice / music */}
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
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
          <div className="flex items-center gap-0.5 border border-border rounded-md overflow-hidden">
            {[15, 30].map((d) => (
              <button
                key={d}
                onClick={() => setReelDuration(d as 15 | 30)}
                disabled={render.rendering}
                className={cn('px-2.5 py-1 transition-colors', reelDuration === d ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:bg-surface-2')}
              >{d}s</button>
            ))}
          </div>

          {brollUrl ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-accent-soft text-accent">
              <ImageIcon className="h-3 w-3" />
              <span className="truncate max-w-[120px]">{brollFilename || 'b-roll'}</span>
              <button onClick={() => { setBrollUrl(null); setBrollFilename(null); }} disabled={render.rendering} className="ml-0.5 text-muted-foreground hover:text-text" title="Remove b-roll"><X className="h-3 w-3" /></button>
            </span>
          ) : (
            <button onClick={() => setShowBroll(true)} disabled={render.rendering} className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-dashed border-border hover:border-accent text-muted-foreground hover:text-accent transition-colors">
              <Folder className="h-3 w-3" /> Pick b-roll
            </button>
          )}

          {voices.length > 0 && (
            <select
              value={voiceId}
              onChange={(e) => setVoiceId(e.target.value)}
              disabled={render.rendering}
              className={cn('bg-surface-2 border rounded-md px-2 py-1', voiceoverScript.trim() ? 'border-accent text-text' : 'border-border text-muted-foreground')}
              title={voiceoverScript.trim() ? 'Voiceover voice' : 'Add a voiceover script to enable'}
            >
              {voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
            </select>
          )}

          {musicFilename ? (
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-accent-soft text-accent">
              <Music className="h-3 w-3" /><span className="truncate max-w-[100px]">{musicFilename}</span>
              <button onClick={() => setMusicFilename(null)} disabled={render.rendering} className="ml-0.5 text-muted-foreground hover:text-text" title="Remove music"><X className="h-3 w-3" /></button>
            </span>
          ) : (
            <button onClick={() => setShowMusic(true)} disabled={render.rendering} className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-dashed border-border hover:border-accent text-muted-foreground hover:text-accent transition-colors">
              <Music className="h-3 w-3" /> Music
            </button>
          )}
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="text-[11px] text-muted-foreground font-mono">local render, no credits · ~10s</span>
          <RenderButton
            onClick={() => render.renderBrandReel({
              headline, subhead, statValue, statLabel, cta, voiceoverScript,
              brollUrl, voiceId, aspect, reelDuration, accountId, campaignId,
            })}
            disabled={!canRender}
            busy={render.rendering}
            label={render.rendering ? 'Rendering…' : 'Render reel'}
          />
        </div>

        <StatusStrip rendering={render.rendering} error={render.error} stage={render.stage} stageMsg={render.stageMsg} elapsed={render.elapsed} />
      </div>

      {/* Modals */}
      {showBroll && (
        <BrollPickerModal
          images={libImages.images}
          loading={libImages.loading}
          onPick={(img) => { setBrollUrl(img.url); setBrollFilename(img.filename); setShowBroll(false); }}
          onClearAndClose={() => { setBrollUrl(null); setBrollFilename(null); setShowBroll(false); }}
          onClose={() => setShowBroll(false)}
        />
      )}
      {showMusic && (
        <MusicPickerModal
          audio={libAudio.audio}
          loading={libAudio.loading}
          onPick={(a) => { setMusicFilename(a.filename); setShowMusic(false); }}
          onClose={() => setShowMusic(false)}
        />
      )}
    </div>
  );
}
