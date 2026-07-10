#!/usr/bin/env python3
"""
Video Builder - creates real, watchable vertical Shorts.
- Branded animated gradient background (NeuronOv3rload: blue/purple on dark)
- Large wrapped title
- Synced caption chunks that follow the narration
- Subtle zoom motion so YouTube sees it as real video
Pure ffmpeg + Pillow, runs anywhere (incl. GitHub Actions).
"""

import os
import re
import json
import math
import textwrap
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Brand palette
BG_TOP = (18, 16, 38)        # deep indigo
BG_BOT = (8, 8, 16)          # near black
ACCENT_BLUE = (56, 189, 248) # electric blue
ACCENT_PURPLE = (168, 85, 247)


def _audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", audio_path],
            capture_output=True, text=True, check=True
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return 30.0


def _gradient_bg() -> Image.Image:
    """Vertical gradient background with soft glow blobs in brand colors."""
    base = Image.new("RGB", (W, H), BG_BOT)
    top = Image.new("RGB", (W, H), BG_TOP)
    mask = Image.new("L", (W, H))
    md = mask.load()
    for y in range(H):
        v = int(255 * (1 - y / H) ** 1.3)
        for x in range(W):
            md[x, y] = v
    base = Image.composite(top, base, mask)

    # glow blobs
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, 200, 600, 1000], fill=ACCENT_PURPLE)
    gd.ellipse([600, 900, 1300, 1700], fill=ACCENT_BLUE)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    base = Image.blend(base, ImageChops_screen(base, glow), 0.5)
    return base


def ImageChops_screen(a, b):
    from PIL import ImageChops
    return ImageChops.screen(a, b)


def _fit_font(draw, text, font_path, max_w, start, min_size=40):
    size = start
    while size > min_size:
        font = ImageFont.truetype(font_path, size)
        wrapped = _wrap(draw, text, font, max_w)
        w = max((draw.textbbox((0, 0), ln, font=font)[2] for ln in wrapped), default=0)
        if w <= max_w:
            return font, wrapped
        size -= 4
    font = ImageFont.truetype(font_path, min_size)
    return font, _wrap(draw, text, font, max_w)


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw_center(draw, lines, font, y, fill, line_gap=14, stroke=0, stroke_fill=(0, 0, 0)):
    """Draw each line horizontally centered using anchor-based positioning."""
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    for ln in lines:
        draw.text((W // 2, y), ln, font=font, fill=fill, anchor="ma",
                  stroke_width=stroke, stroke_fill=stroke_fill)
        y += line_h + line_gap
    return y


def _title_frame(title: str) -> Image.Image:
    """Background + title + subtle brand tag, used as the base plate."""
    img = _gradient_bg()
    draw = ImageDraw.Draw(img)

    # subtle brand tag: small, letter-spaced, muted, centered at very top
    tag_font = ImageFont.truetype(FONT_BOLD, 26)
    tag = " ".join("neuron0v3rload".upper())  # letter-spaced
    draw.text((W // 2, 84), tag, font=tag_font, fill=(120, 132, 168), anchor="ma")

    # title, centered
    tfont, tlines = _fit_font(draw, title.upper(), FONT_BOLD, W - 160, 96, 52)
    _draw_center(draw, tlines, tfont, 360, (255, 255, 255),
                 stroke=3, stroke_fill=(0, 0, 0))
    return img


def _caption_png(text: str, path: str):
    """Transparent PNG with a caption chunk (bottom third)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font, lines = _fit_font(draw, text, FONT_BOLD, W - 160, 78, 46)

    line_h = draw.textbbox((0, 0), "Ag", font=font)[3] + 18
    block_h = line_h * len(lines)
    y0 = H - 560 - block_h // 2

    # rounded backdrop
    pad = 40
    max_w = max(draw.textbbox((0, 0), ln, font=font)[2] for ln in lines)
    x0 = (W - max_w) // 2 - pad
    x1 = (W + max_w) // 2 + pad
    draw.rounded_rectangle([x0, y0 - pad, x1, y0 + block_h + pad],
                           radius=32, fill=(0, 0, 0, 150))
    _draw_center(draw, lines, font, y0, (255, 255, 255),
                 stroke=3, stroke_fill=(0, 0, 0))
    img.save(path)


def _clean_script(script: str):
    """Strip timestamps/labels, return list of caption chunks."""
    txt = re.sub(r"\[[^\]]*\]", " ", script)          # [0:00-0:03]
    txt = re.sub(r"\b(HOOK|CONTENT|CTA)\b:?", " ", txt, flags=re.I)
    txt = re.sub(r"\s+", " ", txt).strip()
    # split into sentence-ish chunks
    parts = re.split(r"(?<=[.!?]) +", txt)
    chunks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # further split long sentences
        if len(p) > 90:
            chunks.extend(textwrap.wrap(p, 80))
        else:
            chunks.append(p)
    return [c for c in chunks if c]


def _pick_music(script_dir: str):
    """Return a random royalty-free track from a music/ folder, if any exist."""
    import random
    music_dir = os.path.join(script_dir, "music")
    if not os.path.isdir(music_dir):
        return None
    tracks = [os.path.join(music_dir, f) for f in os.listdir(music_dir)
              if f.lower().endswith((".mp3", ".m4a", ".wav", ".aac", ".ogg"))]
    return random.choice(tracks) if tracks else None


def build_video(video_id: int, title: str, script: str,
                voiceover_path: str, output_dir: str,
                music_path: str = None) -> str:
    """Assemble a real, watchable vertical short."""
    os.makedirs(output_dir, exist_ok=True)
    dur = _audio_duration(voiceover_path)

    # auto-pick background music if a music/ folder exists next to the script
    if music_path is None:
        music_path = _pick_music(os.path.dirname(os.path.abspath(__file__)))

    # base plate
    base_path = os.path.join(output_dir, f"_base_{video_id}.png")
    _title_frame(title).save(base_path)

    # captions
    chunks = _clean_script(script) or [title]
    per = max(dur / len(chunks), 1.2)
    cap_dir = os.path.join(output_dir, f"_caps_{video_id}")
    os.makedirs(cap_dir, exist_ok=True)
    cap_files = []
    for i, ch in enumerate(chunks):
        p = os.path.join(cap_dir, f"cap_{i:03d}.png")
        _caption_png(ch, p)
        cap_files.append((p, i * per, min((i + 1) * per, dur) - 0.08))

    # build inputs: base image, caption PNGs, voiceover, (optional looped music)
    inputs = ["-loop", "1", "-i", base_path]
    for p, _, _ in cap_files:
        inputs += ["-i", p]
    voice_idx = len(cap_files) + 1
    inputs += ["-i", voiceover_path]
    music_idx = None
    if music_path and os.path.exists(music_path):
        music_idx = voice_idx + 1
        inputs += ["-stream_loop", "-1", "-i", music_path]  # loop to cover length

    # video filter: subtle zoom + timed caption overlays
    fps = 30
    filt = (
        f"[0:v]scale={W}:{H},zoompan=z='min(zoom+0.0006,1.10)':"
        f"d={int(dur*fps)}:s={W}x{H}:fps={fps}[bg]"
    )
    last = "bg"
    for idx, (_, start, end) in enumerate(cap_files, start=1):
        nxt = f"v{idx}"
        filt += (f";[{last}][{idx}:v]overlay=0:0:"
                 f"enable='between(t,{start:.2f},{end:.2f})'[{nxt}]")
        last = nxt

    # audio filter: voice full volume, music ducked underneath
    if music_idx is not None:
        filt += (f";[{voice_idx}:a]volume=1.0[va]"
                 f";[{music_idx}:a]volume=0.12[ma]"
                 f";[va][ma]amix=inputs=2:duration=first:normalize=0[aout]")
        audio_map = "[aout]"
    else:
        audio_map = f"{voice_idx}:a"

    out = os.path.join(output_dir, f"video_{video_id}.mp4")
    cmd = ["ffmpeg", "-y", *inputs,
           "-filter_complex", filt,
           "-map", f"[{last}]", "-map", audio_map,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "192k",
           "-pix_fmt", "yuv420p", "-t", f"{dur:.2f}",
           "-r", str(fps), out]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


if __name__ == "__main__":
    # DEMO with a generated tone as stand-in for the ElevenLabs voiceover
    demo_dir = "/home/claude/demo_out"
    os.makedirs(demo_dir, exist_ok=True)
    tone = os.path.join(demo_dir, "demo_audio.m4a")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "sine=frequency=220:duration=18", "-c:a", "aac", tone],
        check=True, capture_output=True)

    demo_title = "June Home Sales Hit An All-Time High"
    demo_script = (
        "[0:00-0:03] HOOK: Wait until you hear what just happened to home prices. "
        "In June, the housing market did something almost nobody expected. "
        "Sales actually disappointed, even as prices smashed a brand new record high. "
        "That means buyers are paying more than ever, for fewer homes. "
        "Economists say this squeeze could reshape the market for years. "
        "[CTA] Follow for the numbers nobody is talking about."
    )
    path = build_video(1, demo_title, demo_script, tone, demo_dir)
    print("BUILT", path)
