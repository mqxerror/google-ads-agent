"""Premium Reel — Hyperframes (HTML+GSAP+headless Chrome) rendering pipeline.

Sister to brand_reel.py. Same SSE event shape, same output destination
(ad_assets), same scene-data inputs. Difference: every scene is rendered as
a full HTML composition with per-letter / per-element kinetic typography
animations powered by GSAP timelines, then exported to MP4 by the Hyperframes
CLI (headless Chrome → ffmpeg).

The 3 Premium Reel templates live under
  backend/hyperframes/video-projects/{mercan-hero,mercan-stat,mercan-cta}/
Each template has a `data-*` attribute on its #root that we string-replace
to inject the scene's content before invoking `npx hyperframes render`.

Total render time ≈ 60-90s per reel (3 scenes × 20s each + stitch). All local.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from app.config import settings
from app.services.video import ASSETS_DIR, elevenlabs_tts

logger = logging.getLogger(__name__)


# Where the Hyperframes student kit + our scene templates live
HYPERFRAMES_ROOT = Path(__file__).parent.parent.parent / "hyperframes"
TEMPLATE_HERO  = HYPERFRAMES_ROOT / "video-projects" / "mercan-hero"
TEMPLATE_STAT  = HYPERFRAMES_ROOT / "video-projects" / "mercan-stat"
TEMPLATE_CTA   = HYPERFRAMES_ROOT / "video-projects" / "mercan-cta"
TEMPLATE_LOGO  = HYPERFRAMES_ROOT / "video-projects" / "brand-logo"

# Broll has multiple "composition" templates — Director picks one per scene
# from a palette so consecutive broll scenes don't all share the same layout.
BROLL_COMPOSITIONS = {
    "fullbleed":   HYPERFRAMES_ROOT / "video-projects" / "mercan-broll",       # default — caption bottom-left
    "letterbox":   HYPERFRAMES_ROOT / "video-projects" / "broll-letterbox",    # 21:9 cinematic with corner brackets
    "split":       HYPERFRAMES_ROOT / "video-projects" / "broll-split",        # image left, copy right
    "lowerthird":  HYPERFRAMES_ROOT / "video-projects" / "broll-lowerthird",   # broadcast lower-third strip
}
TEMPLATE_BROLL = BROLL_COMPOSITIONS["fullbleed"]

# Map storyboard `type` → (default_template_dir, default_duration_s, attr_keys)
# For broll, the actual template is selected per-scene from BROLL_COMPOSITIONS
# based on the scene's `composition` field — see _template_for_scene().
TYPE_TO_TEMPLATE = {
    "hero":  (TEMPLATE_HERO,  4.0, ["headline", "brand-name", "tagline"]),
    "broll": (TEMPLATE_BROLL, 5.0, ["image-path", "caption", "scene-label", "motion", "text-treatment"]),
    "stat":  (TEMPLATE_STAT,  4.0, ["stat-value", "stat-label"]),
    "cta":   (TEMPLATE_CTA,   5.0, ["cta", "logo-path", "brand-name", "tagline"]),
    "logo":  (TEMPLATE_LOGO,  4.0, ["logo-path", "brand-name", "tagline"]),
}


def _template_for_scene(scene: dict) -> Path:
    """Return the template directory to use for a given scene. For broll
    scenes, picks the composition variant; for everything else, returns the
    default template registered in TYPE_TO_TEMPLATE.
    """
    stype = (scene.get("type") or "").lower()
    if stype == "broll":
        comp = (scene.get("composition") or "fullbleed").lower()
        return BROLL_COMPOSITIONS.get(comp, BROLL_COMPOSITIONS["fullbleed"])
    return TYPE_TO_TEMPLATE[stype][0]


@dataclass
class PremiumReelRequest:
    headline: str
    subhead: str = ""               # not yet used (no broll template); kept for future parity
    stat_value: str = ""
    stat_label: str = ""
    cta: str = "Book a free consultation"
    voiceover_script: str = ""
    voice_id: Optional[str] = None
    music_path: Optional[Path] = None      # royalty-free music bed (already resolved to local disk)
    quality: str = "draft"          # draft | standard | high (Hyperframes flag)


# ── Public API ─────────────────────────────────────────────────────


async def generate_premium_reel(req: PremiumReelRequest) -> AsyncIterator[dict]:
    """Render the 3-scene Premium Reel and yield SSE-style progress events."""
    if not _hyperframes_available():
        yield {"type": "error", "stage": "deps",
               "message": "Hyperframes not installed — run `npm install` in backend/hyperframes/"}
        return

    reel_id = str(uuid.uuid4())
    work_root = Path(tempfile.mkdtemp(prefix=f"premiumreel-{reel_id[:8]}-"))
    try:
        # 1-3. Render the three scenes in sequence (parallel was too memory-hungry
        # for the 16 GB machine — Chrome workers compete for RAM).
        scenes_specs = [
            ("hero", TEMPLATE_HERO, {"headline": req.headline}),
            ("stat", TEMPLATE_STAT, {
                "stat-value": req.stat_value or "EUR 250K",
                "stat-label": req.stat_label or "minimum investment",
            }),
            ("cta", TEMPLATE_CTA, {"cta": req.cta or "Book a free consultation"}),
        ]
        scene_mp4s: list[Path] = []
        for i, (name, tpl, data_attrs) in enumerate(scenes_specs, 1):
            yield {"type": "status", "stage": f"scene{i}",
                   "message": f"Rendering {name} (Hyperframes · GSAP · headless Chrome)..."}
            scene_dir = work_root / f"s{i}_{name}"
            _prepare_scene(tpl, scene_dir, data_attrs)
            mp4 = await _render_with_hyperframes(scene_dir, quality=req.quality)
            scene_mp4s.append(mp4)

        # 4. Optional voiceover (ElevenLabs, same as Brand Reel)
        audio_path: Optional[Path] = None
        if req.voiceover_script:
            if not settings.ELEVENLABS_API_KEY:
                yield {"type": "status", "stage": "voice-skipped",
                       "message": "VO requested but ELEVENLABS_API_KEY not set — render will be silent."}
            else:
                yield {"type": "status", "stage": "voice", "message": "Generating voiceover (ElevenLabs)..."}
                try:
                    voice_id = req.voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID
                    audio_bytes = await elevenlabs_tts(req.voiceover_script, voice_id)
                    audio_path = work_root / "vo.mp3"
                    audio_path.write_bytes(audio_bytes)
                except Exception as e:
                    logger.warning("Premium Reel VO failed: %s", e)
                    yield {"type": "status", "stage": "voice-failed",
                           "message": f"VO generation failed — continuing silent. Reason: {str(e)[:200]}"}

        # 5. Stitch with crossfades + fade-to-black + audio mux
        yield {"type": "status", "stage": "stitch", "message": "Stitching scenes with crossfades..."}
        out_path = ASSETS_DIR / f"{reel_id}.mp4"
        await _stitch_mp4s(scene_mp4s, audio_path, out_path, music=req.music_path)

        size_bytes = out_path.stat().st_size if out_path.is_file() else None
        duration = await _probe_duration(out_path) if out_path.is_file() else 0.0

        yield {
            "type": "done", "stage": "done", "message": "Premium Reel ready.",
            "video_id": reel_id,
            "public_url": f"/api/video/assets/{reel_id}.mp4",
            "duration": duration,
            "size_bytes": size_bytes,
        }
    except Exception as e:
        logger.exception("Premium Reel render failed")
        yield {"type": "error", "stage": "error", "message": str(e)}
    finally:
        try:
            shutil.rmtree(work_root, ignore_errors=True)
        except Exception:
            pass


# ── Storyboard reel — N scenes from a Director storyboard ────────────


@dataclass
class StoryboardReelRequest:
    scenes: list[dict]              # output of brand_reel.generate_storyboard
    voiceover_script: str = ""
    voice_id: Optional[str] = None
    music_path: Optional[Path] = None      # royalty-free music bed (already resolved to local disk)
    quality: str = "draft"
    parallel_workers: int = 2       # how many Chrome workers can run side-by-side
    # When True, synthesise per-scene TTS using each scene's `_speak_text`
    # (set by the verbatim splitter) and stretch each scene to match its
    # audio length. Audio + visual stay in sync; no mid-sentence cuts.
    sync_audio_to_scenes: bool = False
    # Epic 11 P1: `type:"higgsfield"` scenes generate a clip via the
    # higgsfield CLI and splice it into the stitch. These fields tag the
    # cached clip's ad_assets row (library visibility + prompt-hash
    # reuse) and pick the generation aspect. Renders without higgsfield
    # scenes never touch any of this.
    account_id: Optional[str] = None
    campaign_id: Optional[str] = None
    aspect: str = "16:9"            # mezzanine target is 1920x1080 (16:9)


async def generate_storyboard_reel(req: StoryboardReelRequest) -> AsyncIterator[dict]:
    """Render an arbitrary N-scene storyboard. Renders up to N scenes in parallel
    (bounded by parallel_workers — keep low because each Chrome instance eats
    ~256 MB RAM and the M2 Pro only has 16 GB)."""
    if not _hyperframes_available():
        yield {"type": "error", "stage": "deps",
               "message": "Hyperframes not installed — run `npm install` in backend/hyperframes/"}
        return
    if not req.scenes:
        yield {"type": "error", "stage": "input", "message": "no scenes in storyboard"}
        return

    reel_id = str(uuid.uuid4())
    work_root = Path(tempfile.mkdtemp(prefix=f"storyreel-{reel_id[:8]}-"))
    try:
        # ── 0. (sync mode only) Per-scene TTS so we can stretch each scene to
        #     match its audio length. Eliminates mid-sentence cuts because each
        #     scene now lasts as long as its line takes to speak.
        per_scene_audio: list[Optional[Path]] = [None] * len(req.scenes)
        per_scene_duration: list[Optional[float]] = [None] * len(req.scenes)
        sync_active = bool(req.sync_audio_to_scenes and settings.ELEVENLABS_API_KEY)
        if req.sync_audio_to_scenes and not settings.ELEVENLABS_API_KEY:
            yield {"type": "status", "stage": "voice-skipped",
                   "message": "Audio-sync requested but ELEVENLABS_API_KEY not set — falling back to fixed scene durations."}
        if sync_active:
            voice_id = req.voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID
            audio_dir = work_root / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            yield {"type": "status", "stage": "voice-sync",
                   "message": f"Generating per-scene voiceover ({len(req.scenes)} clips) for tight sync…"}

            # Cap concurrent TTS to 2 — ElevenLabs free/starter tiers reject
            # parallel requests beyond this and silently 429 some clips, leaving
            # the final video either silent or (with -shortest) truncated.
            tts_sem = asyncio.Semaphore(2)

            async def _tts_one(idx: int, scene: dict) -> Optional[Path]:
                # Explicit `_speak_text` always wins — lets the caller separate
                # visible caption ("€500K") from spoken text ("five hundred
                # thousand euros") so TTS doesn't pronounce abbreviations as
                # letters. Empty string `_speak_text=""` means silent scene.
                if "_speak_text" in scene:
                    speak = (scene.get("_speak_text") or "").strip()
                else:
                    stype = (scene.get("type") or "").lower()
                    if stype == "stat":
                        speak = f"{scene.get('stat_value','')} {scene.get('stat_label','')}".strip()
                    elif stype == "logo":
                        parts = [scene.get("brand_name", ""), scene.get("tagline", "")]
                        speak = " — ".join(p for p in parts if p).strip()
                    else:
                        speak = (
                            scene.get("caption")
                            or scene.get("headline")
                            or scene.get("cta")
                            or ""
                        ).strip()
                if not speak:
                    return None
                async with tts_sem:
                    # Retry once on transient errors (rate limits, network blips)
                    for attempt in range(2):
                        try:
                            audio_bytes = await elevenlabs_tts(speak, voice_id)
                            p = audio_dir / f"s{idx:02d}.mp3"
                            p.write_bytes(audio_bytes)
                            return p
                        except Exception as e:
                            if attempt == 0:
                                logger.warning("per-scene TTS attempt 1 failed for scene %d: %s — retrying", idx, e)
                                await asyncio.sleep(1.5)
                                continue
                            logger.warning("per-scene TTS failed for scene %d: %s", idx, e)
                            return None
                    return None

            results = await asyncio.gather(*[_tts_one(i, s) for i, s in enumerate(req.scenes)])
            for i, p in enumerate(results):
                per_scene_audio[i] = p
                if p is not None:
                    per_scene_duration[i] = await _probe_duration(p)
            n_ok = sum(1 for p in per_scene_audio if p is not None)
            if n_ok < len(req.scenes):
                yield {"type": "status", "stage": "voice-partial",
                       "message": f"⚠ Got TTS for {n_ok}/{len(req.scenes)} scenes — missing scenes will play silent."}

        # ── 1. Prepare every scene (cheap — file IO + string substitution) ──
        # Entry shape: (idx, type, payload, duration). payload is the
        # prepared template dir for hyperframes types, or the raw scene
        # dict for `higgsfield` scenes (clip generation happens in the
        # render phase so it can run inside the same batched gather).
        prepared: list[tuple[int, str, Any, float]] = []
        n_higgsfield = 0
        for i, scene in enumerate(req.scenes):
            stype = (scene.get("type") or "").lower()
            if stype == "higgsfield":
                # Epic 11 P1 — generative clip spliced into the stitch.
                # Cap per render: credit-burn guard (defense in depth
                # with pmax_video._clean_scenes; this path also covers
                # hand-edited storyboards).
                from app.services.higgsfield_scene import MAX_HIGGSFIELD_SCENES
                if not (scene.get("prompt") or "").strip():
                    logger.warning("storyboard scene %d higgsfield without prompt — skipping", i)
                    continue
                if n_higgsfield >= MAX_HIGGSFIELD_SCENES:
                    yield {"type": "status", "stage": "higgsfield-capped",
                           "message": f"Scene {i+1} skipped — max {MAX_HIGGSFIELD_SCENES} AI clips per render (credit guard)."}
                    continue
                n_higgsfield += 1
                hf_dur = 5.0
                try:
                    hf_dur = max(1.5, float(scene.get("duration") or 5.0))
                except Exception:
                    pass
                prepared.append((i, "higgsfield", dict(scene), hf_dur))
                continue
            if stype not in TYPE_TO_TEMPLATE:
                logger.warning("storyboard scene %d unknown type %r — skipping", i, stype)
                continue
            template_dir = _template_for_scene(scene)
            _, default_dur, _attr_keys = TYPE_TO_TEMPLATE[stype]
            effective_dur = default_dur
            # Explicit per-scene `duration` field overrides everything (used for
            # things like a "hold for 3s" QR card). Falls back to audio-sync if
            # not set, then to the type's default.
            if scene.get("duration"):
                try: effective_dur = max(1.5, float(scene["duration"]))
                except Exception: pass
            elif sync_active and per_scene_duration[i]:
                effective_dur = max(3.0, per_scene_duration[i] + 0.6)

            scene_dir = work_root / f"s{i:02d}_{stype}"
            data_attrs = _scene_to_data_attrs(scene)
            if abs(effective_dur - default_dur) > 0.01:
                data_attrs["duration"] = f"{effective_dur:.2f}"
            _prepare_scene(template_dir, scene_dir, data_attrs)
            prepared.append((i, stype, scene_dir, effective_dur))

        if not prepared:
            yield {"type": "error", "stage": "prepare", "message": "no valid scenes after preparation"}
            return

        # ── 2. Render in batches of `parallel_workers` ──
        async def _render_one(idx: int, stype: str, payload: Any) -> Path:
            """Render a single prepared entry to a local MP4. Hyperframes
            types go through headless Chrome; higgsfield scenes generate
            (or cache-hit) a clip and mezzanine-normalize it so the
            xfade chain accepts it next to the 1920x1080/30fps HTML
            scenes."""
            if stype == "higgsfield":
                from app.services.higgsfield_scene import (
                    normalize_clip,
                    resolve_higgsfield_clip,
                )
                raw_clip, was_cached = await resolve_higgsfield_clip(
                    payload,
                    aspect=req.aspect,
                    account_id=req.account_id,
                    campaign_id=req.campaign_id,
                )
                if was_cached:
                    logger.info("scene %d reusing cached higgsfield clip", idx)
                # Spoken line longer than the fixed-length clip → freeze
                # the last frame so the VO fits (generative clips can't
                # stretch to audio like HTML scenes do).
                min_dur: Optional[float] = None
                if sync_active and per_scene_duration[idx]:
                    min_dur = per_scene_duration[idx] + 0.3
                dest = work_root / f"s{idx:02d}_higgsfield_norm.mp4"
                return await normalize_clip(raw_clip, dest, min_duration=min_dur)
            return await _render_with_hyperframes(payload, quality=req.quality)

        scene_mp4s: list[Path] = [None] * len(prepared)  # type: ignore
        total = len(prepared)
        for batch_start in range(0, total, req.parallel_workers):
            batch = prepared[batch_start:batch_start + req.parallel_workers]
            n_hf_batch = sum(1 for (_, t, _, _) in batch if t == "higgsfield")
            yield {
                "type": "status", "stage": f"render-batch-{batch_start//req.parallel_workers + 1}",
                "message": (
                    f"Rendering scenes {batch_start+1}-{batch_start+len(batch)}/{total}"
                    + (" (includes an AI clip — can take several minutes)…"
                       if n_hf_batch else " (Hyperframes · GSAP · headless Chrome)…")
                ),
            }
            results = await asyncio.gather(
                *[_render_one(idx, t, payload) for (idx, t, payload, _) in batch],
                return_exceptions=True,
            )
            for (rel_idx, (idx, stype, _d, _dur)), res in zip(enumerate(batch), results):
                if isinstance(res, Exception):
                    # Don't kill the whole reel for one bad scene — surface a warning
                    # event and stitch what we have. A 12/13 scene reel is still a win.
                    logger.warning("scene %d (%s) render failed: %s", idx, stype, res)
                    yield {
                        "type": "status", "stage": "scene-skipped",
                        "message": f"Scene {idx+1} ({stype}) failed to render — continuing with remaining scenes.",
                    }
                    continue
                scene_mp4s[batch_start + rel_idx] = res

        # Filter the ones that actually rendered
        ordered_mp4s = [m for m in scene_mp4s if m is not None]
        if not ordered_mp4s:
            raise RuntimeError("all scenes failed to render")

        # ── 3. Voiceover ──
        audio_path: Optional[Path] = None
        if sync_active and any(p for p in per_scene_audio):
            # Concat per-scene MP3s into one continuous track. Each scene is
            # already stretched to its line's audio length (step 1), so
            # concatenation aligns naturally — no padding needed.
            audio_path = work_root / "vo.mp3"
            try:
                await _concat_audios([p for p in per_scene_audio if p is not None], audio_path)
                yield {"type": "status", "stage": "voice-sync-ready",
                       "message": f"Per-scene audio aligned — {len([p for p in per_scene_audio if p])} clips concatenated."}
            except Exception as e:
                logger.warning("audio concat failed: %s", e)
                yield {"type": "status", "stage": "voice-failed",
                       "message": f"Audio concat failed — continuing silent. Reason: {str(e)[:200]}"}
                audio_path = None
        elif req.voiceover_script:
            if not settings.ELEVENLABS_API_KEY:
                yield {"type": "status", "stage": "voice-skipped",
                       "message": "VO requested but ELEVENLABS_API_KEY not set — render will be silent."}
            else:
                yield {"type": "status", "stage": "voice", "message": "Generating voiceover (ElevenLabs)..."}
                try:
                    voice_id = req.voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID
                    audio_bytes = await elevenlabs_tts(req.voiceover_script, voice_id)
                    audio_path = work_root / "vo.mp3"
                    audio_path.write_bytes(audio_bytes)
                except Exception as e:
                    logger.warning("Storyboard Reel VO failed: %s", e)
                    yield {"type": "status", "stage": "voice-failed",
                           "message": f"VO generation failed — continuing silent. Reason: {str(e)[:200]}"}

        # ── 4. Stitch ──
        yield {"type": "status", "stage": "stitch",
               "message": f"Stitching {len(ordered_mp4s)} scenes with crossfades…"}
        out_path = ASSETS_DIR / f"{reel_id}.mp4"
        await _stitch_mp4s(ordered_mp4s, audio_path, out_path, music=req.music_path)

        size_bytes = out_path.stat().st_size if out_path.is_file() else None
        # Probe the ACTUAL output file rather than estimating — if any scenes
        # were skipped during render, the estimate would over-count badly.
        # The asset library shows this duration to the user, so it has to match
        # what the player will actually report.
        duration = await _probe_duration(out_path) if out_path.is_file() else 0.0

        yield {
            "type": "done", "stage": "done", "message": "Brand Story Reel ready.",
            "video_id": reel_id,
            "public_url": f"/api/video/assets/{reel_id}.mp4",
            "duration": round(duration, 1),
            "size_bytes": size_bytes,
            "scene_count": len(ordered_mp4s),
        }
    except Exception as e:
        logger.exception("Storyboard Reel render failed")
        yield {"type": "error", "stage": "error", "message": str(e)}
    finally:
        try:
            shutil.rmtree(work_root, ignore_errors=True)
        except Exception:
            pass


def _scene_to_data_attrs(scene: dict) -> dict[str, str]:
    """Convert a scene dict from the storyboard into the data-* attribute map
    the template expects.

    Notably translates `image_filename` → `image-path` (the template attribute)
    by resolving the filename against the local /api/assets/file/ URL — but
    since Hyperframes renders headlessly inside the project dir, we copy the
    image into the project's assets/ folder and reference it as `assets/<name>`.
    """
    stype = (scene.get("type") or "").lower()
    if stype == "hero":
        return {"headline": scene.get("headline") or ""}
    if stype == "stat":
        return {
            "stat-value": scene.get("stat_value") or "",
            "stat-label": scene.get("stat_label") or "",
        }
    if stype == "cta":
        # Optional logo + brand mark + tagline — template hides each gracefully if empty
        logo_fn = scene.get("logo_filename") or ""
        return {
            "cta": scene.get("cta") or "Book a free consultation",
            "logo-path": f"assets/{logo_fn}" if logo_fn else "",
            "brand-name": scene.get("brand_name") or "",
            "tagline": scene.get("tagline") or "",
        }
    if stype == "logo":
        # Pure brand-mark scene — for intro / outro
        logo_fn = scene.get("logo_filename") or ""
        return {
            "logo-path": f"assets/{logo_fn}" if logo_fn else "",
            "brand-name": scene.get("brand_name") or "",
            "tagline": scene.get("tagline") or "",
        }
    if stype == "broll":
        # Image is copied into the scene_dir's assets/ folder by the caller
        # (see _copy_image_for_scene below). Template reads it via assets/<name>.
        fn = scene.get("image_filename") or ""
        return {
            "image-path": f"assets/{fn}",
            "caption": scene.get("caption") or "",
            "scene-label": scene.get("scene_label") or "",
            # Per-scene visual treatment — Director picks from a fixed palette
            "motion": scene.get("motion") or "kenburns-zoom-in",
            "text-treatment": scene.get("text_treatment") or "blur-stagger",
        }
    return {}


# ── Per-scene preparation + render ─────────────────────────────────


def _prepare_scene(template_dir: Path, dest_dir: Path, data_attrs: dict[str, str]) -> None:
    """Copy a template project to a fresh dir + inject data-* attribute values
    into its index.html. We use simple regex substitution on the existing
    `data-<key>="..."` attributes — keeps the templates editable as plain HTML.

    For broll scenes (image-path attr present), also copies the referenced
    library image into the scene's assets/ folder so Hyperframes can resolve
    the relative path during headless render.
    """
    # Copy the whole template tree (small — usually <1 MB)
    shutil.copytree(template_dir, dest_dir, dirs_exist_ok=True)

    index = dest_dir / "index.html"
    html = index.read_text(encoding="utf-8")

    for key, value in data_attrs.items():
        # Escape the value for HTML attribute context — strip quotes that would
        # break out of the attribute. Templates handle their own .toUpperCase()
        # if needed, so we keep the casing the user typed.
        safe = (value or "").replace('"', "&quot;").replace("\n", " ").strip()
        # Replace `data-key="..."` (any quoted value) with `data-key="safe"`
        pattern = rf'(data-{re.escape(key)}=")[^"]*(")'
        new_html, n = re.subn(pattern, rf'\g<1>{safe}\g<2>', html, count=1)
        if n == 0:
            logger.warning("template %s has no data-%s attribute — skipping injection",
                           template_dir.name, key)
        html = new_html

    index.write_text(html, encoding="utf-8")

    # Copy any referenced library image (broll background, logo) into assets/
    # so the headless Chrome render can resolve assets/<filename> relative to
    # the project dir.
    for attr in ("image-path", "logo-path"):
        path_attr = data_attrs.get(attr)
        if path_attr and path_attr.startswith("assets/"):
            fn = path_attr.split("/", 1)[1]
            src = ASSETS_DIR / fn
            if src.is_file():
                (dest_dir / "assets").mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_dir / "assets" / fn)
            else:
                logger.warning("scene %s asset not found in ad_assets: %s", attr, src)


async def _render_with_hyperframes(project_dir: Path, *, quality: str = "draft") -> Path:
    """Run `npx hyperframes render` against the project. Returns the rendered MP4 path.

    Pinned to `--workers 1` because we already parallelise scenes at the asyncio
    layer. Letting hyperframes auto-spawn extra Chrome instances on top stacks
    4-8 Chromes simultaneously and intermittently crashes Puppeteer with
    "Failed to launch the browser process" on a 16 GB machine.

    IMPORTANT — *poll for output* rather than wait for process exit. Hyperframes
    has a bug where its producer-server stays alive after the MP4 is written,
    so `proc.communicate()` never returns. We watch the renders/ directory, and
    as soon as a fresh MP4 appears (newer than the start time), we kill the
    process and return the file. Hard ceiling of 180 s per scene.
    """
    renders_dir = project_dir / "renders"
    # Wipe any stale MP4s the template directory might have shipped with —
    # otherwise the "newest mp4" heuristic could pick up a leftover from a
    # previous test render and skip the actual capture.
    if renders_dir.exists():
        for old in renders_dir.glob("*.mp4"):
            try: old.unlink()
            except Exception: pass

    cmd = [
        "npx", "-y", "hyperframes", "render",
        "--quality", quality,
        "--workers", "1",
        "--quiet",
    ]

    last_err = ""
    for attempt in range(2):
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        deadline = asyncio.get_event_loop().time() + 180.0
        rendered: Optional[Path] = None
        # Poll for output every 0.5s — kills hung producer-server problem
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.5)
            # Process may have actually exited cleanly
            if proc.returncode is not None:
                break
            # Check for a freshly written MP4
            if renders_dir.exists():
                mp4s = list(renders_dir.glob("*.mp4"))
                if mp4s:
                    # Confirm file is no longer being written: stable size for 1s
                    candidate = max(mp4s, key=lambda p: p.stat().st_mtime)
                    s1 = candidate.stat().st_size
                    await asyncio.sleep(1.0)
                    s2 = candidate.stat().st_size
                    if s1 == s2 and s1 > 0:
                        rendered = candidate
                        break

        # If we got an output MP4 (whether or not the process exited), use it
        if rendered is not None:
            # Best-effort kill of any hung producer-server child processes
            if proc.returncode is None:
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=3.0)
                except Exception:
                    pass
            return rendered

        # No MP4 produced in time — kill and fall through to retry / fail
        if proc.returncode is None:
            try:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except Exception:
                pass

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3.0)
        except (asyncio.TimeoutError, ValueError):
            stdout = stderr = b""
        out = (stdout or b"").decode("utf-8", errors="replace")[-1500:]
        err = (stderr or b"").decode("utf-8", errors="replace")[-1500:]
        last_err = err or out or "no MP4 written within 180s"
        # Only retry on transient launch failures or pure timeouts
        if attempt == 0:
            await asyncio.sleep(2.0)
            continue

    raise RuntimeError(f"hyperframes render failed (rc={proc.returncode}):\n{last_err}")


# ── MP4 stitcher (xfade + final fade-to-black + audio mux) ─────────


async def _stitch_mp4s(
    scene_mp4s: list[Path],
    audio: Optional[Path],
    out: Path,
    *,
    music: Optional[Path] = None,
) -> None:
    """Concatenate MP4s with 0.6s crossfades + 0.5s fade-to-black at the end.
    Assumes each scene MP4 is the same dimensions and frame rate.

    Audio mixing rules:
      - VO only:            VO at 0 dB.
      - VO + music:         VO at 0 dB, music sidechained-down to -18 dB and
                            clipped to video duration with 1s/1.5s fade.
      - Music only:         Music at -6 dB with 1s/1.5s fade.
      - No audio:           Silent video.
    """
    if not scene_mp4s:
        raise RuntimeError("no scenes to stitch")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not on PATH")

    inputs: list[str] = []
    for mp4 in scene_mp4s:
        inputs += ["-i", str(mp4)]
    audio_idx: Optional[int] = None
    music_idx: Optional[int] = None
    if audio is not None:
        inputs += ["-i", str(audio)]
        audio_idx = len(scene_mp4s)
    if music is not None:
        inputs += ["-i", str(music)]
        music_idx = len(scene_mp4s) + (1 if audio is not None else 0)

    # Read scene durations from each input via ffprobe so the xfade offsets line up
    durations = [await _probe_duration(mp4) for mp4 in scene_mp4s]
    fade_d = 0.6

    # Build the xfade chain: [0:v][1:v]xfade...[xf1];[xf1][2:v]xfade...[vout]
    # Rotate through xfade transitions — curated cinematic palette, no
    # PowerPoint moves. Picked by join index for determinism.
    transition_palette = [
        "fade",           # crossfade — neutral
        "smoothleft",     # soft slide L — narrative push
        "fadeblack",      # cut to black — beat
        "circleopen",     # iris open from center — reveal
        "smoothright",    # soft slide R
        "wiperight",      # hard wipe — energy
        "dissolve",       # textured grain dissolve
        "radial",         # radial sweep — drama
    ]
    parts: list[str] = []
    if len(scene_mp4s) == 1:
        chain = "[0:v]copy"
        cumulative = durations[0]
    else:
        chain = "[0:v]"
        cumulative = durations[0]
        for i in range(1, len(scene_mp4s)):
            offset = cumulative - fade_d
            transition = transition_palette[(i - 1) % len(transition_palette)]
            chain += (
                f"[{i}:v]xfade=transition={transition}:duration={fade_d:.2f}:offset={offset:.3f}"
            )
            if i < len(scene_mp4s) - 1:
                chain += f"[xf{i}];[xf{i}]"
            cumulative += durations[i] - fade_d

    # Final fade-to-black
    fade_out_d = 0.5
    fade_out_start = max(0.0, cumulative - fade_out_d)
    chain += f"[xf_out];[xf_out]fade=t=out:st={fade_out_start:.3f}:d={fade_out_d:.2f}[vout]"
    parts.append(chain)

    # Audio chain — clipped to video, with fades
    total_d = cumulative
    music_fade_in = 1.0
    music_fade_out = 1.5
    music_fade_out_st = max(0.0, total_d - music_fade_out)

    audio_map: Optional[str] = None
    # apad ensures audio is padded with silence to match the full video length —
    # without this, if some per-scene TTS calls fail, the audio is shorter than
    # video and ffmpeg either errors or the container muxes badly. Padding makes
    # the tail play silent rather than truncating the video.
    if audio is not None and music is not None:
        # VO + music: VO at 0 dB padded with silence, music ducked to -18 dB
        parts.append(
            f"[{audio_idx}:a]apad=whole_dur={total_d:.3f}[vopad];"
            f"[{music_idx}:a]atrim=0:{total_d:.3f},asetpts=PTS-STARTPTS,"
            f"volume=-18dB,afade=t=in:st=0:d={music_fade_in:.2f},"
            f"afade=t=out:st={music_fade_out_st:.3f}:d={music_fade_out:.2f}[mbed];"
            f"[vopad][mbed]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        audio_map = "[aout]"
    elif audio is not None:
        # VO only — pad to video length with silence
        parts.append(
            f"[{audio_idx}:a]apad=whole_dur={total_d:.3f}[aout]"
        )
        audio_map = "[aout]"
    elif music is not None:
        parts.append(
            f"[{music_idx}:a]atrim=0:{total_d:.3f},asetpts=PTS-STARTPTS,"
            f"volume=-6dB,afade=t=in:st=0:d={music_fade_in:.2f},"
            f"afade=t=out:st={music_fade_out_st:.3f}:d={music_fade_out:.2f}[aout]"
        )
        audio_map = "[aout]"

    filter_complex = ";".join(parts)

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", "[vout]"]
    if audio_map is not None:
        # apad in filter_complex (above) padded audio to video length, so the
        # muxer ends naturally on the video stream without -shortest truncation.
        cmd += ["-map", audio_map, "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        snippet = stderr.decode("utf-8", errors="replace")[-1800:]
        raise RuntimeError(f"ffmpeg stitch failed (rc={proc.returncode}):\n{snippet}")


async def _concat_audios(audios: list[Path], out: Path) -> None:
    """Concatenate per-scene MP3s into a single continuous audio track via
    ffmpeg's concat filter (re-encodes — safer than the demuxer for MP3s with
    different headers / sample rates).
    """
    if not audios:
        raise RuntimeError("no audio files to concat")
    if len(audios) == 1:
        # Single file → just copy
        shutil.copy2(audios[0], out)
        return

    inputs: list[str] = []
    for a in audios:
        inputs += ["-i", str(a)]
    n = len(audios)
    # [0:a][1:a]...[N-1:a]concat=n=N:v=0:a=1[a]
    streams = "".join(f"[{i}:a]" for i in range(n))
    filter_complex = f"{streams}concat=n={n}:v=0:a=1[aout]"

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "libmp3lame", "-q:a", "3",
        str(out),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        snippet = stderr.decode("utf-8", errors="replace")[-1500:]
        raise RuntimeError(f"audio concat failed (rc={proc.returncode}):\n{snippet}")


async def _probe_duration(mp4: Path) -> float:
    """Read the duration of an MP4 via ffprobe. Falls back to 4.0 if probe fails."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(mp4),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode("utf-8").strip())
    except Exception:
        return 4.0


# ── Dep check ──────────────────────────────────────────────────────


def _hyperframes_available() -> bool:
    """Cheap startup check: kit folder exists + node_modules in place."""
    return (HYPERFRAMES_ROOT / "node_modules").is_dir() and TEMPLATE_HERO.is_dir()
