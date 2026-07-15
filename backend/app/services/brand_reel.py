"""Brand Reel — local cinematic motion-graphics ads + scene auto-generator.

No HeyGen, no avatar. Pillow renders four scenes as PNGs (hero, B-roll +
overlay, value-prop, CTA card) using the Mercan brand palette. ffmpeg stitches
them with Ken-Burns zoompan + crossfade transitions and overlays an optional
ElevenLabs voiceover. Fully local, fully free per draft.

Scene structure (15s default, 30s = 2× durations):
  Scene 1 · Hero        — bold headline on navy with gold accent (3s)
  Scene 2 · B-roll      — hotel/program photo with text overlay (4s)
  Scene 3 · Value-prop  — single number/stat reveal on solid bg    (4s)
  Scene 4 · CTA card    — call-to-action + brand mark              (4s)
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config import settings
from app.services.video import ASSETS_DIR, elevenlabs_tts

logger = logging.getLogger(__name__)

# ── Brand palette ──────────────────────────────────────────────────
NAVY = (1, 49, 96)            # #013160 — Mercan primary
GOLD = (201, 168, 76)         # #c9a84c — Mercan accent
GOLD_RGB = GOLD               # alias (some Pillow paths want plain RGB tuples)
DARK = (10, 22, 40)           # #0a1628 — deep background
WHITE = (255, 255, 255)
WHITE_SOFT = (240, 240, 240)
GOLD_SOFT = (201, 168, 76, 60)


# ── Layout helpers ────────────────────────────────────────────────


def _vertical_gradient(w: int, h: int, top: tuple, bottom: tuple) -> Image.Image:
    """Smooth top→bottom gradient between two RGB colors. ~10× faster than
    drawing per-pixel — uses Pillow's resize from a 1×N seed."""
    seed = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        seed.putpixel((0, y), (r, g, b))
    return seed.resize((w, h), Image.NEAREST)


# ── Transparent layer factories ───────────────────────────────────


def _text_layer_png(text: str, font: ImageFont.FreeTypeFont, fill: tuple,
                    out: Path, *, max_width: int = 0,
                    line_spacing: float = 1.15, shadow: bool = False,
                    align: str = "left") -> tuple[Path, int, int]:
    """Render text into a tightly-cropped transparent PNG. Returns (path, w, h).

    `align` controls per-line alignment within the PNG bounding box. When
    `max_width > 0` and the text would exceed it, the text wraps.
    """
    lines = _wrap_text(text, font, max_width) if max_width else [text]
    line_h = int(font.size * line_spacing) if hasattr(font, "size") else 28
    line_widths = [font.getbbox(l)[2] - font.getbbox(l)[0] for l in lines]
    w = max(line_widths) if line_widths else 1
    h = line_h * len(lines)
    pad = 12  # extra room for shadow
    img = Image.new("RGBA", (w + pad * 2, h + pad), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        bbox = font.getbbox(line)
        line_w = bbox[2] - bbox[0]
        if align == "center":
            x = pad + (w - line_w) // 2
        elif align == "right":
            x = pad + (w - line_w)
        else:  # left
            x = pad
        y = i * line_h
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 130))
        draw.text((x, y), line, font=font, fill=fill)
    img.save(out, "PNG", optimize=True)
    return out, img.size[0], img.size[1]


def _rect_layer_png(width: int, height: int, fill: tuple, out: Path) -> Path:
    """Render a solid-color rectangle into a transparent PNG (handy for accent
    bars, gold underlines, color overlays). `fill` may include alpha."""
    if len(fill) == 3:
        fill = (*fill, 255)
    img = Image.new("RGBA", (width, height), fill)
    img.save(out, "PNG", optimize=True)
    return out


def _border_box_png(width: int, height: int, color: tuple, thickness: int,
                    inner_color: tuple | None, inner_gap: int, out: Path) -> Path:
    """Draw an outlined rectangle (gold border) into a transparent PNG. Used
    for the CTA frame in Scene 4."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i in range(thickness):
        draw.rectangle([(i, i), (width - 1 - i, height - 1 - i)], outline=color)
    if inner_color is not None:
        gap = thickness + inner_gap
        draw.rectangle([(gap, gap), (width - 1 - gap, height - 1 - gap)], outline=inner_color)
    img.save(out, "PNG", optimize=True)
    return out


def _gradient_overlay_png(width: int, height: int, top_alpha: int, bottom_alpha: int,
                          color: tuple, out: Path) -> Path:
    """Vertical alpha gradient (used to darken the bottom of B-roll for text legibility)."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    px = img.load()
    for y in range(height):
        t = y / max(1, height - 1)
        a = int(top_alpha + (bottom_alpha - top_alpha) * t)
        # Simple band fill — Pillow's putpixel per row is fine for ≤1080
        for x in range(width):
            px[x, y] = (color[0], color[1], color[2], a)
    img.save(out, "PNG", optimize=True)
    return out


def _autosize_text(text: str, max_w: int, *, max_size: int, min_size: int, max_lines: int) -> tuple[int, list[str]]:
    """Pick the largest font size where `text` wraps to ≤ max_lines within max_w.

    Returns (font_size, list_of_lines). Falls back to min_size if nothing fits.
    """
    for size in range(max_size, min_size - 1, -4):
        font = _font(size, bold=True)
        lines = _wrap_text(text, font, max_w)
        if len(lines) <= max_lines:
            return size, lines
    # Fallback — force-fit at min_size, accept overflow
    font = _font(min_size, bold=True)
    return min_size, _wrap_text(text, font, max_w)


@dataclass
class BrandReelRequest:
    headline: str                            # Scene 1 hero text
    subhead: str = ""                        # Scene 2 overlay
    stat_value: str = ""                     # Scene 3 big number ("EUR 250K")
    stat_label: str = ""                     # Scene 3 small label
    cta: str = "Book a free consultation"    # Scene 4
    voiceover_script: str = ""               # Optional ElevenLabs VO
    b_roll_url: Optional[str] = None         # Scene 2 image (URL or local path)
    voice_id: Optional[str] = None
    width: int = 1920
    height: int = 1080
    duration_s: int = 15                     # 15 or 30
    program_color: tuple[int, int, int] = NAVY  # palette can shift per program


@dataclass
class _Scene:
    duration: float
    png_path: Path
    motion: str = "zoompan"  # zoompan = Ken Burns; static = no motion
    layers: list["Layer"] = field(default_factory=list)


@dataclass
class Layer:
    """One animated overlay element (a transparent PNG positioned over the scene
    background and animated with a slide/fade entrance).

    Coordinates are absolute video pixels — the layer PNG is rendered at the
    exact size it should appear; we don't scale at composite time.
    """
    png_path: Path
    x: int                         # base X position (top-left of the PNG)
    y: int                         # base Y position
    appear_at: float = 0.3         # seconds into the scene when entrance starts
    anim_dur: float = 0.55         # entrance duration
    animation: str = "slide_up"    # slide_up | slide_down | slide_left | slide_right | fade
    slide_distance: int = 28       # how far the slide travels (px)


# ── Public API ─────────────────────────────────────────────────────


async def generate_brand_reel(req: BrandReelRequest) -> AsyncIterator[dict]:
    """Render a Brand Reel and yield SSE-style progress events.

    Yields: {"type": "status"|"done"|"error", "stage": str, "message": str, ...}
    """
    if shutil.which("ffmpeg") is None:
        yield {"type": "error", "stage": "ffmpeg", "message": "ffmpeg not on PATH — required for Brand Reel renders"}
        return

    reel_id = str(uuid.uuid4())
    tmpdir = Path(tempfile.mkdtemp(prefix=f"brandreel-{reel_id[:8]}-"))
    try:
        # Compute per-scene durations (15s = 3+4+4+4, 30s = 5+8+8+9)
        if req.duration_s >= 30:
            durs = [5.0, 8.0, 8.0, 9.0]
        else:
            durs = [3.0, 4.0, 4.0, 4.0]

        yield {"type": "status", "stage": "scene1", "message": "Rendering hero scene..."}
        s1, l1 = await _render_hero(req, tmpdir / "s1.png", tmpdir)

        yield {"type": "status", "stage": "scene2", "message": "Rendering B-roll scene..."}
        s2, l2 = await _render_broll(req, tmpdir / "s2.png", tmpdir)

        yield {"type": "status", "stage": "scene3", "message": "Rendering value-prop scene..."}
        s3, l3 = await _render_stat(req, tmpdir / "s3.png", tmpdir)

        yield {"type": "status", "stage": "scene4", "message": "Rendering CTA scene..."}
        s4, l4 = await _render_cta(req, tmpdir / "s4.png", tmpdir)

        scenes = [
            _Scene(durs[0], s1, motion="zoompan", layers=l1),
            _Scene(durs[1], s2, motion="zoompan", layers=l2),
            _Scene(durs[2], s3, motion="static", layers=l3),
            _Scene(durs[3], s4, motion="static", layers=l4),
        ]

        # Optional voiceover
        audio_path: Optional[Path] = None
        if req.voiceover_script and settings.ELEVENLABS_API_KEY:
            yield {"type": "status", "stage": "voice", "message": "Generating voiceover..."}
            try:
                voice_id = req.voice_id or settings.ELEVENLABS_DEFAULT_VOICE_ID
                audio_bytes = await elevenlabs_tts(req.voiceover_script, voice_id)
                audio_path = tmpdir / "vo.mp3"
                audio_path.write_bytes(audio_bytes)
            except Exception as e:
                logger.warning("Brand Reel VO failed: %s — continuing without audio", e)

        yield {"type": "status", "stage": "stitch", "message": "Stitching with ffmpeg..."}
        out_path = ASSETS_DIR / f"{reel_id}.mp4"
        await _stitch(scenes, audio_path, out_path, req.width, req.height)

        size_bytes = out_path.stat().st_size if out_path.is_file() else None

        yield {
            "type": "done",
            "stage": "done",
            "message": "Brand Reel ready.",
            "video_id": reel_id,
            "public_url": f"/api/video/assets/{reel_id}.mp4",
            "duration": sum(s.duration for s in scenes),
            "size_bytes": size_bytes,
        }
    except Exception as e:
        logger.exception("Brand Reel render failed")
        yield {"type": "error", "stage": "error", "message": str(e)}
    finally:
        # Clean up scratch frames but keep the final mp4 (already in ASSETS_DIR)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ── Scene renderers ────────────────────────────────────────────────


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Pick a system font — falls back to Pillow's default if none found."""
    candidates = (
        # macOS
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.FreeTypeFont,
                   fill: tuple, max_width: int, line_spacing: float = 1.15) -> int:
    """Word-wrap centered text. Returns the y after the last line."""
    lines = _wrap_text(text, font, max_width)
    line_h = font.size if hasattr(font, "size") else 24
    spacing = int(line_h * line_spacing)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (max_width - w) // 2 + (draw.im.size[0] - max_width) // 2
        draw.text((x, y + i * spacing), line, font=font, fill=fill)
    return y + len(lines) * spacing


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for w in words:
        trial = " ".join(current + [w])
        bbox = font.getbbox(trial) if hasattr(font, "getbbox") else (0, 0, len(trial) * 10, 24)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(w)
        else:
            lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines


async def _render_hero(req: BrandReelRequest, out: Path, tmpdir: Path) -> tuple[Path, list[Layer]]:
    """Cinematic hero — base PNG (gradient + ambient glow only), text elements
    return as separate animated overlay layers.

    Layer timeline:
      t=0.20  brand mark slides down + fades in
      t=0.50  headline slides in from the left + fades in
      t=1.20  gold underline fades in
      t=1.55  tagline slides up + fades in
    """
    # Base: vertical gradient + warm gold glow upper-right (no text)
    img = _vertical_gradient(req.width, req.height, DARK, NAVY)
    glow = Image.new("RGBA", (req.width, req.height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gx, gy = int(req.width * 0.78), int(req.height * 0.25)
    for r in range(420, 0, -20):
        alpha = max(0, int(20 * (1 - r / 420)))
        gd.ellipse([(gx - r, gy - r), (gx + r, gy + r)], fill=(201, 168, 76, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    img.save(out, "PNG", optimize=True)

    layers: list[Layer] = []

    # 1. Brand mark (text + gold underline as ONE pre-composed layer)
    brand_font = _font(28, bold=True)
    brand_png = tmpdir / "hero_brand.png"
    bw, bh = brand_font.getbbox("MERCAN GROUP")[2:4]
    bimg = Image.new("RGBA", (bw + 24, bh + 30), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(bimg)
    bdraw.text((12, 0), "MERCAN GROUP", font=brand_font, fill=GOLD)
    bdraw.rectangle([(12, bh + 14), (12 + 100, bh + 18)], fill=GOLD)
    bimg.save(brand_png, "PNG", optimize=True)
    layers.append(Layer(brand_png, x=68, y=60, appear_at=0.2, anim_dur=0.45,
                        animation="slide_down", slide_distance=20))

    # 2. Headline — auto-sized, wraps ≤2 lines
    safe_x = max(120, int(req.width * 0.08))
    max_w = req.width - 2 * safe_x
    headline_text = (req.headline or "Your Next Move Starts Here").upper()
    h_size, h_lines = _autosize_text(headline_text, max_w, max_size=120, min_size=64, max_lines=2)
    headline_font = _font(h_size, bold=True)
    headline_png = tmpdir / "hero_headline.png"
    hp, hw, hh = _text_layer_png("\n".join(h_lines), headline_font, WHITE,
                                  headline_png, max_width=max_w,
                                  shadow=True, align="center")
    block_y = (req.height - hh) // 2 - 50
    layers.append(Layer(hp, x=(req.width - hw) // 2, y=block_y,
                        appear_at=0.5, anim_dur=0.7,
                        animation="slide_left", slide_distance=80))

    # 3. Gold underline
    underline_w = min(220, max_w // 4)
    underline_y = block_y + hh + 18
    underline_png = tmpdir / "hero_underline.png"
    _rect_layer_png(underline_w, 4, GOLD, underline_png)
    layers.append(Layer(underline_png, x=(req.width - underline_w) // 2, y=underline_y,
                        appear_at=1.2, anim_dur=0.4, animation="fade"))

    # 4. Tagline
    tag_font = _font(34, bold=False)
    tag_png = tmpdir / "hero_tagline.png"
    tp, tw, th = _text_layer_png("INVESTMENT IMMIGRATION · EU RESIDENCY", tag_font,
                                  (220, 220, 220), tag_png, align="center")
    layers.append(Layer(tp, x=(req.width - tw) // 2, y=underline_y + 22,
                        appear_at=1.55, anim_dur=0.5,
                        animation="slide_up", slide_distance=18))

    return out, layers


async def _render_broll(req: BrandReelRequest, out: Path, tmpdir: Path) -> tuple[Path, list[Layer]]:
    """B-roll scene — base is the photo (or brand gradient), text + accents
    enter as layered overlays."""
    bg: Optional[Image.Image] = None
    if req.b_roll_url:
        url = req.b_roll_url.strip()
        try:
            if url.startswith("/api/assets/file/") or url.startswith("/api/video/assets/"):
                fname = url.rsplit("/", 1)[-1]
                local_path = ASSETS_DIR / fname
                if local_path.is_file():
                    raw = Image.open(local_path).convert("RGB")
                    bg = _cover_resize(raw, req.width, req.height)
                else:
                    logger.warning("Brand Reel b-roll local file not found: %s", local_path)
            else:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        from io import BytesIO
                        raw = Image.open(BytesIO(r.content)).convert("RGB")
                        bg = _cover_resize(raw, req.width, req.height)
        except Exception as e:
            logger.warning("Brand Reel b-roll load failed: %s — using gradient", e)

    if bg is None:
        bg = Image.new("RGB", (req.width, req.height), NAVY)
        ov = Image.new("RGBA", (req.width, req.height))
        ovd = ImageDraw.Draw(ov)
        for i in range(40):
            ovd.rectangle([(i * 50, 0), (i * 50 + 200, req.height)],
                          fill=(201, 168, 76, max(0, 30 - i)))
        ov = ov.filter(ImageFilter.GaussianBlur(60))
        bg = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
    bg.save(out, "PNG", optimize=True)

    layers: list[Layer] = []

    # 1. Dark gradient overlay (bottom 50%) — fades in
    grad_h = int(req.height * 0.55)
    grad_png = tmpdir / "broll_grad.png"
    _gradient_overlay_png(req.width, grad_h, top_alpha=0, bottom_alpha=210,
                          color=(10, 22, 40), out=grad_png)
    layers.append(Layer(grad_png, x=0, y=req.height - grad_h,
                        appear_at=0.2, anim_dur=0.5, animation="fade"))

    # 2. Gold accent strip (vertical) on the left
    strip_x = 80
    strip_y = int(req.height * 0.62)
    strip_h = int(req.height * 0.30)
    strip_png = tmpdir / "broll_strip.png"
    _rect_layer_png(8, strip_h, GOLD, strip_png)
    layers.append(Layer(strip_png, x=strip_x, y=strip_y,
                        appear_at=0.5, anim_dur=0.5,
                        animation="slide_down", slide_distance=20))

    # 3. Subhead — wraps to 3 lines max, slides in from left
    sub_font = _font(64, bold=True)
    margin_left = strip_x + 50
    sub_max_w = req.width - margin_left - 200
    text = (req.subhead or req.headline or "EU Residency Through Strategic Investment").strip()
    sub_png = tmpdir / "broll_sub.png"
    sp, sw, sh = _text_layer_png(text, sub_font, WHITE, sub_png,
                                  max_width=sub_max_w, shadow=True)
    layers.append(Layer(sp, x=margin_left, y=int(req.height * 0.66),
                        appear_at=0.85, anim_dur=0.65,
                        animation="slide_left", slide_distance=70))

    return out, layers


async def _render_stat(req: BrandReelRequest, out: Path, tmpdir: Path) -> tuple[Path, list[Layer]]:
    """Stat scene — solid navy base, big number pops in, underline draws,
    label rises."""
    bg = Image.new("RGB", (req.width, req.height), NAVY)
    # Subtle vertical gradient for depth
    bg = _vertical_gradient(req.width, req.height, NAVY, DARK)
    bg.save(out, "PNG", optimize=True)

    layers: list[Layer] = []

    # 1. Stat number — slides up + fades in
    stat_font = _font(220, bold=True)
    stat = req.stat_value or "EUR 250K"
    stat_png = tmpdir / "stat_num.png"
    sp, sw, sh = _text_layer_png(stat, stat_font, GOLD, stat_png, shadow=True)
    stat_x = (req.width - sw) // 2
    stat_y = req.height // 2 - 180
    layers.append(Layer(sp, x=stat_x, y=stat_y, appear_at=0.25, anim_dur=0.6,
                        animation="slide_up", slide_distance=40))

    # 2. White underline — fades in centered below the stat
    ul_w = 180
    ul_png = tmpdir / "stat_ul.png"
    _rect_layer_png(ul_w, 6, WHITE, ul_png)
    ul_y = stat_y + sh + 16
    layers.append(Layer(ul_png, x=(req.width - ul_w) // 2, y=ul_y,
                        appear_at=0.95, anim_dur=0.4, animation="fade"))

    # 3. Label — rises from below
    label_font = _font(48, bold=False)
    label_text = (req.stat_label or "minimum investment").upper()
    label_png = tmpdir / "stat_label.png"
    lp, lw, lh = _text_layer_png(label_text, label_font, WHITE_SOFT, label_png)
    layers.append(Layer(lp, x=(req.width - lw) // 2, y=ul_y + 28,
                        appear_at=1.25, anim_dur=0.5,
                        animation="slide_up", slide_distance=22))

    return out, layers


async def _render_cta(req: BrandReelRequest, out: Path, tmpdir: Path) -> tuple[Path, list[Layer]]:
    """CTA scene — gold-bordered box fades in first, text scales/slides up,
    brand mark + tagline rise after."""
    bg = _vertical_gradient(req.width, req.height, NAVY, DARK)
    bg.save(out, "PNG", optimize=True)

    layers: list[Layer] = []

    # Compute CTA layout (same as before so framing stays predictable)
    text = (req.cta or "Book a free consultation").strip()
    safe_x = max(120, int(req.width * 0.08))
    max_w = req.width - 2 * safe_x
    cta_size, cta_lines = _autosize_text(text, max_w - 160, max_size=88, min_size=44, max_lines=2)
    cta_font = _font(cta_size, bold=True)
    line_h = int(cta_size * 1.15)
    text_block_h = line_h * len(cta_lines)

    # Box dimensions based on widest line + padding
    line_widths = [cta_font.getbbox(ln)[2] for ln in cta_lines]
    widest = max(line_widths) if line_widths else 0
    pad_x, pad_y = 70, 36
    box_w = widest + 2 * pad_x
    box_h = text_block_h + 2 * pad_y
    brand_zone_h = 110
    box_y = (req.height - (box_h + brand_zone_h)) // 2
    box_x = (req.width - box_w) // 2

    # 1. Gold border box — fades in
    box_png = tmpdir / "cta_box.png"
    _border_box_png(box_w + 8, box_h + 8, color=GOLD, thickness=4,
                    inner_color=(201, 168, 76, 120), inner_gap=8, out=box_png)
    layers.append(Layer(box_png, x=box_x - 4, y=box_y - 4,
                        appear_at=0.3, anim_dur=0.55, animation="fade"))

    # 2. CTA text (the lines, all in one PNG) — slides up
    cta_png = tmpdir / "cta_text.png"
    cp, cw, ch = _text_layer_png("\n".join(cta_lines), cta_font, WHITE,
                                  cta_png, shadow=True, align="center",
                                  line_spacing=1.15)
    cta_text_x = box_x + (box_w - cw) // 2
    cta_text_y = box_y + pad_y
    layers.append(Layer(cp, x=cta_text_x, y=cta_text_y,
                        appear_at=0.85, anim_dur=0.55,
                        animation="slide_up", slide_distance=30))

    # 3. Brand mark below the box
    mark_font = _font(34, bold=False)
    mark_png = tmpdir / "cta_mark.png"
    mp, mw, mh = _text_layer_png("MERCAN GROUP", mark_font, GOLD, mark_png)
    mark_y = box_y + box_h + 36
    layers.append(Layer(mp, x=(req.width - mw) // 2, y=mark_y,
                        appear_at=1.45, anim_dur=0.45,
                        animation="slide_up", slide_distance=18))

    # 4. Tagline
    tag_font = _font(20, bold=False)
    tag_png = tmpdir / "cta_tag.png"
    tp, tw, th = _text_layer_png("INVESTMENT IMMIGRATION · 30+ YEARS", tag_font,
                                  (180, 180, 180), tag_png)
    layers.append(Layer(tp, x=(req.width - tw) // 2, y=mark_y + 44,
                        appear_at=1.75, anim_dur=0.4, animation="fade"))

    return out, layers


def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize image to cover (w, h) without distortion, cropping the overflow."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    dst_ratio = w / h
    if src_ratio > dst_ratio:
        # source is wider — match height, crop sides
        new_h = h
        new_w = int(h * src_ratio)
    else:
        new_w = w
        new_h = int(w / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


# ── ffmpeg stitch with Ken-Burns + crossfades ──────────────────────


def _slide_offsets(animation: str, slide_distance: int) -> tuple[str, str]:
    """Return (x_offset_expr, y_offset_expr) — the *additional* offset on top
    of the layer's base position, animating from `slide_distance` toward 0
    over the entrance duration. Time variable `T` is "seconds since appearance".
    `appear_at` and `anim_dur` are interpolated by the caller into the bigger
    overlay expression.
    """
    if animation == "slide_left":
        return (f"(1-min(1,T/D))*-{slide_distance}", "0")
    if animation == "slide_right":
        return (f"(1-min(1,T/D))*{slide_distance}", "0")
    if animation == "slide_up":
        return ("0", f"(1-min(1,T/D))*{slide_distance}")
    if animation == "slide_down":
        return ("0", f"(1-min(1,T/D))*-{slide_distance}")
    # fade — no offset
    return ("0", "0")


def _build_layer_overlay(layer: Layer, prev_label: str, layer_input_idx: int,
                         layer_label: str, scene_label: str) -> tuple[str, str]:
    """Build the two filter graph fragments needed for one layer:
      1. Pre-process the layer input (alpha fade-in) → labelled `[L<idx>]`
      2. Overlay it on top of `prev_label` → produces `[scene_label]`

    Returns (preprocess_fragment, overlay_fragment).
    """
    appear, dur = layer.appear_at, layer.anim_dur

    # Step 1: fade the layer's alpha in over its entrance window
    pre = (
        f"[{layer_input_idx}:v]format=rgba,"
        f"fade=t=in:st={appear:.3f}:d={dur:.3f}:alpha=1"
        f"[{layer_label}]"
    )

    # Step 2: build x/y position expressions
    x_off, y_off = _slide_offsets(layer.animation, layer.slide_distance)
    # Substitute T (time-since-appear) and D (animation duration) into the offsets
    def sub(e: str) -> str:
        return e.replace("T", f"max(0,(t-{appear:.3f}))").replace("D", f"{dur:.3f}")
    x_expr = f"{layer.x}+({sub(x_off)})"
    y_expr = f"{layer.y}+({sub(y_off)})"

    overlay = (
        f"[{prev_label}][{layer_label}]"
        f"overlay=x='{x_expr}':y='{y_expr}':enable='gte(t,{appear:.3f})'"
        f"[{scene_label}]"
    )
    return pre, overlay


async def _stitch(scenes: list[_Scene], audio: Optional[Path], out: Path,
                  w: int, h: int, fps: int = 30) -> None:
    """Build a filter_complex that:
      1. Loads each scene's background as input (with optional Ken-Burns motion)
      2. Overlays each layer onto the background with its own slide+fade entrance
      3. Crossfades between consecutive scene composites
      4. Adds a final fade-to-black + optional audio
    """
    if not scenes:
        raise RuntimeError("no scenes to stitch")

    # ── Build the input list — backgrounds first, then ALL layers grouped per scene ──
    inputs: list[str] = []
    bg_input_indices: list[int] = []
    layer_input_indices: list[list[int]] = []  # layer_input_indices[scene_i] = [input_idx_per_layer]

    cur_input = 0
    for s in scenes:
        inputs += ["-loop", "1", "-t", f"{s.duration:.3f}", "-r", str(fps), "-i", str(s.png_path)]
        bg_input_indices.append(cur_input); cur_input += 1
        layer_idxs = []
        for layer in s.layers:
            inputs += ["-loop", "1", "-t", f"{s.duration:.3f}", "-r", str(fps), "-i", str(layer.png_path)]
            layer_idxs.append(cur_input); cur_input += 1
        layer_input_indices.append(layer_idxs)

    if audio is not None:
        inputs += ["-i", str(audio)]
        audio_input_idx = cur_input

    # ── Per-scene composition: scale background + (optional) Ken-Burns + overlay layers ──
    fade_in_d = 0.30
    parts: list[str] = []
    scene_out_labels: list[str] = []

    for i, s in enumerate(scenes):
        bg_idx = bg_input_indices[i]
        frames = max(2, int(s.duration * fps))
        if s.motion == "zoompan":
            bg_chain = (
                f"[{bg_idx}:v]scale={w*2}:{h*2},zoompan="
                f"z='min(zoom+0.0008,1.10)':d={frames}:s={w}x{h}:fps={fps}"
            )
        else:
            bg_chain = f"[{bg_idx}:v]scale={w}:{h},setsar=1,fps={fps}"
        # The whole scene fades in (from black) over fade_in_d
        bg_chain += f",fade=t=in:st=0:d={fade_in_d:.2f}"
        bg_label = f"s{i}_bg"
        parts.append(f"{bg_chain}[{bg_label}]")

        # Overlay each layer in order
        prev = bg_label
        for j, layer in enumerate(s.layers):
            layer_label = f"s{i}_l{j}_a"   # alpha-faded layer
            scene_label = f"s{i}_v{j+1}"   # composite up to and including this layer
            pre, ov = _build_layer_overlay(
                layer, prev, layer_input_indices[i][j], layer_label, scene_label,
            )
            parts.append(pre)
            parts.append(ov)
            prev = scene_label
        scene_out_labels.append(prev)

    # ── Crossfade chain across scenes ──
    fade_d = 0.6
    chain = f"[{scene_out_labels[0]}]"
    cumulative = scenes[0].duration
    for i in range(1, len(scenes)):
        offset = cumulative - fade_d
        chain += (
            f"[{scene_out_labels[i]}]"
            f"xfade=transition=fade:duration={fade_d:.2f}:offset={offset:.3f}"
        )
        if i < len(scenes) - 1:
            chain += f"[xf{i}];[xf{i}]"
        cumulative += scenes[i].duration - fade_d

    # Final fade-to-black
    fade_out_d = 0.5
    fade_out_start = max(0.0, cumulative - fade_out_d)
    chain += f"[xf_out];[xf_out]fade=t=out:st={fade_out_start:.3f}:d={fade_out_d:.2f}[vout]"
    parts.append(chain)
    filter_complex = ";".join(parts)

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", "[vout]"]
    if audio is not None:
        cmd += ["-map", f"{audio_input_idx}:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out)]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        snippet = stderr.decode("utf-8", errors="replace")[-1800:]
        raise RuntimeError(f"ffmpeg failed: rc={proc.returncode}\n{snippet}")


# ── Scene auto-generator (Claude one-shot, returns JSON) ──────────────


SCENE_GENERATOR_PROMPT = """You are a senior creative director writing 4 scenes for a 15-second motion-graphics video ad. The output is a Brand Reel — no avatar, just animated text and brand visuals on Mercan Group's house style (navy + gold, premium, immigration/golden-visa for HNW investors).

Scenes:
  1 · HEADLINE  — bold one-liner, the hook (5-8 words)
  2 · SUBHEAD   — supporting line that pays off the hook (8-14 words)
  3 · STAT      — a credible number/figure + a 2-4 word label
  4 · CTA       — a single call to action (3-6 words)
And one optional VOICEOVER (35-45 words spoken, 12-15 seconds at natural pace).

HARD RULES (Mercan brand):
- Currency is USD or EUR — never invent a number you don't see in the campaign context.
- NO third-party brand names in copy (no Hilton, Marriott, IHG, Hard Rock, etc. — legal risk).
- NEVER use eligibility / qualification language ("see if you qualify", "check eligibility", "take our quiz"). The CTA is consultation-based.
- HNW investor audience — speak to motivation (security, EU access, family Plan B, ROI), never to affordability.
- Greece = real estate investment. Portugal = fund route. Panama = QIV. EB-3 = USA green card via job.
- For brand-new campaigns with no historical data, do NOT cite CPA/CPC/conversions — say nothing about performance metrics.

OUTPUT FORMAT — STRICT JSON inside <json> tags. No prose outside the tags. No markdown fences inside the JSON.

<json>
{
  "headline": "...",
  "subhead": "...",
  "stat_value": "...",
  "stat_label": "...",
  "cta": "...",
  "voiceover_script": "..."
}
</json>

If a field genuinely doesn't apply (e.g. no honest stat available), set it to "".
"""


async def fetch_url_text(url: str, *, max_chars: int = 8000) -> str:
    """Fetch a URL and strip HTML to plain text. Returns "" on any failure.

    Conservative: no JS rendering, no link following, just GET + tag strip.
    Truncates to max_chars so we don't blow the prompt budget.
    """
    import re
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "MercanStudio/1.0 (+brand-reel)"},
        ) as client:
            r = await client.get(url)
            if r.status_code != 200:
                logger.warning("URL fetch %s returned %d", url, r.status_code)
                return ""
            html = r.text
    except Exception as e:
        logger.warning("URL fetch %s failed: %s", url, e)
        return ""
    # Drop scripts/styles, then strip all tags
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode common entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
    text = text.replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


async def generate_scenes(
    brief: str,
    *,
    account_id: str | None = None,
    campaign_id: str | None = None,
    campaign_name: str | None = None,
    source_url: str | None = None,
) -> dict:
    """Run Claude one-shot with the brand prompt + optional campaign context.
    Returns {headline, subhead, stat_value, stat_label, cta, voiceover_script}.

    `source_url` (optional): a landing page or article. We fetch it, strip HTML,
    and feed the plain text to the model so the scenes match the page's claims.
    """
    context_block = ""
    if account_id and campaign_id:
        try:
            from app.services.campaign_memory import (
                load_pinned_facts, load_decisions, load_role_notes,
            )
            pinned = (load_pinned_facts(account_id, campaign_id) or "")[:2000]
            decisions = (load_decisions(account_id, campaign_id, limit=15) or "")[:2000]
            cd_notes = (load_role_notes(account_id, campaign_id, "creative_director") or "")[:1500]
            parts = []
            if campaign_name: parts.append(f"Campaign: {campaign_name}")
            if pinned: parts.append("PINNED FACTS:\n" + pinned)
            if decisions: parts.append("RECENT DECISIONS:\n" + decisions)
            if cd_notes: parts.append("CREATIVE DIRECTOR NOTES:\n" + cd_notes)
            if parts:
                context_block = "\n\n## CAMPAIGN CONTEXT\n" + "\n\n".join(parts)
        except Exception:
            logger.exception("scene generator: failed to load campaign context")

    # Optional: pull a landing-page / article to anchor copy in real claims
    url_block = ""
    if source_url:
        page_text = await fetch_url_text(source_url)
        if page_text:
            url_block = (
                f"\n\n## SOURCE PAGE (fetched from {source_url})\n"
                f"Use only claims, numbers, and program names you can find in this text. "
                f"If a stat appears here, use it; if not, leave stat_value empty.\n\n"
                f"{page_text}"
            )
        else:
            url_block = f"\n\n## SOURCE PAGE\n(URL {source_url} could not be fetched — fall back to other context.)"

    user_msg = (
        f"Brief from the user (may be empty — fall back to campaign or URL context):\n"
        f"{brief.strip() or '(no brief — use the URL/campaign context only)'}\n"
        f"{context_block}{url_block}\n\n"
        f"Now write the 4 scenes + voiceover as JSON."
    )

    full_prompt = SCENE_GENERATOR_PROMPT + "\n\n" + user_msg

    raw = await _call_claude_json(full_prompt)
    if not raw:
        raise RuntimeError("scene generator returned no output (Claude CLI unavailable or timed out)")

    parsed = _parse_scene_json(raw)
    if not parsed.get("headline"):
        raise RuntimeError("scene generator returned no headline — model may have refused")

    return parsed


_CLI_PATH_CACHE: list[str] | None = None  # argv prefix ([claude] or [node, cli.js])


def _find_claude_cli() -> list[str] | None:
    global _CLI_PATH_CACHE
    if _CLI_PATH_CACHE is not None:
        return _CLI_PATH_CACHE
    # Prefer the native-binary install (~/.local/bin/claude) — the logged-in,
    # auto-updating CLI. Checked explicitly FIRST because shutil.which can
    # miss ~/.local/bin under a stripped PATH and the npm cli.js copy can be
    # badly stale.
    native_claude = Path.home() / ".local/bin/claude"
    if native_claude.exists():
        _CLI_PATH_CACHE = [str(native_claude)]
        return _CLI_PATH_CACHE
    import glob
    node_path = shutil.which("node") or "node"
    candidates = [
        Path("/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path("/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js"),
        Path.home() / ".npm-global/lib/node_modules/@anthropic-ai/claude-code/cli.js",
    ]
    cli_js = next((p for p in candidates if p.exists()), None)
    if not cli_js:
        nvm = glob.glob(str(Path.home() / ".nvm/versions/node/*/lib/node_modules/@anthropic-ai/claude-code/cli.js"))
        if nvm:
            cli_js = Path(nvm[0])
    if not cli_js:
        try:
            r = subprocess.run([shutil.which("npm") or "npm", "root", "-g"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                candidate = Path(r.stdout.strip()) / "@anthropic-ai/claude-code/cli.js"
                if candidate.exists():
                    cli_js = candidate
        except Exception:
            pass
    if not cli_js:
        which_claude = shutil.which("claude")
        if which_claude:
            _CLI_PATH_CACHE = [which_claude]
            return _CLI_PATH_CACHE
        return None
    _CLI_PATH_CACHE = [node_path, str(cli_js)]
    return _CLI_PATH_CACHE


async def _call_claude_json(prompt: str, model: str = "claude-opus-4-8", timeout_s: int = 120) -> str | None:
    """Call Claude CLI in one-shot mode, return concatenated text output. Async-safe."""
    cli_cmd = _find_claude_cli()
    if not cli_cmd:
        logger.warning("Claude CLI not found for scene generator")
        return None

    cmd = [
        *cli_cmd,
        "--print", "--verbose", "--output-format", "stream-json",
        "--max-turns", "1",
        "--model", model,
        "--permission-mode", "bypassPermissions",
    ]
    import os, json as _json
    env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "sdk-py"}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_SESSION", None)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode("utf-8")),
            timeout=timeout_s,
        )
        if proc.returncode != 0:
            logger.warning("scene generator CLI failed (rc=%d): %s",
                           proc.returncode, stderr.decode("utf-8", errors="replace")[:300])
            return None
        text_parts: list[str] = []
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = _json.loads(line)
                if data.get("type") == "assistant":
                    for block in data.get("message", {}).get("content", []):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
            except (_json.JSONDecodeError, KeyError):
                continue
        return "\n".join(text_parts) if text_parts else None
    except asyncio.TimeoutError:
        logger.warning("scene generator timed out after %ds", timeout_s)
        return None
    except Exception as e:
        logger.warning("scene generator error: %s", e)
        return None


STORYBOARD_PROMPT = """You are running a small VIDEO PRODUCTION TEAM for a Mercan Group brand reel. Four specialists collaborate inside this single response — read each role's brief carefully and produce one storyboard JSON that reflects ALL FOUR roles' decisions inline.

═══════════════════════════════════════════════
ROLE 1 · DIRECTOR (story arc + scene count)
═══════════════════════════════════════════════
You decide the narrative. A great brand reel follows a story arc, NOT a feature dump:
  PROBLEM → CONTEXT → PROOF → SOLUTION → INVITATION
- Open with a hook (hero or logo) that frames the audience's WHY.
- Build tension/context with broll scenes — let images tell the story.
- Land 1-3 stats as proof points (only stats verified in the brief/context).
- Resolve with a clear call-to-action (cta).
- If a [LOGO] image is in the library, OPEN with a `logo` scene (brand-mark intro) AND CLOSE the cta with the same logo above the CTA text.

═══════════════════════════════════════════════
ROLE 2 · CINEMATOGRAPHER (per-scene composition + motion)
═══════════════════════════════════════════════
Every broll scene gets TWO fields: `composition` (the layout) and `motion` (the camera move on the background image).

`composition` — pick one from this palette and ROTATE so consecutive broll scenes never share the same composition:
  - "fullbleed"   : full-screen photo, caption bottom-left with gold accent (default — use for hero broll moments)
  - "letterbox"   : 21:9 cinematic crop with corner brackets drawing in, caption centered in lower bar (use for "this is a film" moments — credibility, scope, beauty shots)
  - "split"       : image left 56%, copy right 44% with vertical gold divider (use for declarative claims, brand statements, where copy is the focus)
  - "lowerthird"  : full image with broadcast-style lower-third strip + scene-label eyebrow (use for fact/proof beats, location reveals)

`motion` — pick from:
  - "kenburns-zoom-in"   : slow zoom toward subject (intimacy)
  - "kenburns-zoom-out"  : slow pull back (revelation, scale)
  - "pan-left"           : horizontal drift L→R
  - "pan-right"          : horizontal drift R→L
  - "dolly-in"           : aggressive forward push (drama)
  - "parallax-tilt"      : subtle perspective tilt (depth, modernism)

Variety rule: across N broll scenes, use AT LEAST 3 different compositions if N≥4. Match composition+motion combo to caption mood.

═══════════════════════════════════════════════
ROLE 3 · COPYWRITER (every line of text)
═══════════════════════════════════════════════
- hero `headline`         : 4-7 words, declarative, no period.
- broll `caption`         : 5-10 words. Single evocative sentence. NO third-party brand names (Hilton, Marriott, IHG, Hard Rock — legal risk). NO eligibility/qualification language. HNW investor audience — speak to motivation, not affordability.
- broll `scene_label`     : OPTIONAL 1-3 word location/project tag (e.g. "Évora, Portugal", "Athens"). Omit if unknown.
- stat                    : `stat_value` is the number alone (e.g. "37"). `stat_label` is 2-5 words (e.g. "years of trust"). NEVER invent stats — only use numbers verifiable in the brief/context.
- cta                     : 4-8 words, action verb first, consultation-based ("Book a free consultation", "Speak with a strategist").

═══════════════════════════════════════════════
ROLE 4 · MOTION DESIGNER (per-scene text reveal)
═══════════════════════════════════════════════
Every broll scene also gets a `text_treatment` field — pick from this palette and VARY across scenes (don't use the same one twice in a row):
  - "blur-stagger"       : per-word blur reveal (the default — calm, premium)
  - "slide-up"           : per-word slide up from below (energetic)
  - "scale-bounce"       : per-word scale in with bounce (playful, attention-grabbing)
  - "typewriter"         : char-by-char typewriter (data-feel, journalistic)
  - "scale-bounce-chars" : per-CHAR bounce (high-impact short captions)
  - "mask-reveal"        : line slides into view via clip-path (cinematic title-card)

═══════════════════════════════════════════════
ROLE 5 · STOCK IMAGE SOURCER (for missing images)
═══════════════════════════════════════════════
If the LIBRARY is empty OR lacks an obvious match for a broll scene, add an
`image_search_query` field instead of `image_filename`.

CRITICAL — queries MUST be generic enough to find results on Pexels/Unsplash:
  ✅ GOOD (returns matches):
    "modern hotel lobby golden hour"
    "diverse family airport luggage"
    "boardroom handshake business meeting"
    "european cityscape skyline sunset"
    "luxury beach resort poolside"
    "passport stamp travel document"
    "professional consultation meeting office"
  ❌ BAD (returns nothing):
    "Mercan portfolio building Évora"
    "37 years of brand trust"
    "regulated hospitality fund €500K"

Rules:
  - 2-6 words, no brand names, no numbers, no proper nouns of small places
  - Use generic photographic categories: people, places, activities, objects
  - Match the EMOTIONAL beat of the caption, not the literal copy
  - Prefer queries you've seen as common stock photo subjects

If you DO have a good library image, ALWAYS prefer it over a search query.

═══════════════════════════════════════════════
PER-SCENE USER INSTRUCTIONS (highest priority)
═══════════════════════════════════════════════
Some scenes may carry an `instructions` string the user typed in the planner —
e.g. "use a Portugal flag image", "make this scene about Greek islands", "punch
the number harder". Treat these as overrides:
  - If `instructions` mentions a location, use that as `scene_label` and steer
    `image_search_query` toward it.
  - If `instructions` requests a stat punch, use a stat scene type.
  - If `instructions` requests a flag/symbol, write `image_search_query` like
    "[country] flag waving close-up" — backend fetches a stock match.
  - When echoing scenes back, preserve any incoming `instructions` field.

═══════════════════════════════════════════════
SCENE TYPES
═══════════════════════════════════════════════
1. **logo**   — brand-mark intro. Big logo + brand name + tagline. Use ONCE at start when a [LOGO] image exists in library. Skip if no logo image.
2. **hero**   — opening title (or 2nd scene after logo). Big bold headline. Use ONCE per reel.
3. **broll**  — image + kinetic caption. ONE library image (NOT [LOGO]) per scene. Use these to walk through projects, locations, proof points.
4. **stat**   — single big number reveal. Use 1-3 to anchor credibility.
5. **cta**    — closing call-to-action. Use ONCE at the very end. Set `logo_filename` to the library logo if available.

DURATION BUDGET (averages — mix to hit target):
  logo: 4s · hero: 4s · broll: 5s · stat: 4s · cta: 5s
  60s ≈ 11-13 scenes with 0.6s crossfades between each.

═══════════════════════════════════════════════
OUTPUT FORMAT — STRICT JSON inside <json> tags. No prose outside the tags. No markdown fences inside.
═══════════════════════════════════════════════

<json>
{
  "scenes": [
    {"type": "logo", "logo_filename": "<storage_id of [LOGO] image>", "brand_name": "MERCAN GROUP", "tagline": "INVESTMENT IMMIGRATION · 30+ YEARS"},
    {"type": "hero", "headline": "Three decades of proven strategy"},
    {"type": "broll", "image_filename": "<storage_id>", "caption": "...", "scene_label": "Évora, Portugal", "composition": "letterbox", "motion": "kenburns-zoom-in", "text_treatment": "blur-stagger"},
    {"type": "broll", "image_search_query": "luxury hotel exterior mediterranean golden hour", "caption": "...", "composition": "split", "motion": "pan-right", "text_treatment": "slide-up"},
    {"type": "stat", "stat_value": "37", "stat_label": "years of trusted experience"},
    {"type": "broll", "image_filename": "<storage_id>", "caption": "...", "motion": "dolly-in", "text_treatment": "scale-bounce"},
    {"type": "cta", "cta": "Speak with a strategist", "logo_filename": "<storage_id of [LOGO] image>", "brand_name": "MERCAN GROUP", "tagline": "INVESTMENT IMMIGRATION"}
  ]
}
</json>

CRITICAL: rotate `motion` and `text_treatment` so consecutive broll scenes never share both. Variety is what makes this look professionally edited rather than templated.
"""


async def generate_storyboard(
    brief: str,
    target_seconds: int,
    library_images: list[dict],   # [{"filename": "...", "width": 1920, "height": 1080}, ...]
    *,
    account_id: str | None = None,
    campaign_id: str | None = None,
    campaign_name: str | None = None,
    source_url: str | None = None,
    target_scenes: int | None = None,    # explicit override; None = auto from duration
) -> list[dict]:
    """Generate an N-scene storyboard. Returns a list of scene dicts.

    Each scene dict has at minimum a `type` field; other fields depend on type.
    """
    # Build context block (same pattern as generate_scenes)
    context_block = ""
    if account_id and campaign_id:
        try:
            from app.services.campaign_memory import (
                load_pinned_facts, load_decisions, load_role_notes,
            )
            pinned = (load_pinned_facts(account_id, campaign_id) or "")[:2000]
            decisions = (load_decisions(account_id, campaign_id, limit=15) or "")[:1500]
            cd_notes = (load_role_notes(account_id, campaign_id, "creative_director") or "")[:1500]
            parts = []
            if campaign_name: parts.append(f"Campaign: {campaign_name}")
            if pinned: parts.append("PINNED FACTS:\n" + pinned)
            if decisions: parts.append("RECENT DECISIONS:\n" + decisions)
            if cd_notes: parts.append("CREATIVE DIRECTOR NOTES:\n" + cd_notes)
            if parts:
                context_block = "\n\n## CAMPAIGN CONTEXT\n" + "\n\n".join(parts)
        except Exception:
            logger.exception("storyboard generator: failed to load campaign context")

    url_block = ""
    if source_url:
        # Accept comma-separated URLs — fetch each and concatenate their text.
        urls = [u.strip() for u in source_url.split(",") if u.strip()]
        fetched: list[tuple[str, str]] = []
        for u in urls:
            try:
                txt = await fetch_url_text(u)
                if txt:
                    fetched.append((u, txt))
            except Exception:
                logger.warning("storyboard generator: failed to fetch %s", u)
        if fetched:
            url_block = "\n\n## SOURCE PAGES\nUse only claims/numbers/program names you can verify in this text.\n"
            for u, txt in fetched:
                url_block += f"\n### {u}\n{txt}\n"

    # Library images — show the model the original (display) filename so it
    # can pick scene fit by reading the name, but tell it to write back the
    # storage filename in `image_filename` for our validator.
    img_block = "\n\n## AVAILABLE LIBRARY IMAGES (assign one per broll scene)\n"
    img_block += "Format: `<storage_id>` — original: `<readable_name>` (<dims>)\n"
    img_block += "When you assign an image to a scene, copy the `<storage_id>` (the first backtick-quoted value) verbatim into `image_filename`.\n"
    img_block += "Images marked [LOGO] go in `logo` scenes (brand-mark intro) and `cta` scenes (set `logo_filename` to that storage_id). NEVER use a [LOGO] image as a broll image_filename — broll Ken-Burns'es the photo which looks wrong on a logo.\n\n"
    import re as _re
    for img in library_images:
        dims = f"{img.get('width','?')}×{img.get('height','?')}"
        display = img.get("display_name") or img["filename"]
        is_logo = bool(_re.search(r"(^|[^a-z])logo([^a-z]|$)", display, _re.IGNORECASE))
        tag = " [LOGO]" if is_logo else ""
        img_block += f"- `{img['filename']}` — original: `{display}` ({dims}){tag}\n"

    # Estimate scene count target
    avg_scene_s = 4.6  # weighted average across types
    # User can override the recommended count; otherwise auto from duration.
    if target_scenes is None or target_scenes <= 0:
        target_scenes = max(3, round(target_seconds / avg_scene_s))

    user_msg = (
        f"Brief: {brief.strip() or '(no brief — use context only)'}\n"
        f"Target duration: ~{target_seconds} seconds (≈ {target_scenes} scenes — adjust ±2)\n"
        f"{context_block}{url_block}{img_block}\n\n"
        f"Now produce the storyboard JSON."
    )

    raw = await _call_claude_json(
        STORYBOARD_PROMPT + "\n\n" + user_msg,
        timeout_s=180,
    )
    if not raw:
        raise RuntimeError("storyboard generator returned no output")

    # Reuse the json extractor but expect a top-level "scenes" key
    import re, json as _json
    m = re.search(r"<json>(.*?)</json>", raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1).strip() if m else raw.strip()
    if body.startswith("```"):
        body = re.sub(r"^```\w*\s*|\s*```$", "", body, flags=re.MULTILINE).strip()
    if not body.startswith("{"):
        m2 = re.search(r"\{.*\}", body, re.DOTALL)
        if m2: body = m2.group(0)
    try:
        data = _json.loads(body)
    except _json.JSONDecodeError as e:
        raise RuntimeError(f"storyboard returned non-JSON: {e}; body[:300]={body[:300]!r}")

    scenes = data.get("scenes") or []
    if not isinstance(scenes, list) or not scenes:
        raise RuntimeError("storyboard returned no scenes")

    # Validate + clean
    valid_filenames = {img["filename"] for img in library_images}
    # Identify the LOGO image (if any) so we can validate logo_filename refs
    import re as _re_logo
    def _is_logo(name: str) -> bool:
        return bool(_re_logo.search(r"(^|[^a-z])logo([^a-z]|$)", name, _re_logo.IGNORECASE))
    logo_filenames = {
        img["filename"] for img in library_images
        if _is_logo(img.get("display_name") or img["filename"])
    }
    # Allowed motion + text-treatment palettes (must match the broll template's switch)
    motion_palette = {
        "kenburns-zoom-in", "kenburns-zoom-out",
        "pan-left", "pan-right", "dolly-in", "parallax-tilt",
    }
    text_palette = {
        "blur-stagger", "slide-up", "scale-bounce",
        "typewriter", "scale-bounce-chars", "mask-reveal",
    }
    composition_palette = {"fullbleed", "letterbox", "split", "lowerthird"}

    def _attach_instructions(out: dict, src: dict) -> dict:
        """Preserve any user-typed scene instructions from the planner so they
        round-trip through the render pipeline (and are visible if the user
        regenerates)."""
        instr = (src.get("instructions") or src.get("user_instructions") or "").strip()
        if instr:
            out["instructions"] = instr
        return out

    cleaned: list[dict] = []
    for s in scenes:
        if not isinstance(s, dict): continue
        t = (s.get("type") or "").strip().lower()
        if t == "hero":
            cleaned.append(_attach_instructions(
                {"type": "hero", "headline": (s.get("headline") or "").strip()}, s))
        elif t == "logo":
            logo_fn = (s.get("logo_filename") or "").strip()
            if logo_fn and logo_fn not in valid_filenames:
                # Try to recover by picking the first logo image we can identify
                logo_fn = next(iter(logo_filenames), "")
            if not logo_fn:
                logger.warning("storyboard: dropped logo scene — no usable logo image in library")
                continue
            cleaned.append(_attach_instructions({
                "type": "logo",
                "logo_filename": logo_fn,
                "brand_name": (s.get("brand_name") or "").strip(),
                "tagline": (s.get("tagline") or "").strip(),
            }, s))
        elif t == "broll":
            fn = (s.get("image_filename") or "").strip()
            search_query = (s.get("image_search_query") or "").strip()
            # Allow either a library reference OR a search query — the router's
            # storyboard endpoint resolves search queries to fetched stock images.
            if fn:
                if fn not in valid_filenames:
                    logger.warning("storyboard: dropped broll with invalid filename %r (not in library)", fn)
                    continue
                if fn in logo_filenames:
                    logger.warning("storyboard: broll picked a [LOGO] image (%s) — dropping", fn)
                    continue
            elif not search_query:
                logger.warning("storyboard: dropped broll with neither image_filename nor image_search_query")
                continue
            motion = (s.get("motion") or "").strip().lower()
            if motion not in motion_palette: motion = "kenburns-zoom-in"
            tt = (s.get("text_treatment") or "").strip().lower()
            if tt not in text_palette: tt = "blur-stagger"
            comp = (s.get("composition") or "").strip().lower()
            if comp not in composition_palette: comp = "fullbleed"
            scene_out = {
                "type": "broll",
                "image_filename": fn,    # may be empty — router fills via stock search
                "caption": (s.get("caption") or "").strip(),
                "scene_label": (s.get("scene_label") or "").strip(),
                "composition": comp,
                "motion": motion,
                "text_treatment": tt,
            }
            if search_query:
                scene_out["image_search_query"] = search_query
            cleaned.append(_attach_instructions(scene_out, s))
        elif t == "stat":
            cleaned.append(_attach_instructions({
                "type": "stat",
                "stat_value": (s.get("stat_value") or "").strip(),
                "stat_label": (s.get("stat_label") or "").strip(),
            }, s))
        elif t == "cta":
            logo_fn = (s.get("logo_filename") or "").strip()
            if logo_fn and logo_fn not in valid_filenames:
                logo_fn = next(iter(logo_filenames), "")
            cleaned.append(_attach_instructions({
                "type": "cta",
                "cta": (s.get("cta") or "Book a free consultation").strip(),
                "logo_filename": logo_fn,
                "brand_name": (s.get("brand_name") or "").strip(),
                "tagline": (s.get("tagline") or "").strip(),
            }, s))

    if not cleaned:
        raise RuntimeError("storyboard returned no usable scenes after validation")
    return cleaned


def _parse_scene_json(raw: str) -> dict:
    """Pull JSON out of <json>...</json> tags (or fall back to first {...} block)."""
    import re, json as _json
    m = re.search(r"<json>(.*?)</json>", raw, re.DOTALL | re.IGNORECASE)
    body = m.group(1).strip() if m else raw.strip()
    if body.startswith("```"):
        body = re.sub(r"^```\w*\s*|\s*```$", "", body, flags=re.MULTILINE).strip()
    if not body.startswith("{"):
        m2 = re.search(r"\{.*\}", body, re.DOTALL)
        if m2:
            body = m2.group(0)
    try:
        data = _json.loads(body)
    except _json.JSONDecodeError as e:
        raise RuntimeError(f"scene generator returned non-JSON: {e}; body[:200]={body[:200]!r}")
    return {
        "headline": (data.get("headline") or "").strip(),
        "subhead": (data.get("subhead") or "").strip(),
        "stat_value": (data.get("stat_value") or "").strip(),
        "stat_label": (data.get("stat_label") or "").strip(),
        "cta": (data.get("cta") or "Book a free consultation").strip(),
        "voiceover_script": (data.get("voiceover_script") or "").strip(),
    }
