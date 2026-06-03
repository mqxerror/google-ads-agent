---
date: 2026-04-29
type: improvement
title: Brand Reel — cinematic intro/outro + Studio upload fixes
tags: [studio, video, brand]
---

Polish pass on the Brand Reel after first real renders.

**Intro upgraded.** The hero scene now has:
- Smooth navy → black vertical gradient (no more flat block)
- Top-left "MERCAN GROUP" brand mark with gold underline
- Auto-sized headline that wraps to ≤2 lines with a subtle drop shadow
- Gold underline accent + tagline ("INVESTMENT IMMIGRATION · EU RESIDENCY") below the headline
- Soft gold radial glow in the upper-right for depth

**Outro fixed.** The CTA scene was getting cut and brand mark sometimes left the frame. Now:
- CTA text auto-wraps to ≤2 lines (long CTAs like "Book Your Private Consultation" fit cleanly)
- Gold double-border around the CTA (cleaner than the old 4-row outline)
- Brand mark + tagline are positioned in a reserved zone below the box — guaranteed to stay in frame
- Final 0.5s fade-to-black so the video doesn't end abruptly

**Per-scene fade-in.** Every scene now fades in over 0.3s on top of the existing crossfades. No more abrupt cuts when a scene starts.

### Studio upload
- Backend dep (`python-multipart`) is now properly synced — restart the backend after pulling. Upload errors mention this if they detect the symptom.
- Upload errors now surface in a single grouped alert with HTTP status + detail, instead of a vague "Upload failed".
- Campaign scope is now passed with the upload (so files land in the selected campaign's slice of the library).
- New **🔒 local only** badge in the Studio header — files stay on this machine, never uploaded to Google or any cloud.

### What's next (planned, not shipped)
The user asked for "Hyperframes-style beautiful animated text". That's true kinetic typography (per-letter reveals, blur-in, gradient text) which Pillow can't produce — it needs HTML+GSAP. Plan saved as **Phase B — Premium Reel** in `research/hyperframes_premium_reel_plan.md`. Will land as a third Studio mode alongside Avatar Snap and Brand Reel, ~3-4 working days when prioritised.
