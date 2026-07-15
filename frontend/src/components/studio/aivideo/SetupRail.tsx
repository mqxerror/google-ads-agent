/**
 * SetupRail — the left column of the AI Video Studio. Owns the setup controls
 * (campaign link, Director consult, model chip, length, aspect, audio, brand
 * avatar) plus the empty-state brief → draft entry point. All state lives on
 * the page; this component is presentational + fires the callbacks it is given.
 */

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { fetchCampaigns, listBrandAvatars } from '@/lib/api';
import type { BrandAvatar } from '@/lib/api';
import { useClipMath } from '@/components/studio/useClipMath';
import { originLine, isSoulCapable } from './shared';
import type { BriefSourceType, RailControls } from './types';

const SOURCE_TABS: { id: BriefSourceType; label: string }[] = [
  { id: 'text', label: 'Write brief' },
  { id: 'campaign', label: 'From campaign' },
  { id: 'landing_page', label: 'From landing page' },
];

interface MusicAsset {
  id: string;
  filename: string;
  url: string;
}
interface Voice {
  voice_id: string;
  name: string;
}

const LENGTH_PRESETS = [15, 30, 60];
const ASPECT_FALLBACK = ['16:9', '9:16', '1:1', '4:5'];

export default function SetupRail(props: RailControls) {
  const {
    accountId,
    campaignId,
    onCampaignChange,
    consultDirector,
    onConsultChange,
    modelId,
    modelInfo,
    onOpenGallery,
    targetSeconds,
    onTargetChange,
    aspect,
    onAspectChange,
    audio,
    onAudioChange,
    avatar,
    onAvatarChange,
    brief,
    onBriefChange,
    briefSourceType,
    onBriefSourceTypeChange,
    landingUrl,
    onLandingUrlChange,
    draftError,
    hasStoryboard,
    drafting,
    onDraft,
  } = props;

  const navigate = useNavigate();
  const { maxClip, estClips } = useClipMath(modelInfo, targetSeconds);

  // Campaigns for the dropdown.
  const { data: campaigns } = useQuery({
    queryKey: ['campaigns', accountId],
    queryFn: () => fetchCampaigns(accountId),
    staleTime: 60_000,
    enabled: !!accountId,
  });

  // Aspect option list — clamp current into the model's legal set.
  const aspectOptions = modelInfo?.constraints.aspect_ratios?.length
    ? modelInfo.constraints.aspect_ratios
    : ASPECT_FALLBACK;
  useEffect(() => {
    if (aspectOptions.length && !aspectOptions.includes(aspect)) {
      onAspectChange(aspectOptions[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelId]);

  // Music assets + voices (minimal, fetched on demand when toggled on).
  const [music, setMusic] = useState<MusicAsset[]>([]);
  const [voices, setVoices] = useState<Voice[]>([]);

  useEffect(() => {
    if (!audio.musicOn || !accountId || music.length) return;
    let cancelled = false;
    fetch(`/api/assets?account_id=${encodeURIComponent(accountId)}&asset_type=audio&limit=60`)
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: MusicAsset[]) => {
        if (!cancelled) setMusic(Array.isArray(rows) ? rows : []);
      })
      .catch(() => { /* leave picker empty */ });
    return () => { cancelled = true; };
  }, [audio.musicOn, accountId, music.length]);

  useEffect(() => {
    if (!audio.voOn || voices.length) return;
    let cancelled = false;
    fetch('/api/video/voices')
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: Voice[]) => {
        if (cancelled) return;
        const list = Array.isArray(rows) ? rows : [];
        setVoices(list);
        if (!audio.voiceId && list.length) {
          const sarah = list.find((v) => v.name === 'Sarah');
          onAudioChange({ voiceId: (sarah ?? list[0]).voice_id });
        }
      })
      .catch(() => { /* leave voice unset */ });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audio.voOn, voices.length]);

  // Brand avatars — only when the model is soul-capable.
  const soulCapable = isSoulCapable(modelInfo); // §13 default (soul-capable gating)
  const { data: avatars } = useQuery({
    queryKey: ['brand-avatars', accountId],
    queryFn: () => listBrandAvatars(accountId),
    staleTime: 60_000,
    enabled: !!accountId && soulCapable,
  });

  const campaignLinked = !!campaignId;

  // Group campaigns for the selector: Active (ENABLED) vs everything else.
  // Reuses Sidebar's status field/comparison (c.status === 'ENABLED').
  // .filter is stable, preserving fetchCampaigns' original relative order.
  const activeCampaigns = campaigns?.filter((c) => c.status === 'ENABLED') ?? [];
  const pausedCampaigns = campaigns?.filter((c) => c.status !== 'ENABLED') ?? [];

  return (
    <div className="flex w-[264px] shrink-0 flex-col overflow-auto border-r border-border bg-surface">
      <div className="space-y-5 p-4">
        {/* Campaign */}
        <div className="space-y-1.5">
          <p className="label-section">Campaign</p>
          <select
            value={campaignId ?? ''}
            onChange={(e) => onCampaignChange(e.target.value || null)}
            className="h-8 w-full rounded border border-border bg-card px-2 text-xs text-text"
          >
            <option value="">No campaign</option>
            {activeCampaigns.length > 0 && (
              <optgroup label={`Active (${activeCampaigns.length})`}>
                {activeCampaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </optgroup>
            )}
            {pausedCampaigns.length > 0 && (
              <optgroup label={`Paused (${pausedCampaigns.length})`}>
                {pausedCampaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
          <label
            className={cn(
              'mt-1 flex items-center gap-2 text-[11px]',
              campaignLinked ? 'text-muted-foreground' : 'text-subtle',
            )}
            title={campaignLinked ? '' : 'Link a campaign to consult its Director'}
          >
            <input
              type="checkbox"
              disabled={!campaignLinked}
              checked={consultDirector}
              onChange={(e) => onConsultChange(e.target.checked)} // §13 default (consult defaults ON when linked)
            />
            Consult campaign Director
          </label>
        </div>

        {/* Model */}
        <div className="space-y-1.5">
          <p className="label-section">Model</p>
          <div className="flex items-center gap-2">
            <span className="min-w-0 flex-1 truncate rounded border border-border bg-card px-2 py-1.5 text-xs text-text">
              {modelInfo?.label ?? modelId}
            </span>
            <button
              onClick={onOpenGallery}
              className="shrink-0 rounded border border-border px-2 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-surface-2"
            >
              Change
            </button>
          </div>
          {modelInfo && originLine(modelInfo) && (
            <p className="text-[11px] text-subtle">{originLine(modelInfo)}</p>
          )}
        </div>

        {/* Length */}
        <div className="space-y-1.5">
          <p className="label-section">Length</p>
          <div className="flex gap-1.5">
            {LENGTH_PRESETS.map((s) => (
              <button
                key={s}
                onClick={() => onTargetChange(s)}
                className={cn(
                  'flex-1 rounded border px-2 py-1.5 text-xs transition-colors',
                  targetSeconds === s
                    ? 'border-strong bg-accent-soft text-accent'
                    : 'border-border text-muted-foreground hover:bg-surface-2',
                )}
              >
                {s}s
              </button>
            ))}
          </div>
          {maxClip && (
            <p className="font-mono text-[11px] text-subtle">
              ~ {estClips} clips x {maxClip}s
            </p>
          )}
        </div>

        {/* Aspect */}
        <div className="space-y-1.5">
          <p className="label-section">Aspect</p>
          <select
            value={aspect}
            onChange={(e) => onAspectChange(e.target.value)}
            className="h-8 w-full rounded border border-border bg-card px-2 text-xs text-text"
          >
            {aspectOptions.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>

        {/* Audio */}
        <div className="space-y-2">
          <p className="label-section">Audio</p>
          <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <input
              type="checkbox"
              checked={audio.musicOn}
              onChange={(e) => onAudioChange({ musicOn: e.target.checked })}
            />
            Music bed
          </label>
          {audio.musicOn && (
            <select
              value={audio.musicFilename ?? ''}
              onChange={(e) => onAudioChange({ musicFilename: e.target.value || null })}
              className="h-8 w-full rounded border border-border bg-card px-2 text-xs text-text"
            >
              <option value="">Pick a track</option>
              {music.map((m) => (
                <option key={m.id} value={m.filename}>
                  {m.filename}
                </option>
              ))}
            </select>
          )}
          <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <input
              type="checkbox"
              checked={audio.voOn}
              onChange={(e) => onAudioChange({ voOn: e.target.checked })}
            />
            Voiceover
          </label>
          {audio.voOn && (
            <select
              value={audio.voiceId ?? ''}
              onChange={(e) => onAudioChange({ voiceId: e.target.value || null })}
              className="h-8 w-full rounded border border-border bg-card px-2 text-xs text-text"
            >
              {voices.map((v) => (
                <option key={v.voice_id} value={v.voice_id}>
                  {v.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Brand Avatar (soul-capable models only) */}
        {soulCapable && (
          <div className="space-y-1.5">
            <p className="label-section">Brand Avatar</p>
            {avatars && avatars.length > 0 ? (
              <select
                value={avatar.soulId ?? ''}
                onChange={(e) => {
                  const picked = (avatars as BrandAvatar[]).find((a) => a.soul_id === e.target.value);
                  onAvatarChange({
                    soulId: e.target.value || null,
                    voiceId: picked?.voice_id ?? avatar.voiceId,
                  });
                }}
                className="h-8 w-full rounded border border-border bg-card px-2 text-xs text-text"
              >
                <option value="">none</option>
                {(avatars as BrandAvatar[])
                  .filter((a) => a.soul_id)
                  .map((a) => (
                    <option key={a.id} value={a.soul_id ?? ''}>
                      {a.name}
                    </option>
                  ))}
              </select>
            ) : (
              <button
                onClick={() => navigate('/studio#souls')}
                className="text-[11px] text-accent hover:underline"
              >
                Train a Brand Avatar in Souls
              </button>
            )}
          </div>
        )}

        {/* Empty state — brief → draft */}
        {!hasStoryboard && (() => {
          const urlOk = /^https?:\/\/\S+/i.test(landingUrl.trim());
          const canDraft =
            briefSourceType === 'campaign'
              ? campaignLinked
              : briefSourceType === 'landing_page'
                ? urlOk
                : !!brief.trim();
          return (
            <div className="space-y-2 rounded-lg border border-border bg-card p-3">
              <p className="text-xs font-medium text-text">Start with a brief</p>

              {/* source selector — segmented chips (matches Length pattern) */}
              <div className="flex gap-1.5">
                {SOURCE_TABS.map((t) => {
                  const disabled = t.id === 'campaign' && !campaignLinked;
                  return (
                    <button
                      key={t.id}
                      onClick={() => onBriefSourceTypeChange(t.id)}
                      disabled={disabled}
                      title={disabled ? 'Select a campaign first' : ''}
                      className={cn(
                        'flex-1 rounded border px-1.5 py-1.5 text-[10.5px] leading-tight transition-colors',
                        briefSourceType === t.id
                          ? 'border-strong bg-accent-soft text-accent'
                          : 'border-border text-muted-foreground hover:bg-surface-2',
                        disabled && 'cursor-not-allowed opacity-40 hover:bg-transparent',
                      )}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>

              {/* per-source input + helper copy */}
              {briefSourceType === 'text' && (
                <>
                  <p className="text-[11px] text-muted-foreground">
                    Describe the video, pick a model, then let the Director draft concepts.
                  </p>
                  <textarea
                    value={brief}
                    onChange={(e) => onBriefChange(e.target.value)}
                    rows={4}
                    placeholder="What is this video for? Product, audience, the one thing to land."
                    className="w-full resize-y rounded border border-border bg-surface-2 px-2 py-1.5 text-[12.5px] leading-snug text-text outline-none focus:border-strong"
                  />
                </>
              )}

              {briefSourceType === 'campaign' && (
                <p className="text-[11px] text-muted-foreground">
                  Director reads the campaign's guidelines, pinned facts and recent decisions
                </p>
              )}

              {briefSourceType === 'landing_page' && (
                <>
                  <p className="text-[11px] text-muted-foreground">
                    Director reads the page and anchors copy in its real claims
                  </p>
                  <input
                    type="url"
                    inputMode="url"
                    value={landingUrl}
                    onChange={(e) => onLandingUrlChange(e.target.value)}
                    placeholder="https://your-landing-page.com"
                    className="w-full rounded border border-border bg-surface-2 px-2 py-1.5 text-[12.5px] leading-snug text-text outline-none focus:border-strong"
                  />
                </>
              )}

              <button
                onClick={onDraft}
                disabled={drafting || !canDraft}
                className="flex w-full items-center justify-center gap-2 rounded border border-strong bg-accent px-3 py-2 text-xs font-medium text-on-accent transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                {drafting && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                Draft with Director
              </button>

              {draftError && (
                <p className="text-[11px] text-danger">{draftError}</p>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
