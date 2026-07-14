#!/usr/bin/env python3
"""
The brain: long-term memory + topic selection + self-reflection.

  data/playbook.md   — the channel's accumulated strategy. Grows over time.
                       Fed into EVERY script prompt. This is the memory.
  data/insights.json — structured record of what was learned and when.

  ACTION=reflect   -> analyse all results, update the playbook
  ACTION=show      -> print the current playbook

Guardrails (deliberate):
  - Claude must state sample size (n=) for every claim.
  - With n < 5 for a pattern it must say "unproven", not assert it.
  - Every playbook change is committed to git -> full history, revertible.
  - Every change is announced on Telegram so nothing happens silently.
"""

import os
import re
import json
from datetime import datetime, timezone

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYBOOK = os.path.join(SCRIPT_DIR, "data", "playbook.md")
INSIGHTS = os.path.join(SCRIPT_DIR, "data", "insights.json")
VIDEOS = os.path.join(SCRIPT_DIR, "data", "videos.json")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MODEL = "claude-sonnet-4-5"
PLAYBOOK_MAX_CHARS = 6000   # keep it focused; force pruning of stale lessons

SEED_PLAYBOOK = """# NeuronOverload — Channel Playbook

*Living strategy document. Updated by the weekly reflection.
Everything here is fed into every script prompt.*

## Status
- Videos published: 0
- Confidence: NONE — no data yet. Everything below is a starting hypothesis,
  not a proven rule.

## What we believe works (unproven starting assumptions)
- The first 2 seconds decide everything. Open with the most surprising fact,
  never with context or setup.
- Concrete numbers beat adjectives ("1200 people" > "many people").
- Short sentences. Fast pace. No dramatic pauses.
- One idea per video. No lists, no "there are 5 reasons".

## What we avoid
- Topics with no global relevance (local US politics rarely travels).
- Tragedy framed as entertainment. Stay factual and respectful — it is also
  a channel-strike risk.
- Headlines copied verbatim as titles.

## Open questions to test
- Do curiosity-gap hooks ("Nobody noticed this...") beat fact hooks?
- Do science/tech topics outperform news topics?
- Does the publish hour matter at all, or is it noise?

## Lessons learned (with evidence)
*(empty — nothing proven yet)*
"""


def alert(msg, emoji="🧠"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"{emoji} {msg}"[:4000],
                  "disable_web_page_preview": True},
            timeout=10)
    except Exception as e:
        print(f"⚠️ telegram: {e}")


def _client():
    from anthropic import Anthropic
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _text(resp):
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def load_playbook() -> str:
    if os.path.exists(PLAYBOOK):
        try:
            with open(PLAYBOOK) as f:
                return f.read()
        except Exception:
            pass
    return SEED_PLAYBOOK


def save_playbook(text: str):
    os.makedirs(os.path.dirname(PLAYBOOK), exist_ok=True)
    with open(PLAYBOOK, "w") as f:
        f.write(text)


def load_videos():
    if not os.path.exists(VIDEOS):
        return []
    try:
        with open(VIDEOS) as f:
            return json.load(f)
    except Exception:
        return []


# ------------------------------------------------------ topic selection ----

def propose_evergreen(n=4):
    """Let Claude invent evergreen candidates (science / tech / weird facts).

    These compete with the news headlines — so the brain can decide that today
    a mind-blowing science fact beats yet another politics story.
    """
    try:
        prompt = f"""Propose {n} video ideas for a viral YouTube Shorts channel.

CHANNEL PLAYBOOK (what works here so far):
{load_playbook()}

Rules:
- These are EVERGREEN ideas, not news: mind-blowing science, technology,
  space, psychology, history, "weird facts nobody knows".
- Each must have a genuinely surprising core fact — something that makes
  someone stop scrolling. No generic "top 5" listicles.
- Must be TRUE and verifiable. No made-up statistics.
- Must be visual (there has to be stock footage that fits).

Return ONLY JSON:
{{"ideas": [
  {{"title": "<punchy title, max 70 chars>",
    "description": "<the surprising core fact, 1-2 sentences>",
    "category": "science|tech|space|psychology|history|weird"}}
]}}"""
        resp = _client().messages.create(
            model=MODEL, max_tokens=900,
            messages=[{"role": "user", "content": prompt}])
        raw = re.sub(r"```(?:json)?|```", "", _text(resp)).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)

        out = []
        for idea in data.get("ideas", [])[:n]:
            if not idea.get("title"):
                continue
            out.append({
                "title": idea["title"],
                "description": idea.get("description", ""),
                "source": f"evergreen/{idea.get('category', 'general')}",
                "kind": "evergreen",
            })
        print(f"🧠 {len(out)} Evergreen-Ideen vorgeschlagen")
        return out
    except Exception as e:
        print(f"⚠️ Evergreen-Ideen fehlgeschlagen: {e}")
        return []


def select_topics(headlines, want=2):
    """Pick today's topics from news AND evergreen ideas, guided by the playbook.

    The brain decides the mix: it may pick two news items, two evergreen ideas,
    or one of each — whatever it thinks works best today.
    """
    candidates = list(headlines) + propose_evergreen(4)
    if len(candidates) <= want:
        return candidates
    try:
        listing = "\n".join(
            f"{i}. [{c.get('kind', 'news')}] {c['title']} "
            f"({c.get('source', '')})\n   {c.get('description', '')[:120]}"
            for i, c in enumerate(candidates)
        )
        prompt = f"""Pick the {want} ideas with the best chance of going viral
as YouTube Shorts TODAY. You are free to choose any mix.

CHANNEL PLAYBOOK (what we have learned so far):
{load_playbook()}

CANDIDATES (news headlines and evergreen ideas):
{listing}

How to judge:
- Would a random person stop scrolling for this? That is the only real test.
- Global relevance beats local. US-only politics rarely travels.
- Surprise beats importance. A weird fact can outperform major news.
- Visual potential: is there footage that fits?
- Evergreen ideas keep working for months; news dies in a day. Weigh that.
- Follow what the playbook says works, avoid what it says to avoid.
- Do NOT default to news just because it is there. If today's headlines are
  weak or too local, pick evergreen ideas instead.

Return ONLY JSON:
{{"picks": [<index>, <index>], "why": "<one sentence per pick>"}}"""

        resp = _client().messages.create(
            model=MODEL, max_tokens=400,
            messages=[{"role": "user", "content": prompt}])
        raw = re.sub(r"```(?:json)?|```", "", _text(resp)).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)

        picks = [candidates[i] for i in data.get("picks", [])
                 if isinstance(i, int) and 0 <= i < len(candidates)]
        if picks:
            print(f"🧠 Themenwahl: {data.get('why', '')}")
            for p in picks:
                print(f"   → [{p.get('kind', 'news')}] {p['title']}")
            return picks[:want]
    except Exception as e:
        print(f"⚠️ Themenwahl fehlgeschlagen ({e}) — nehme die ersten {want}")
    return candidates[:want]


# ---------------------------------------------------------- reflection ----

def _performance_table(videos):
    rows = []
    for v in videos:
        if v.get("upload_status") != "public" or v.get("views") is None:
            continue
        rows.append({
            "title": (v.get("youtube_title") or v.get("title") or "")[:70],
            "topic_source": v.get("source", ""),
            "views": v.get("views", 0),
            "likes": v.get("likes", 0),
            "avg_view_pct": v.get("avg_view_pct"),   # None if not available
            "published_at": v.get("published_at", ""),
            "hook": (v.get("script_preview") or "")[:90],
        })
    rows.sort(key=lambda r: r["views"], reverse=True)
    return rows


def reflect():
    """Analyse everything, rewrite the playbook, announce what changed."""
    videos = load_videos()
    perf = _performance_table(videos)
    n = len(perf)

    if n == 0:
        msg = "Noch keine veröffentlichten Videos mit Zahlen — nichts zu lernen."
        print(msg)
        alert(msg)
        return

    prompt = f"""You are the strategist for a faceless YouTube Shorts channel.
Rewrite the channel playbook based on REAL results.

CURRENT PLAYBOOK:
{load_playbook()}

REAL PERFORMANCE DATA (n={n} published videos):
{json.dumps(perf, indent=1)}

HARD RULES — violating these makes the playbook worse, not better:
- State the sample size for every claim, e.g. "(n=3, unproven)".
- With fewer than 5 examples supporting a pattern, you MUST label it
  "unproven hypothesis", never a rule.
- View counts on Shorts are dominated by algorithmic luck. Do NOT invent
  causal stories for single outliers. One video with many views proves nothing.
- If the data shows nothing conclusive, SAY SO and keep the playbook mostly
  unchanged. A playbook that admits ignorance is more useful than a confident
  wrong one.
- Keep it under {PLAYBOOK_MAX_CHARS} characters. Delete lessons that were
  disproven or are no longer relevant.
- You may evolve the content direction (topics, hooks, style) if the data
  or reasoning supports it.

Return ONLY the new playbook in markdown. Keep these sections:
Status / What we believe works / What we avoid / Open questions to test /
Lessons learned (with evidence)."""

    try:
        resp = _client().messages.create(
            model=MODEL, max_tokens=2500,
            messages=[{"role": "user", "content": prompt}])
        new_pb = _text(resp).strip()
        new_pb = re.sub(r"^```(?:markdown)?|```$", "", new_pb).strip()
    except Exception as e:
        print(f"❌ Reflexion fehlgeschlagen: {e}")
        alert(f"Reflexion fehlgeschlagen: {e}", "❌")
        return

    if len(new_pb) < 200:
        print("⚠️ Antwort zu kurz — Playbook bleibt unverändert")
        return
    if len(new_pb) > PLAYBOOK_MAX_CHARS * 1.5:
        new_pb = new_pb[:PLAYBOOK_MAX_CHARS]

    old_pb = load_playbook()
    if new_pb.strip() == old_pb.strip():
        print("ℹ️ Keine Änderung nötig")
        alert(f"Wöchentliche Reflexion (n={n}): keine Änderung nötig.")
        return

    save_playbook(new_pb)

    # structured record of the change
    entries = []
    if os.path.exists(INSIGHTS):
        try:
            with open(INSIGHTS) as f:
                entries = json.load(f)
        except Exception:
            entries = []
    entries.append({
        "at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "videos_analysed": n,
        "playbook_chars": len(new_pb),
    })
    with open(INSIGHTS, "w") as f:
        json.dump(entries[-50:], f, indent=2)

    # tell the human what the brain concluded
    summary = new_pb
    m = re.search(r"##\s*Lessons learned.*", new_pb, re.S)
    if m:
        summary = m.group(0)
    alert(f"Playbook aktualisiert (n={n} Videos ausgewertet).\n\n"
          f"{summary[:1200]}\n\n"
          f"Vollständig: data/playbook.md im Repo (git history = rollback)")
    print(f"✅ Playbook aktualisiert ({len(new_pb)} Zeichen, n={n})")


if __name__ == "__main__":
    action = (os.getenv("ACTION") or "reflect").strip().lower()
    if action == "reflect":
        reflect()
    elif action == "show":
        print(load_playbook())
    elif action == "seed":
        if not os.path.exists(PLAYBOOK):
            save_playbook(SEED_PLAYBOOK)
            print("✅ Playbook angelegt")
        else:
            print("ℹ️ Playbook existiert bereits")
    else:
        raise SystemExit(f"unknown ACTION: {action!r}")
