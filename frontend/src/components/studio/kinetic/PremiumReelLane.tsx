/**
 * PremiumReelLane — "kinetic typography · Hyperframes GSAP".
 *
 * Two sub-lanes:
 *  - Single Reel → POST /api/video/premium-reel (useKineticRender.renderPremiumReel)
 *  - Brand Story → plan/preview/render two-phase (useBrandStoryPlan):
 *      POST /api/video/premium-reel/storyboard-plan  then  …/storyboard-render
 *
 * Recomposes VideoCreator's premium-reel branches (@430-545, @776-806,
 * @1030-1637). Storyboard cards are RESTYLED to the §3.3 card language:
 * bg-card border-border rounded-lg, mono duration/type chips, token colors,
 * transform/opacity motion. Payloads byte-identical to legacy (AC D2).
 */

import { useState, useEffect } from 'react';
import { Music, Link as LinkIcon, Folder, X, Lock, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Field, LaneLabel, RenderButton, StatusStrip, StoryboardPickerModal, MusicPickerModal, SceneImageSwapModal } from './KineticShared';
import { TypePreview } from './TypePreview';
import { useKineticRender } from './useKineticRender';
import { useBrandStoryPlan } from './useBrandStoryPlan';
import { useLibraryImages, useLibraryAudio, useAvatarVoiceOptions, isLogoFilename } from './useKineticLibrary';

type SubMode = 'single' | 'storyboard';

interface Props {
  accountId?: string;
  campaignId?: string | null;
  onVideoReady: (url: string, script: string, thumb?: string) => void;
}

export default function PremiumReelLane({ accountId, campaignId, onVideoReady }: Props) {
  const [subMode, setSubMode] = useState<SubMode>('single');
  const render = useKineticRender({ onVideoReady: (r) => onVideoReady(r.url, r.script, r.thumbnail) });
  const story = useBrandStoryPlan({
    accountId, campaignId,
    consumeStream: render.consumeStream,
    setRendering: render.setRendering,
    setStage: render.setStage,
    setStageMsg: render.setStageMsg,
    setError: render.setError,
  });
  const { voices, voiceId, setVoiceId } = useAvatarVoiceOptions(true);
  const libImages = useLibraryImages(accountId);
  const libAudio = useLibraryAudio(accountId);

  // Shared fields (single + used as brief seed)
  const [headline, setHeadline] = useState('');
  const [subhead, setSubhead] = useState('');
  const [statValue, setStatValue] = useState('');
  const [statLabel, setStatLabel] = useState('');
  const [cta, setCta] = useState('Book a free consultation');
  const [voiceoverScript, setVoiceoverScript] = useState('');
  const [musicFilename, setMusicFilename] = useState<string | null>(null);

  // Brand Story fields
  const [brief, setBrief] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [targetSeconds, setTargetSeconds] = useState<30 | 60 | 90>(60);
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [overrideSceneCount, setOverrideSceneCount] = useState<number | null>(null);
  const [useBriefVerbatim, setUseBriefVerbatim] = useState(false);

  // Pickers
  const [showStoryboardPicker, setShowStoryboardPicker] = useState(false);
  const [showMusic, setShowMusic] = useState(false);
  useEffect(() => {
    if (showStoryboardPicker || story.swapImageForScene !== null) libImages.load();
  }, [showStoryboardPicker, story.swapImageForScene]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (showMusic) libAudio.load(); }, [showMusic]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-run stock search when swap modal opens on stock tab with a query (verbatim @290-295)
  useEffect(() => {
    if (story.swapImageForScene !== null && story.swapMode === 'stock' && story.stockQuery.trim() && story.stockMatches.length === 0) {
      story.runStockSearch(story.stockQuery);
    }
  }, [story.swapImageForScene, story.swapMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const singleCanRender = !!headline.trim() && !render.rendering;
  const storyCanRender = story.plannedScenes
    ? !render.rendering
    : (!!brief.trim() || !!sourceUrl.trim() || selectedImages.size > 0) && !render.rendering && !story.planning;

  return (
    <div className="space-y-4">
      {/* Sub-lane toggle */}
      <div className="inline-flex items-center gap-1 p-0.5 bg-surface-2 border border-border rounded-lg">
        {([
          { k: 'single', label: 'Single Reel', hint: '3 scenes · 12s' },
          { k: 'storyboard', label: 'Brand Story', hint: 'N scenes · plan then render' },
        ] as const).map((t) => (
          <button
            key={t.k}
            onClick={() => setSubMode(t.k)}
            disabled={render.rendering}
            className={cn(
              'px-3 py-1.5 rounded-md text-[12px] font-medium transition-colors',
              subMode === t.k ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:text-text',
            )}
          >
            {t.label} <span className="text-[10px] text-muted-foreground/80 font-normal ml-1">{t.hint}</span>
          </button>
        ))}
      </div>

      {/* ── SINGLE REEL ── */}
      {subMode === 'single' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-3">
            <LaneLabel>Brief</LaneLabel>
            <Field value={headline} onChange={setHeadline} disabled={render.rendering} placeholder="Headline (Scene 1), e.g. 'Greece Golden Visa'" />
            <Field value={subhead} onChange={setSubhead} disabled={render.rendering} placeholder="Subhead (Scene 2 overlay)" />
            <div className="grid grid-cols-2 gap-2">
              <Field value={statValue} onChange={setStatValue} disabled={render.rendering} placeholder="Stat (e.g. 'EUR 250K')" />
              <Field value={statLabel} onChange={setStatLabel} disabled={render.rendering} placeholder="Stat label" />
            </div>
            <Field value={cta} onChange={setCta} disabled={render.rendering} placeholder="CTA (Scene 4)" />
            <Field value={voiceoverScript} onChange={setVoiceoverScript} disabled={render.rendering} multiline minH="min-h-[52px]" placeholder="(Optional) Voiceover script, leave empty for a silent reel" />
          </div>

          <div className="space-y-3">
            <TypePreview headline={headline} subhead={subhead} cta={cta} statValue={statValue} statLabel={statLabel} aspect="16:9" />
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span className="px-2 py-1 rounded-md text-muted-foreground bg-surface-2 border border-border font-mono">1920×1080 · 12s · GSAP kinetic</span>
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
                  <button onClick={() => setMusicFilename(null)} disabled={render.rendering} className="ml-0.5 text-muted-foreground hover:text-text"><X className="h-3 w-3" /></button>
                </span>
              ) : (
                <button onClick={() => setShowMusic(true)} disabled={render.rendering} className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-dashed border-border hover:border-accent text-muted-foreground hover:text-accent transition-colors">
                  <Music className="h-3 w-3" /> Music
                </button>
              )}
            </div>
            <div className="flex items-center justify-between pt-1">
              <span className="text-[11px] text-muted-foreground font-mono">Hyperframes render · ~80s</span>
              <RenderButton
                onClick={() => render.renderPremiumReel({ headline, subhead, statValue, statLabel, cta, voiceoverScript, voiceId, musicFilename, accountId, campaignId })}
                disabled={!singleCanRender}
                busy={render.rendering}
                label={render.rendering ? 'Rendering…' : 'Render premium'}
              />
            </div>
            <StatusStrip rendering={render.rendering} error={render.error} stage={render.stage} stageMsg={render.stageMsg} elapsed={render.elapsed} />
          </div>
        </div>
      )}

      {/* ── BRAND STORY ── */}
      {subMode === 'storyboard' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* BRIEF */}
            <div className="space-y-3">
              <LaneLabel>Story brief</LaneLabel>

              {/* Script-handling mode: Creative vs Verbatim (lock uses warning token per §7.2) */}
              <div className="flex items-center gap-1 p-0.5 border border-border rounded-lg text-[12px]">
                <button
                  onClick={() => setUseBriefVerbatim(false)}
                  disabled={render.rendering || story.planning}
                  className={cn('flex-1 px-2.5 py-1.5 rounded-md transition-colors', !useBriefVerbatim ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:bg-surface-2')}
                  title="Director writes captions, picks images, and structures the story"
                >
                  Creative, let the agent write captions
                </button>
                <button
                  onClick={() => setUseBriefVerbatim(true)}
                  disabled={render.rendering || story.planning}
                  className={cn('flex-1 inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-md transition-colors', useBriefVerbatim ? 'bg-warning-soft text-warning' : 'text-muted-foreground hover:bg-surface-2')}
                  title="Use the brief text verbatim, no rewriting. For legal or regulated copy."
                >
                  <Lock className="h-3 w-3" /> Verbatim, use my script as-is
                </button>
              </div>

              <Field
                value={brief}
                onChange={setBrief}
                disabled={render.rendering}
                multiline
                placeholder={useBriefVerbatim
                  ? 'Paste your script verbatim. Every sentence becomes a scene caption, exactly as written.'
                  : "Brief, what's the story? e.g. 'Mercan Group brand video, 37 years, 4,100 families, hotel investment immigration'"}
              />

              <div className="flex items-center gap-2">
                <LinkIcon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                <input
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  disabled={render.rendering}
                  placeholder="(Optional) URL, landing page or article. The Director reads it for real claims."
                  className="flex-1 text-[13px] bg-surface-2 border border-border rounded-md px-2.5 py-1.5 text-text focus:outline-none focus:border-accent placeholder:text-muted-foreground/60"
                />
              </div>

              {/* Image multi-select trigger */}
              <button
                onClick={() => setShowStoryboardPicker(true)}
                disabled={render.rendering}
                className={cn(
                  'w-full flex items-center justify-between px-2.5 py-2 rounded-md text-[12px] border transition-colors',
                  selectedImages.size > 0 ? 'bg-accent-soft border-accent text-accent' : 'border-dashed border-border text-muted-foreground hover:border-accent hover:text-accent',
                )}
              >
                <span className="flex items-center gap-1.5">
                  <Folder className="h-3.5 w-3.5" />
                  {selectedImages.size > 0 ? `${selectedImages.size} image${selectedImages.size === 1 ? '' : 's'} selected for b-roll` : 'Pick library images for b-roll scenes (multi-select)'}
                </span>
                <span className="text-[10px] text-muted-foreground">tap to {selectedImages.size > 0 ? 'edit' : 'pick'}</span>
              </button>

              <Field value={voiceoverScript} onChange={setVoiceoverScript} disabled={render.rendering} multiline minH="min-h-[52px]" placeholder="(Optional) Voiceover script, leave empty for a silent reel" />
            </div>

            {/* CONTROLS + PREVIEW */}
            <div className="space-y-3">
              <LaneLabel>Settings</LaneLabel>
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <div className="flex items-center gap-0.5 border border-border rounded-md overflow-hidden">
                  {([30, 60, 90] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => setTargetSeconds(s)}
                      disabled={render.rendering}
                      className={cn('px-2.5 py-1 transition-colors', targetSeconds === s ? 'bg-accent-soft text-accent' : 'text-muted-foreground hover:bg-surface-2')}
                    >{s}s</button>
                  ))}
                </div>

                {/* Scene count override */}
                {(() => {
                  const recommended = Math.max(3, Math.round(targetSeconds / 4.6));
                  const showing = overrideSceneCount ?? recommended;
                  const isOverride = overrideSceneCount !== null && overrideSceneCount !== recommended;
                  return (
                    <div className="flex items-center gap-0.5 px-1.5 py-1 rounded-md text-text bg-surface-2 border border-border">
                      <button onClick={() => setOverrideSceneCount(Math.max(3, showing - 1))} disabled={render.rendering || story.planning} className="w-4 text-muted-foreground hover:text-text disabled:opacity-40" title="Fewer scenes">−</button>
                      <input
                        type="number" min={3} max={40} value={showing}
                        onChange={(e) => { const v = parseInt(e.target.value, 10); setOverrideSceneCount(Number.isFinite(v) && v >= 3 ? v : null); }}
                        disabled={render.rendering || story.planning}
                        className="w-7 bg-transparent text-center font-mono border-0 focus:outline-none"
                        title="Number of scenes"
                      />
                      <button onClick={() => setOverrideSceneCount(Math.min(40, showing + 1))} disabled={render.rendering || story.planning} className="w-4 text-muted-foreground hover:text-text disabled:opacity-40" title="More scenes">+</button>
                      <span className="text-[9px] text-muted-foreground ml-0.5">scenes</span>
                      {isOverride ? (
                        <button onClick={() => setOverrideSceneCount(null)} disabled={render.rendering || story.planning} className="text-[9px] text-accent hover:text-accent-hover ml-1 inline-flex items-center gap-0.5" title={`Reset to recommended (${recommended})`}>
                          <RotateCcw className="h-2.5 w-2.5" /> {recommended}
                        </button>
                      ) : (
                        <span className="text-[9px] text-muted-foreground/60 ml-1" title="Recommended">rec</span>
                      )}
                    </div>
                  );
                })()}

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
                    <button onClick={() => setMusicFilename(null)} disabled={render.rendering} className="ml-0.5 text-muted-foreground hover:text-text"><X className="h-3 w-3" /></button>
                  </span>
                ) : (
                  <button onClick={() => setShowMusic(true)} disabled={render.rendering} className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-dashed border-border hover:border-accent text-muted-foreground hover:text-accent transition-colors">
                    <Music className="h-3 w-3" /> Music
                  </button>
                )}
              </div>

              <div className="text-[11px] text-muted-foreground italic">
                {story.plannedScenes
                  ? `Review the scenes below, about ${Math.ceil((story.planningEta || 0) / 60)} min to render.`
                  : 'Step 1: plan the storyboard (~30s). Then preview the scenes before the long render.'}
              </div>

              <div className="flex items-center justify-end pt-1">
                <RenderButton
                  onClick={() => {
                    if (story.plannedScenes) {
                      story.renderPlannedStoryboard({ brief, targetSeconds, voiceoverScript, voiceId, musicFilename });
                    } else {
                      story.planBrandStory({ brief, sourceUrl, targetSeconds, overrideSceneCount, selectedImages, voiceoverScript, voiceId, useBriefVerbatim });
                    }
                  }}
                  disabled={!storyCanRender}
                  busy={story.planning || render.rendering}
                  label={
                    story.planning ? 'Planning storyboard…'
                    : render.rendering ? 'Rendering…'
                    : story.plannedScenes ? `Render ${story.plannedScenes.length} scenes`
                    : 'Plan storyboard'
                  }
                />
              </div>
              <StatusStrip rendering={render.rendering} error={render.error} stage={render.stage} stageMsg={render.stageMsg} elapsed={render.elapsed} />
            </div>
          </div>

          {/* ── Storyboard preview — §3.3 card language ── */}
          {story.plannedScenes && story.plannedScenes.length > 0 && !render.rendering && (
            <div className="border border-border rounded-lg overflow-hidden bg-surface-2">
              <div className="px-3.5 py-2.5 border-b border-border flex items-center justify-between">
                <span className="label-section text-text">Storyboard · {story.plannedScenes.length} scenes · click any field to edit</span>
                <button
                  onClick={() => story.planBrandStory({ brief, sourceUrl, targetSeconds, overrideSceneCount, selectedImages, voiceoverScript, voiceId, useBriefVerbatim })}
                  disabled={story.planning}
                  className="text-[11px] text-muted-foreground hover:text-accent underline-offset-2 hover:underline disabled:opacity-50 inline-flex items-center gap-1"
                  title="Re-roll the storyboard"
                >
                  <RotateCcw className="h-3 w-3" /> regenerate
                </button>
              </div>
              <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                {story.plannedScenes.map((s, i) => (
                  <StoryboardCard
                    key={i}
                    idx={i}
                    scene={s}
                    imageLookup={story.imageLookup}
                    onUpdate={(patch) => story.updateScene(i, patch)}
                    onSwapImage={() => {
                      const q = String(s.image_search_query || s.caption || '');
                      story.setStockQuery(q);
                      const fn = String(s.image_filename || '');
                      story.setSwapMode(fn ? 'library' : 'stock');
                      story.setSwapImageForScene(i);
                    }}
                    onDelete={() => story.setPlannedScenes((prev) => prev ? prev.filter((_, j) => j !== i) : prev)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modals */}
      {showStoryboardPicker && (
        <StoryboardPickerModal
          images={libImages.images}
          loading={libImages.loading}
          selected={selectedImages}
          onToggle={(filename) => setSelectedImages((prev) => {
            const next = new Set(prev);
            if (next.has(filename)) next.delete(filename); else next.add(filename);
            return next;
          })}
          onClear={() => setSelectedImages(new Set())}
          onClose={() => setShowStoryboardPicker(false)}
        />
      )}
      {showMusic && (
        <MusicPickerModal audio={libAudio.audio} loading={libAudio.loading} onPick={(a) => { setMusicFilename(a.filename); setShowMusic(false); }} onClose={() => setShowMusic(false)} />
      )}
      {story.swapImageForScene !== null && (
        <SceneImageSwapModal
          sceneIdx={story.swapImageForScene}
          images={libImages.images}
          swapMode={story.swapMode}
          setSwapMode={story.setSwapMode}
          stockQuery={story.stockQuery}
          setStockQuery={story.setStockQuery}
          stockMatches={story.stockMatches}
          stockSearching={story.stockSearching}
          runStockSearch={story.runStockSearch}
          aiPrompt={story.aiPrompt}
          setAiPrompt={story.setAiPrompt}
          aiGenerating={story.aiGenerating}
          onPickLibrary={(img) => {
            const stored = (img.url || '').split('/').pop() || img.filename;
            story.updateScene(story.swapImageForScene!, { image_filename: stored });
            story.setImageLookup((prev) => ({ ...prev, [stored]: img.url }));
            story.setSwapImageForScene(null);
          }}
          onAdoptStock={(m) => story.adoptStock(m, story.swapImageForScene!)}
          onGenerateAi={(prompt) => story.generateAiImage(prompt, story.swapImageForScene!)}
          onClose={() => story.setSwapImageForScene(null)}
        />
      )}
    </div>
  );
}

// ── Storyboard scene card (§3.3 card language) ──
function StoryboardCard({
  idx, scene, imageLookup, onUpdate, onSwapImage, onDelete,
}: {
  idx: number;
  scene: Record<string, unknown>;
  imageLookup: Record<string, string>;
  onUpdate: (patch: Record<string, unknown>) => void;
  onSwapImage: () => void;
  onDelete: () => void;
}) {
  const t = String(scene.type || 'scene');
  const fn = String(scene.image_filename || '');
  const thumb = fn ? imageLookup[fn] : null;
  const dur = Number(scene.duration || 0);

  return (
    <div className="group rounded-lg border border-border bg-surface p-3 shadow-[var(--shadow-resting)] transition-[transform,opacity,box-shadow] duration-200 hover:shadow-[var(--shadow-elevated)]">
      {/* Header row: index · type chip · duration chip · delete */}
      <div className="flex items-center gap-2 mb-2">
        <span className="font-mono text-[10px] text-muted-foreground">{String(idx + 1).padStart(2, '0')}</span>
        <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-surface-2 border border-border text-muted-foreground uppercase tracking-wide">{t}</span>
        {dur > 0 && <span className="font-mono text-[9px] px-1.5 py-0.5 rounded bg-surface-2 border border-border text-muted-foreground">{dur}s</span>}
        <button onClick={onDelete} className="ml-auto w-5 h-5 flex items-center justify-center rounded text-muted-foreground/50 hover:text-danger hover:bg-danger-soft transition-colors" title="Remove scene">
          <X className="h-3 w-3" />
        </button>
      </div>

      <div className="flex gap-3">
        {/* Thumbnail (broll) */}
        {t === 'broll' ? (
          <button
            onClick={onSwapImage}
            className={cn(
              'shrink-0 w-24 h-[54px] rounded-md overflow-hidden border block transition-colors relative',
              thumb ? 'bg-surface-2 border-border hover:border-accent' : 'bg-warning-soft border-warning/40 hover:border-warning',
            )}
            title={thumb ? `Click to swap · ${fn}` : `Needs image, click to pick (query: "${String(scene.image_search_query || '')}")`}
          >
            {thumb
              ? <img src={thumb} alt="" className="w-full h-full object-cover" />
              : <span className="flex items-center justify-center w-full h-full text-warning text-lg">!</span>}
            {fn && isLogoFilename(fn) && <span className="absolute top-0 right-0 text-[7px] px-0.5 bg-warning-soft text-warning rounded-bl font-mono uppercase leading-none">l</span>}
          </button>
        ) : (
          <div className="shrink-0 w-24 h-[54px] rounded-md bg-surface-2 border border-border flex items-center justify-center">
            <span className="font-mono text-[9px] text-muted-foreground uppercase">{t}</span>
          </div>
        )}

        {/* Editable fields */}
        <div className="flex-1 min-w-0 space-y-1.5">
          {t === 'hero' && (
            <CardInput value={String(scene.headline || '')} onChange={(v) => onUpdate({ headline: v })} placeholder="Hero headline" bold />
          )}
          {t === 'broll' && (
            <CardInput value={String(scene.caption || '')} onChange={(v) => onUpdate({ caption: v })} placeholder="Caption" />
          )}
          {t === 'logo' && (
            <CardInput value={String(scene.brand_name || '')} onChange={(v) => onUpdate({ brand_name: v })} placeholder="Brand name" bold />
          )}
          {t === 'stat' && (
            <div className="flex gap-2 items-baseline">
              <CardInput value={String(scene.stat_value || '')} onChange={(v) => onUpdate({ stat_value: v })} placeholder="#" bold className="w-20" />
              <CardInput value={String(scene.stat_label || '')} onChange={(v) => onUpdate({ stat_label: v })} placeholder="Label" />
            </div>
          )}
          {t === 'cta' && (
            <CardInput value={String(scene.cta || '')} onChange={(v) => onUpdate({ cta: v })} placeholder="Call to action" bold />
          )}

          {/* Broll motion pickers */}
          {t === 'broll' && (
            <div className="flex flex-wrap gap-1.5">
              <MiniSelect value={String(scene.composition || 'fullbleed')} onChange={(v) => onUpdate({ composition: v })} options={[['fullbleed', 'full'], ['letterbox', 'letterbox'], ['split', 'split'], ['lowerthird', 'lower⅓']]} title="Layout" />
              <MiniSelect value={String(scene.motion || 'kenburns-zoom-in')} onChange={(v) => onUpdate({ motion: v })} options={[['kenburns-zoom-in', 'zoom in'], ['kenburns-zoom-out', 'zoom out'], ['pan-left', 'pan L>R'], ['pan-right', 'pan R>L'], ['dolly-in', 'dolly'], ['parallax-tilt', 'parallax']]} title="Camera motion" />
              <MiniSelect value={String(scene.text_treatment || 'blur-stagger')} onChange={(v) => onUpdate({ text_treatment: v })} options={[['blur-stagger', 'blur'], ['slide-up', 'slide'], ['scale-bounce', 'bounce'], ['typewriter', 'typer'], ['scale-bounce-chars', 'chars'], ['mask-reveal', 'mask']]} title="Text reveal" />
            </div>
          )}

          {/* Per-scene instruction note */}
          <input
            value={String(scene.instructions || '')}
            onChange={(e) => onUpdate({ instructions: e.target.value })}
            placeholder="Instructions (optional, e.g. 'use Portugal flag')"
            className={cn(
              'w-full text-[10px] italic bg-transparent border-b border-transparent hover:border-border focus:border-accent focus:outline-none py-0.5 truncate transition-colors',
              scene.instructions ? 'text-accent' : 'text-muted-foreground/70 opacity-0 group-hover:opacity-100',
            )}
          />
        </div>
      </div>
    </div>
  );
}

function CardInput({ value, onChange, placeholder, bold, className }: { value: string; onChange: (v: string) => void; placeholder: string; bold?: boolean; className?: string }) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn(
        'w-full text-[12px] bg-transparent text-text border-b border-transparent hover:border-border focus:border-accent focus:outline-none py-0.5 truncate transition-colors',
        bold && 'font-semibold', className,
      )}
    />
  );
}

function MiniSelect({ value, onChange, options, title }: { value: string; onChange: (v: string) => void; options: [string, string][]; title: string }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="text-[9px] bg-surface-2 border border-border rounded px-1 py-0.5 text-muted-foreground hover:border-accent focus:border-accent focus:outline-none transition-colors"
      title={title}
    >
      {options.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
    </select>
  );
}
