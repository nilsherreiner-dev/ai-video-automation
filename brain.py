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
from datetime import datetime, timedelta, timezone

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

## Channel identity — THE NICHE
This channel is about **science, discovery, invention and technology**.
Mind-blowing findings, breakthroughs, how things actually work, weird
scientific facts, engineering feats, space, the human brain, the future.

A viewer should learn something that makes them go "wait, WHAT?".

## Status
- Videos published: 0
- Confidence: NONE — no data yet. Everything below is a starting hypothesis,
  not a proven rule.

## What we believe works (unproven starting assumptions)
- The first 2 seconds decide everything. Open with the most surprising fact,
  never with context or setup.
- Concrete numbers beat adjectives ("1200 times stronger" > "much stronger").
- Short sentences. Fast pace. No dramatic pauses.
- One idea per video. No lists, no "there are 5 reasons".
- Science travels globally. That is the whole point of this niche.

## What we avoid
- **Politics, elections, politicians.** Not our channel.
- **Local news** with no global relevance (a US senator means nothing abroad).
- **Sports, celebrities, entertainment gossip.**
- Tragedy as clickbait. We can cover a disaster if there is a real scientific
  angle (why the bridge failed, how the fire spread so fast) — but the video
  must explain and inform, never sensationalise the suffering.
- Made-up or unverifiable "facts". Everything must be true.
- Headlines copied verbatim as titles.

## Topic sources, in order of preference
1. Evergreen science/tech/invention ideas (they keep working for months)
2. Science and technology news (breakthroughs, discoveries, launches)
3. Other news ONLY if there is a genuine scientific or technological angle

## Open questions to test
- Do "how it works" explainers beat "surprising fact" videos?
- Space vs. biology vs. technology — which pulls hardest?
- Does the publish hour matter at all, or is it noise?

## Prediction calibration
*(no scored predictions yet)*

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

def predict_performance(video, videos_history):
    """Predict views BEFORE publishing, so the brain can be scored later.

    This is the only honest way to know whether it is actually learning:
    a prediction that can be wrong, checked against reality.
    """
    try:
        past = [
            {"title": (v.get("youtube_title") or v.get("title") or "")[:60],
             "kind": v.get("kind", "news"),
             "views": v.get("views"),
             "predicted": (v.get("prediction") or {}).get("views")}
            for v in videos_history
            if v.get("upload_status") == "public" and v.get("views") is not None
        ][-25:]

        prompt = f"""Predict how this Short will perform. Be honest, not optimistic.

CHANNEL PLAYBOOK:
{load_playbook()}

VIDEO:
title: {video.get('youtube_title') or video.get('title')}
kind: {video.get('kind', 'news')}
hook: {(video.get('script_preview') or '')[:150]}

PAST VIDEOS — your earlier predictions vs. what actually happened:
{json.dumps(past, indent=1) if past else "NONE — you have never been scored yet."}

If your past predictions were consistently too high or too low, CORRECT for that
now. That is the whole point of this exercise.

Return ONLY JSON:
{{"views": <integer, your best guess for views after 7 days>,
  "reasoning": "<one sentence>",
  "confidence": "low|medium|high",
  "biggest_risk": "<what could make this flop, one short phrase>"}}"""

        resp = _client().messages.create(
            model=MODEL, max_tokens=300,
            messages=[{"role": "user", "content": prompt}])
        raw = re.sub(r"```(?:json)?|```", "", _text(resp)).strip()
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0) if m else raw)

        return {
            "views": int(data.get("views", 0)),
            "reasoning": str(data.get("reasoning", ""))[:200],
            "confidence": str(data.get("confidence", "low")),
            "biggest_risk": str(data.get("biggest_risk", ""))[:120],
            "made_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        }
    except Exception as e:
        print(f"⚠️ Prognose fehlgeschlagen: {e}")
        return None


def calibration_report(videos):
    """How wrong were the predictions? Feeds back into the next reflection."""
    scored = []
    for v in videos:
        pred = (v.get("prediction") or {}).get("views")
        actual = v.get("views")
        if pred is None or actual is None or v.get("upload_status") != "public":
            continue
        pub = v.get("published_at")
        if pub:
            try:
                age = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(pub.replace("Z", "+00:00")))
                if age.total_seconds() < 48 * 3600:
                    continue     # too early to judge
            except Exception:
                pass
        scored.append({
            "title": (v.get("youtube_title") or v.get("title") or "")[:50],
            "predicted": pred,
            "actual": actual,
            "ratio": round(actual / pred, 2) if pred > 0 else None,
        })
    if not scored:
        return None
    ratios = [s["ratio"] for s in scored if s["ratio"]]
    avg = round(sum(ratios) / len(ratios), 2) if ratios else None
    return {"n": len(scored), "avg_actual_over_predicted": avg, "detail": scored[-10:]}


def already_covered(title, videos, days=21):
    """Avoid re-doing a topic we recently covered."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    words = {w.lower() for w in re.findall(r"\w{5,}", title)}
    if not words:
        return False
    for v in videos:
        try:
            when = datetime.fromisoformat(
                (v.get("created_at") or "").replace("Z", "+00:00"))
            if when < cutoff:
                continue
        except Exception:
            continue
        prev = {w.lower() for w in re.findall(r"\w{5,}", v.get("title") or "")}
        if prev and len(words & prev) / len(words) > 0.55:
            return True
    return False


def propose_evergreen(n=6):
    """Generate evergreen science/invention ideas — the backbone of the channel.

    These are the primary source now: news is only used when it has a real
    scientific angle. Evergreen ideas also keep working for months.
    """
    try:
        recent = [v.get("title", "") for v in load_videos()][-25:]
        prompt = f"""Propose {n} video ideas for a SCIENCE & INVENTION YouTube Shorts channel.

CHANNEL PLAYBOOK (the niche and what works here):
{load_playbook()}

ALREADY COVERED — do not repeat these or anything close to them:
{json.dumps(recent, indent=1) if recent else "nothing yet"}

Rules:
- Domains: physics, biology, space, neuroscience, engineering, materials,
  medicine, computing, inventions, weird-but-true scientific facts, how things
  actually work, historical breakthroughs.
- Each needs ONE genuinely surprising core fact — the kind that makes someone
  stop scrolling and say "wait, WHAT?".
- Must be TRUE and verifiable. No invented statistics, no pop-science myths
  (no "we only use 10% of our brain" nonsense).
- Must be visual: there has to be stock footage that plausibly fits.
- Prefer the counterintuitive over the merely impressive.
- No listicles. One idea per video.

Return ONLY JSON:
{{"ideas": [
  {{"title": "<punchy title, max 70 chars>",
    "description": "<the surprising core fact, 1-2 sentences>",
    "category": "physics|biology|space|neuro|engineering|medicine|computing|invention|history"}}
]}}"""
        resp = _client().messages.create(
            model=MODEL, max_tokens=1400,
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
                "source": f"evergreen/{idea.get('category', 'science')}",
                "kind": "evergreen",
            })
        print(f"🧠 {len(out)} Wissenschafts-Ideen vorgeschlagen")
        return out
    except Exception as e:
        print(f"⚠️ Evergreen-Ideen fehlgeschlagen: {e}")
        return []


def select_topics(headlines, want=2):
    """Pick today's topics from news AND evergreen ideas, guided by the playbook.

    The brain decides the mix: it may pick two news items, two evergreen ideas,
    or one of each — whatever it thinks works best today.
    """
    candidates = list(headlines) + propose_evergreen(6)

    # never repeat a topic we covered in the last three weeks
    history = load_videos()
    fresh = [c for c in candidates if not already_covered(c["title"], history)]
    if len(fresh) >= want:
        dropped = len(candidates) - len(fresh)
        if dropped:
            print(f"🧠 {dropped} Thema/Themen übersprungen (kürzlich behandelt)")
        candidates = fresh

    if len(candidates) <= want:
        return candidates
    try:
        listing = "\n".join(
            f"{i}. [{c.get('kind', 'news')}] {c['title']} "
            f"({c.get('source', '')})\n   {c.get('description', '')[:120]}"
            for i, c in enumerate(candidates)
        )
        prompt = f"""Pick the {want} ideas with the best chance of going viral
as YouTube Shorts TODAY for THIS channel.

CHANNEL PLAYBOOK — the niche and everything learned so far:
{load_playbook()}

CANDIDATES (news headlines and evergreen ideas):
{listing}

THE NICHE IS THE FILTER — apply it first:
- This is a SCIENCE / DISCOVERY / INVENTION / TECHNOLOGY channel.
- Reject politics, elections, sports, celebrities, local crime — no matter how
  big the headline. They are off-brand and they do not travel internationally.
- A news story qualifies ONLY if it has a real scientific or technological
  core (a breakthrough, a discovery, how something works, why something failed).
- If today's headlines are all off-niche, pick evergreen science ideas instead.
  An off-brand video is worse than a "boring" on-brand one — it confuses the
  algorithm about who to show this channel to.

RESPONSIBILITY:
- A disaster or accident can be covered ONLY from the "how/why did this happen"
  angle, and must inform rather than exploit the suffering. If you cannot do
  that respectfully, skip it.
- Everything must be factually true. No invented statistics.

Then judge the survivors by:
- Would a random person stop scrolling? Surprise is the only real test.
- Does it make the viewer feel smarter afterwards?
- Visual potential: is there stock footage that fits?
- Evergreen ideas keep working for months; news dies in a day. Weigh that.

Return ONLY JSON:
{{"picks": [<index>, ...], "why": "<one sentence per pick>"}}"""

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

    calib = calibration_report(videos)
    calib_txt = (json.dumps(calib, indent=1) if calib
                 else "NO SCORED PREDICTIONS YET")

    prompt = f"""You are the strategist for a faceless YouTube Shorts channel.
Rewrite the channel playbook based on REAL results.

CURRENT PLAYBOOK:
{load_playbook()}

REAL PERFORMANCE DATA (n={n} published videos):
{json.dumps(perf, indent=1)}

YOUR OWN PREDICTION ACCURACY (this is your report card):
{calib_txt}
If avg_actual_over_predicted is far below 1.0 you have been over-optimistic.
Far above 1.0 means you underestimate. Say so plainly and correct for it.

HARD RULES — violating these makes the playbook worse, not better:
- State the sample size for every claim, e.g. "(n=3, unproven)".
- With fewer than 5 examples supporting a pattern, you MUST label it
  "unproven hypothesis", never a rule.
- View counts on Shorts are dominated by algorithmic luck. Do NOT invent
  causal stories for single outliers. One video with many views proves nothing.
- Compare like with like: retention (avg_view_pct) is a far better signal of
  script quality than views, because it is less algorithm-dependent. If you
  have retention data, weight it heavily.
- If the data shows nothing conclusive, SAY SO and keep the playbook mostly
  unchanged. A playbook that admits ignorance is more useful than a confident
  wrong one.
- Keep it under {PLAYBOOK_MAX_CHARS} characters. Delete lessons that were
  disproven.
- You may evolve the content direction (topics, hooks, style) if the data
  supports it. Also note which topic KIND (news vs evergreen) performs better.

Return ONLY the new playbook in markdown, with these sections:
Status / What we believe works / What we avoid / Open questions to test /
Prediction calibration / Lessons learned (with evidence)."""

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
