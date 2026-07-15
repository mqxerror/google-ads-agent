/**
 * useKineticLibrary — shared asset fetchers for the Kinetic lanes:
 * library images (b-roll), library audio (music beds), and the HeyGen
 * avatar + voice option lists.
 *
 * Extracted from VideoCreator's loadLibraryImages (@268-279),
 * loadLibraryAudio (@215-223), and the avatar/voice bootstrap (@249-265).
 * Same endpoints, same defaults.
 */

import { useState, useCallback, useEffect } from 'react';

export interface LibraryImage {
  id: string;
  filename: string;
  url: string;
  source: string;
  width?: number;
  height?: number;
}

export interface LibraryAudio {
  id: string;
  filename: string;
  url: string;
  size_bytes?: number | null;
}

export interface AvatarOption {
  avatar_id: string;
  name: string;
  preview_image_url?: string;
}

export interface VoiceOption {
  voice_id: string;
  name: string;
  labels?: Record<string, string>;
}

export function useLibraryImages(accountId?: string) {
  const [images, setImages] = useState<LibraryImage[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!accountId) { setImages([]); return; }
    setLoading(true);
    try {
      const qs = new URLSearchParams({ account_id: accountId, asset_type: 'image', limit: '60' });
      // Default to uploaded — brand b-roll. (verbatim from VideoCreator @272-275)
      qs.set('source', 'uploaded');
      const r = await fetch(`/api/assets?${qs}`);
      if (r.ok) setImages(await r.json());
    } catch { /* noop */ } finally { setLoading(false); }
  }, [accountId]);
  return { images, loading, load };
}

export function useLibraryAudio(accountId?: string) {
  const [audio, setAudio] = useState<LibraryAudio[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!accountId) { setAudio([]); return; }
    setLoading(true);
    try {
      const qs = new URLSearchParams({ account_id: accountId, asset_type: 'audio', limit: '60' });
      const r = await fetch(`/api/assets?${qs}`);
      if (r.ok) setAudio(await r.json());
    } catch { /* noop */ } finally { setLoading(false); }
  }, [accountId]);
  return { audio, loading, load };
}

/** Loads HeyGen avatars + voices once. Verbatim bootstrap from VideoCreator @249-265. */
export function useAvatarVoiceOptions(enabled: boolean) {
  const [avatars, setAvatars] = useState<AvatarOption[]>([]);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [avatarId, setAvatarId] = useState('');
  const [voiceId, setVoiceId] = useState('');

  useEffect(() => {
    if (!enabled) return;
    (async () => {
      try {
        const [av, vo] = await Promise.all([
          fetch('/api/video/avatars?limit=30').then(r => r.ok ? r.json() : []),
          fetch('/api/video/voices').then(r => r.ok ? r.json() : []),
        ]);
        setAvatars(av);
        setVoices(vo);
        setAvatarId((prev) => prev || (av[0]?.avatar_id ?? ''));
        setVoiceId((prev) => {
          if (prev) return prev;
          const sarah = vo.find((v: VoiceOption) => v.name === 'Sarah');
          return sarah?.voice_id ?? vo[0]?.voice_id ?? '';
        });
      } catch { /* noop */ }
    })();
  }, [enabled]);

  return { avatars, voices, avatarId, setAvatarId, voiceId, setVoiceId };
}

/** Detect "logo" library images (verbatim from VideoCreator @128). */
export const isLogoFilename = (name: string) => /(^|[^a-z])logo([^a-z]|$)/i.test(name);
