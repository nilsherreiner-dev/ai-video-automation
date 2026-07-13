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
    tag = " ".join("neuronoverload".upper())  # letter-spaced
    draw.text((W // 2, 84), tag, font=tag_font, fill=(120, 132, 168), anchor="ma")

    # title, centered
    tfont, tlines = _fit_font(draw, _clean_title(title).upper(), FONT_BOLD, W - 160, 96, 52)
    _draw_center(draw, tlines, tfont, 360, (255, 255, 255),
                 stroke=3, stroke_fill=(0, 0, 0))
    return img


CAP_YELLOW = (255, 214, 10)


def _render_caption_line(line_words, active_idx, path, font_size=72):
    """Render a caption line with the active word highlighted, auto-fit to width."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_w = W - 120
    size = font_size
    while size > 40:
        font = ImageFont.truetype(FONT_BOLD, size)
        space = draw.textlength(" ", font=font)
        widths = [draw.textlength(w, font=font) for w in line_words]
        total = sum(widths) + space * (len(line_words) - 1) + 40  # +box padding
        if total <= max_w:
            break
        size -= 4

    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    y = H - 640
    x = (W - (sum(widths) + space * (len(line_words) - 1))) / 2
    for i, w in enumerate(line_words):
        wl = widths[i]
        if i == active_idx:
            pad = 16
            draw.rounded_rectangle(
                [x - pad, y - 8, x + wl + pad, y + line_h + 4],
                radius=18, fill=(0, 0, 0, 215))
            draw.text((x, y), w, font=font, fill=CAP_YELLOW,
                      stroke_width=3, stroke_fill=(0, 0, 0))
        else:
            draw.text((x, y), w, font=font, fill=(255, 255, 255),
                      stroke_width=4, stroke_fill=(0, 0, 0))
        x += wl + space
    img.save(path)


def _group_words(words):
    """Group timed words into caption lines that fit the width (measured)."""
    tmp = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(tmp)
    font = ImageFont.truetype(FONT_BOLD, 72)
    space = draw.textlength(" ", font=font)
    max_w = W - 160

    lines, cur, cur_w = [], [], 0.0
    for w in words:
        ww = draw.textlength(w[0], font=font)
        add = ww + (space if cur else 0)
        if cur and (cur_w + add > max_w or len(cur) >= 5):
            lines.append(cur)
            cur, cur_w = [], 0.0
            add = ww
        cur.append(w)
        cur_w += add
    if cur:
        lines.append(cur)
    return lines


def _karaoke_track(words, dur, work_dir):
    """Transparent .mov caption track: whole line stays visible, highlight moves."""
    sub = os.path.join(work_dir, "_work", "caps")
    os.makedirs(sub, exist_ok=True)
    blank = os.path.join(sub, "blank.png")
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)

    lines = _group_words(words)
    segments = []  # (png, duration)
    t = 0.0
    idx = 0
    for li, line in enumerate(lines):
        texts = [w[0] for w in line]
        line_start = line[0][1]
        # keep this line on screen until the next line's first word starts
        if li + 1 < len(lines):
            display_end = lines[li + 1][0][1]
        else:
            display_end = max(dur, line[-1][2])

        if line_start > t + 0.02:
            segments.append((blank, line_start - t))
            t = line_start

        for wi in range(len(line)):
            # highlight persists through the pause until the next word begins
            if wi + 1 < len(line):
                seg_end = line[wi + 1][1]
            else:
                seg_end = display_end
            seg_end = max(seg_end, t + 0.08)
            png = os.path.join(sub, f"l{idx:04d}.png")
            _render_caption_line(texts, wi, png)
            segments.append((png, seg_end - t))
            t = seg_end
            idx += 1

    if t < dur:
        segments.append((blank, dur - t))

    listfile = os.path.join(sub, "list.txt")
    with open(listfile, "w") as f:
        for p, d in segments:
            f.write(f"file '{os.path.abspath(p)}'\n")
            f.write(f"duration {max(d, 0.05):.3f}\n")
        f.write(f"file '{os.path.abspath(segments[-1][0])}'\n")

    out = os.path.join(work_dir, "_work", "caps.mov")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
           "-vf", "fps=30,format=rgba", "-c:v", "qtrle", "-t", f"{dur:.2f}", out]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


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


def _clean_title(title: str) -> str:
    """Strip trailing news-source suffix like ' - Allrecipes' or ' | CNBC'."""
    t = re.sub(r"\s*[-|–—]\s*[^-|–—]{1,30}$", "", title).strip()
    return t or title


def normalize_for_speech(text: str) -> str:
    """Fixes so TTS reads correctly AND punchy (no dramatic pauses)."""
    text = re.sub(r"(?<=\d),(?=\d)", "", text)   # 1,200 -> 1200
    text = text.replace("%", " percent")

    # kill pause-inducing punctuation — these make ElevenLabs slow down hard
    text = text.replace("…", " ")
    text = re.sub(r"\.{2,}", " ", text)          # "..." -> space
    text = re.sub(r"\s*[—–]\s*", " ", text)      # em/en dash -> space
    text = re.sub(r"\s+-\s+", " ", text)         # spaced hyphen -> space
    text = re.sub(r"[:;]", ",", text)            # softer than a full stop
    text = re.sub(r"\s*,\s*,+", ", ", text)      # collapse doubled commas
    text = re.sub(r"\s+([.,!?])", r"\1", text)   # no space before punctuation

    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_text(script: str) -> str:
    """Strip timestamps/labels/stage-directions so they are not read aloud."""
    txt = re.sub(r"\[[^\]]*\]", " ", script)              # [0:00-0:03]
    txt = re.sub(r"\([^)]*\)", " ", txt)                  # (pause), (excited)
    txt = re.sub(r"\*[^*]*\*", " ", txt)                  # *emphasis* stage cues
    txt = re.sub(r"(?mi)^\s*(HOOK|CONTENT|CTA|SCRIPT|VOICEOVER|NARRATOR)\s*:?",
                 " ", txt)
    txt = re.sub(r"\b(HOOK|CONTENT|CTA)\b:?", " ", txt, flags=re.I)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _clean_script(script: str):
    """Return caption-sized chunks of the cleaned narration text."""
    txt = clean_text(script)
    parts = re.split(r"(?<=[.!?]) +", txt)
    chunks = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 90:
            chunks.extend(textwrap.wrap(p, 80))
        else:
            chunks.append(p)
    return [c for c in chunks if c]


def _fit_title(draw, text, max_w, max_h, start=78, min_size=42, max_lines=4):
    """Fit title within width AND height, capped to max_lines (truncate if needed)."""
    size = start
    while size >= min_size:
        font = ImageFont.truetype(FONT_BOLD, size)
        lines = _wrap(draw, text, font, max_w)
        a, d = font.getmetrics()
        lh = a + d + 12
        fits_w = all(draw.textbbox((0, 0), ln, font=font)[2] <= max_w for ln in lines)
        if len(lines) <= max_lines and lh * len(lines) <= max_h and fits_w:
            return font, lines, lh
        size -= 4
    font = ImageFont.truetype(FONT_BOLD, min_size)
    a, d = font.getmetrics()
    lh = a + d + 12
    lines = _wrap(draw, text, font, max_w)[:max_lines]
    if lines:
        lines[-1] = lines[-1].rstrip() + "…"
    return font, lines, lh


def _title_overlay_png(title: str, path: str):
    """Transparent PNG: small brand tag + compact title in the UPPER area only,
    sized so it never reaches the caption zone."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    title = _clean_title(title).upper()
    top, max_h = 300, 460          # title lives here; captions are ~y1280+
    font, lines, lh = _fit_title(draw, title, W - 160, max_h)
    block_h = lh * len(lines)
    start_y = top + (max_h - block_h) // 2

    # scrim sized to the actual text block
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    sd.rectangle([80, start_y - 90, W - 80, start_y + block_h + 40],
                 fill=(0, 0, 0, 120))
    scrim = scrim.filter(ImageFilter.GaussianBlur(50))
    img.alpha_composite(scrim)

    tag_font = ImageFont.truetype(FONT_BOLD, 26)
    draw.text((W // 2, start_y - 70), " ".join("neuronoverload".upper()),
              font=tag_font, fill=(150, 200, 255), anchor="ma")

    y = start_y
    for ln in lines:
        draw.text((W // 2, y), ln, font=font, fill=(255, 255, 255),
                  anchor="ma", stroke_width=3, stroke_fill=(0, 0, 0))
        y += lh
    img.save(path)


def _build_background(clips, dur, work_dir):
    """Concatenate stock clips into one 1080x1920 background of length `dur`,
    with SMOOTH Ken Burns motion (per-frame zoompan + supersampling)."""
    fps = 30
    per = max(dur / len(clips), 2.0)
    T = max(int(per * fps), 2)   # total frames per clip
    SS = 2                        # supersample factor kills zoompan jitter

    # motion presets using on/T in [0,1]; z is gentle for a calm, smooth move
    presets = [
        # zoom in, centered
        ("1+0.16*on/{T}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        # slight zoom, pan right
        ("1.12", "(iw-iw/zoom)*(on/{T})", "ih/2-(ih/zoom/2)"),
        # zoom out, centered
        ("1.16-0.16*on/{T}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        # slight zoom, pan left
        ("1.12", "(iw-iw/zoom)*(1-on/{T})", "ih/2-(ih/zoom/2)"),
        # slight zoom, tilt up
        ("1.12", "iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-on/{T})"),
    ]

    inputs, filts, labels = [], [], []
    for i, clip in enumerate(clips):
        inputs += ["-i", clip]
        z, xexpr, yexpr = presets[i % len(presets)]
        z = z.replace("{T}", str(T))
        xexpr = xexpr.replace("{T}", str(T))
        yexpr = yexpr.replace("{T}", str(T))
        filts.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={fps},trim=0:{per:.2f},setpts=PTS-STARTPTS,"
            f"scale={W*SS}:{H*SS},"                       # supersample
            f"zoompan=z='{z}':x='{xexpr}':y='{yexpr}':d=1:s={W}x{H}:fps={fps}[v{i}]"
        )
        labels.append(f"[v{i}]")
    concat = "".join(labels) + f"concat=n={len(clips)}:v=1:a=0[cat]"
    tail = "[cat]tpad=stop_mode=clone:stop_duration=6[bg]"
    filt = ";".join(filts + [concat, tail])

    sub = os.path.join(work_dir, "_work")
    os.makedirs(sub, exist_ok=True)
    out = os.path.join(sub, "bg.mp4")
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filt,
           "-map", "[bg]", "-t", f"{dur:.2f}", "-r", str(fps),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
           "-pix_fmt", "yuv420p", out]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


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
                music_path: str = None, bg_clips: list = None,
                word_timings: list = None) -> str:
    """Assemble a real, watchable vertical short.

    word_timings (optional): list of (word, start, end) → karaoke captions.
    Falls back to block captions when not provided.
    """
    os.makedirs(output_dir, exist_ok=True)
    dur = _audio_duration(voiceover_path)
    fps = 30

    if music_path is None:
        music_path = _pick_music(os.path.dirname(os.path.abspath(__file__)))

    use_footage = bool(bg_clips)

    # --- base visual -------------------------------------------------------
    if use_footage:
        try:
            bg_path = _build_background(bg_clips, dur, output_dir)
            base_inputs = ["-i", bg_path]
            base_filter = "[0:v]setsar=1[bg]"
        except Exception as e:
            print(f"⚠️ Stock background failed ({e}) — using gradient")
            use_footage = False

    if not use_footage:
        base_path = os.path.join(output_dir, f"_base_{video_id}.png")
        _title_frame(title).save(base_path)
        base_inputs = ["-loop", "1", "-i", base_path]
        base_filter = (f"[0:v]scale={W}:{H},zoompan=z='min(zoom+0.0006,1.10)':"
                       f"d={int(dur*fps)}:s={W}x{H}:fps={fps}[bg]")

    # --- karaoke caption track (preferred) ---------------------------------
    caps_video = None
    if word_timings:
        if len(word_timings) > 600:
            print(f"⚠️ {len(word_timings)} words > cap; using block captions")
        else:
            try:
                caps_video = _karaoke_track(word_timings, dur, output_dir)
            except Exception as e:
                print(f"⚠️ Karaoke captions failed ({e}) — using block captions")
                caps_video = None
    else:
        print("ℹ️ No word timings available — using block captions")

    # --- PNG overlays: title over footage, + block captions if no karaoke --
    overlays = []  # (png_path, start, end)
    if use_footage:
        title_png = os.path.join(output_dir, f"_title_{video_id}.png")
        _title_overlay_png(title, title_png)
        overlays.append((title_png, 0.0, min(3.6, dur)))

    if caps_video is None:
        chunks = _clean_script(script) or [title]
        per = max(dur / len(chunks), 1.2)
        cap_dir = os.path.join(output_dir, f"_caps_{video_id}")
        os.makedirs(cap_dir, exist_ok=True)
        for i, ch in enumerate(chunks):
            p = os.path.join(cap_dir, f"cap_{i:03d}.png")
            _caption_png(ch, p)
            overlays.append((p, i * per, min((i + 1) * per, dur) - 0.08))

    # --- assemble ffmpeg inputs -------------------------------------------
    inputs = list(base_inputs)
    for p, _, _ in overlays:
        inputs += ["-i", p]
    caps_idx = None
    if caps_video:
        caps_idx = len(overlays) + 1
        inputs += ["-i", caps_video]
    voice_idx = len(overlays) + (1 if caps_video else 0) + 1
    inputs += ["-i", voiceover_path]
    music_idx = None
    if music_path and os.path.exists(music_path):
        music_idx = voice_idx + 1
        inputs += ["-stream_loop", "-1", "-i", music_path]

    # video filter chain: PNG overlays (timed) then karaoke video (full length)
    filt = base_filter
    last = "bg"
    for idx, (_, start, end) in enumerate(overlays, start=1):
        nxt = f"v{idx}"
        filt += (f";[{last}][{idx}:v]overlay=0:0:"
                 f"enable='between(t,{start:.2f},{end:.2f})'[{nxt}]")
        last = nxt
    if caps_idx:
        filt += f";[{last}][{caps_idx}:v]overlay=0:0[vk]"
        last = "vk"

    # audio: voice full, music ducked underneath
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
