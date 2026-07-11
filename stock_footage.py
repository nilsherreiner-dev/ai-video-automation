#!/usr/bin/env python3
"""
Footage source — fetches background video clips for a topic.

Current backend: Pexels (free, royalty-free, commercial use with attribution).
Designed as a pluggable seam so AI-video backends (Kling/Veo/etc.) can be
added later behind the same get_background_clips() interface.
"""

import os
import re
import requests

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_SEARCH = "https://api.pexels.com/videos/search"


def _pick_file(video: dict, target_h: int = 1920):
    """Choose the mp4 rendition closest to (but >=) the target height."""
    files = [f for f in video.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("link")]
    if not files:
        return None
    # prefer portrait-ish files at/above target height, else the tallest
    tall = [f for f in files if (f.get("height") or 0) >= target_h * 0.6]
    pool = tall or files
    pool.sort(key=lambda f: abs((f.get("height") or 0) - target_h))
    return pool[0]["link"]


def search_pexels_clips(keywords, out_dir, max_clips=4, min_duration=3):
    """
    Search Pexels for vertical clips matching the keywords and download them.
    Returns (clip_paths, attributions).
    """
    if not PEXELS_API_KEY:
        print("⚠️ No PEXELS_API_KEY set — falling back to gradient background")
        return [], []

    os.makedirs(out_dir, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}
    clips, attributions, seen = [], [], set()

    for kw in keywords:
        if len(clips) >= max_clips:
            break
        try:
            r = requests.get(
                PEXELS_SEARCH,
                headers=headers,
                params={"query": kw, "orientation": "portrait",
                        "per_page": 5, "size": "medium"},
                timeout=15,
            )
            if r.status_code != 200:
                print(f"⚠️ Pexels '{kw}' -> HTTP {r.status_code}")
                continue
            for video in r.json().get("videos", []):
                vid = video.get("id")
                if vid in seen or (video.get("duration") or 0) < min_duration:
                    continue
                link = _pick_file(video)
                if not link:
                    continue
                path = os.path.join(out_dir, f"stock_{vid}.mp4")
                try:
                    data = requests.get(link, timeout=45)
                    if data.status_code == 200 and len(data.content) > 10000:
                        with open(path, "wb") as f:
                            f.write(data.content)
                        clips.append(path)
                        seen.add(vid)
                        author = (video.get("user") or {}).get("name", "Pexels")
                        attributions.append(f"{author} (Pexels)")
                        break  # one clip per keyword for variety
                except Exception as e:
                    print(f"⚠️ download failed: {e}")
        except Exception as e:
            print(f"⚠️ Pexels search failed for '{kw}': {e}")

    print(f"✅ Got {len(clips)} stock clip(s)")
    return clips, attributions


def get_background_clips(topic, keywords, out_dir, source="stock", **kwargs):
    """
    Unified entry point for background footage.

    source="stock"  -> Pexels (implemented)
    source="ai"     -> reserved for Kling/Veo/etc. (future Option 2/3)
    """
    if source == "stock":
        return search_pexels_clips(keywords, out_dir, **kwargs)
    if source == "ai":
        raise NotImplementedError(
            "AI video backend not wired yet — planned for Option 2/3")
    raise ValueError(f"Unknown footage source: {source}")
