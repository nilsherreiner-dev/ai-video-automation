#!/usr/bin/env python3
"""
Footage source with RELEVANCE CHECKING.

The old version took whatever Pexels returned first — which is how a video
about Neptune ended up showing a baseball game. Now:

  1. search several queries and gather many candidates
  2. read each clip's description (Pexels puts it in the URL slug)
  3. let Claude judge which ones actually fit the topic, reject the rest
  4. if too few survive, fall back to safe on-theme queries (space, lab, ...)

Kept as a pluggable seam so AI-video backends can slot in later.
"""

import os
import re
import json
import requests

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PEXELS_SEARCH = "https://api.pexels.com/videos/search"

SAFE_FALLBACKS = {
    "space": ["galaxy stars", "planet space", "nebula"],
    "physics": ["laboratory experiment", "particle light", "energy abstract"],
    "biology": ["microscope cells", "dna helix", "nature macro"],
    "neuro": ["brain scan", "neurons abstract", "mri scan"],
    "engineering": ["machine factory", "robot arm", "construction site"],
    "computing": ["server room", "code screen", "circuit board"],
    "medicine": ["hospital laboratory", "medical research", "scientist working"],
    "history": ["ancient ruins", "old documents", "museum artifact"],
    "default": ["science laboratory", "abstract technology", "research"],
}


def _slug_description(url: str) -> str:
    """Pexels URLs look like /video/aerial-view-of-a-city-12345/ —
    the slug IS the clip description. Free metadata for relevance checking."""
    try:
        m = re.search(r"/video/([a-z0-9\-]+?)-\d+/?$", (url or "").lower())
        if m:
            return m.group(1).replace("-", " ")
    except Exception:
        pass
    return ""


def _pick_file(video: dict, target_h: int = 1920):
    files = [f for f in video.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("link")]
    if not files:
        return None
    tall = [f for f in files if (f.get("height") or 0) >= target_h * 0.6]
    pool = tall or files
    pool.sort(key=lambda f: abs((f.get("height") or 0) - target_h))
    return pool[0]["link"]


def _search(query: str, per_page: int = 6):
    if not PEXELS_API_KEY:
        return []
    try:
        r = requests.get(
            PEXELS_SEARCH,
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "orientation": "portrait",
                    "per_page": per_page, "size": "medium"},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"   ⚠️ Pexels '{query}' -> HTTP {r.status_code}")
            return []
        out = []
        for v in r.json().get("videos", []):
            if (v.get("duration") or 0) < 3:
                continue
            link = _pick_file(v)
            if not link:
                continue
            out.append({
                "id": v.get("id"),
                "link": link,
                "desc": _slug_description(v.get("url", "")) or query,
                "author": (v.get("user") or {}).get("name", "Pexels"),
                "query": query,
            })
        return out
    except Exception as e:
        print(f"   ⚠️ Pexels '{query}' failed: {e}")
        return []


def _judge_relevance(topic: str, candidates, want: int):
    """Ask Claude which clips actually match. Rejecting is encouraged."""
    if not candidates or not ANTHROPIC_API_KEY:
        return candidates[:want]
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        listing = "\n".join(f"{i}. {c['desc']}" for i, c in enumerate(candidates))
        prompt = f"""Pick the background clips that actually FIT this video topic.

VIDEO TOPIC: {topic}

AVAILABLE STOCK CLIPS (descriptions):
{listing}

Rules:
- Pick up to {want} clips a viewer would accept as fitting the topic.
- A loose thematic match is fine (space topic -> stars, planets, telescope).
- An UNRELATED clip is worse than no clip. A video about Neptune must never
  show a baseball game. When in doubt, REJECT.
- Prefer variety: avoid {want} near-identical clips.
- If nothing fits, return an empty list. That is a valid answer.

Return ONLY JSON: {{"picks": [<index>, ...], "why": "<short reason>"}}"""

        resp = client.messages.create(
            model="claude-sonnet-4-5", max_tokens=250,
            messages=[{"role": "user", "content": prompt}])
        text = ""
        for b in resp.content:
            if getattr(b, "type", None) == "text":
                text = b.text
                break
        raw = re.sub(r"```(?:json)?|```", "", text).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)

        picks = [candidates[i] for i in data.get("picks", [])
                 if isinstance(i, int) and 0 <= i < len(candidates)]
        rejected = len(candidates) - len(picks)
        if rejected:
            print(f"   🚫 {rejected} unpassende Clips verworfen ({data.get('why', '')})")
        return picks[:want]
    except Exception as e:
        print(f"   ⚠️ Relevanzprüfung fehlgeschlagen ({e})")
        return candidates[:want]


def _download(cands, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    paths, credits = [], []
    for c in cands:
        path = os.path.join(out_dir, f"stock_{c['id']}.mp4")
        try:
            data = requests.get(c["link"], timeout=45)
            if data.status_code == 200 and len(data.content) > 10000:
                with open(path, "wb") as f:
                    f.write(data.content)
                paths.append(path)
                credits.append(f"{c['author']} (Pexels)")
        except Exception as e:
            print(f"   ⚠️ Download fehlgeschlagen: {e}")
    return paths, credits


def search_pexels_clips(topic, keywords, out_dir, max_clips=3, category="default"):
    if not PEXELS_API_KEY:
        print("   ⚠️ Kein PEXELS_API_KEY — Gradient-Hintergrund")
        return [], []

    seen, candidates = set(), []
    for kw in keywords:
        for c in _search(kw):
            if c["id"] not in seen:
                seen.add(c["id"])
                candidates.append(c)

    picked = _judge_relevance(topic, candidates, max_clips)

    if len(picked) < max_clips:
        fallbacks = SAFE_FALLBACKS.get(category, SAFE_FALLBACKS["default"])
        print(f"   ↩️ Nur {len(picked)} passende Clips — ergänze mit {fallbacks}")
        extra = []
        for kw in fallbacks:
            for c in _search(kw, per_page=3):
                if c["id"] not in seen:
                    seen.add(c["id"])
                    extra.append(c)
        picked += extra[: max_clips - len(picked)]

    paths, credits = _download(picked, out_dir)
    print(f"   ✅ {len(paths)} Hintergrund-Clip(s)")
    return paths, credits


def get_background_clips(topic, keywords, out_dir, source="stock", **kwargs):
    """Unified entry point. source='ai' reserved for future AI-video backends."""
    if source == "stock":
        return search_pexels_clips(topic, keywords, out_dir, **kwargs)
    if source == "ai":
        raise NotImplementedError("AI video backend not wired yet")
    raise ValueError(f"Unknown footage source: {source}")
