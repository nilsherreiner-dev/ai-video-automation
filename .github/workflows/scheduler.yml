#!/usr/bin/env python3
"""
Scheduling + feedback loop.

  ACTION=schedule  YOUTUBE_ID=...   -> ask Claude for the best publish time
  ACTION=publish_due                -> publish everything whose time has come
  ACTION=collect                    -> pull real view counts from YouTube

The feedback loop: every prediction is stored, every published video gets its
view count measured, and past (time -> views) pairs are fed back into the next
prediction. With little history Claude is told to say so instead of pretending.
"""

import os
import re
import json
from datetime import datetime, timedelta, timezone

import requests
import manage_videos as mv

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_DELAY_HOURS = 36   # never schedule further out than this


def alert(msg, emoji="📊"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"{emoji} {msg}",
                  "disable_web_page_preview": True},
            timeout=10)
    except Exception as e:
        print(f"⚠️ telegram: {e}")


def now_utc():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- history ----

def build_history(videos):
    """Past results: when it went live (UTC hour) -> how many views it got."""
    rows = []
    for v in videos:
        if v.get("upload_status") != "public":
            continue
        pub = v.get("published_at")
        views = v.get("views")
        if not pub or views is None:
            continue
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            continue
        age_h = (now_utc() - dt).total_seconds() / 3600
        if age_h < 12:          # too fresh to judge
            continue
        rows.append({
            "topic": (v.get("youtube_title") or v.get("title") or "")[:70],
            "published_hour_utc": dt.hour,
            "weekday": dt.strftime("%a"),
            "hours_live": round(age_h),
            "views": views,
        })
    return rows


# --------------------------------------------------------------- predict ----

def predict_time(video, history):
    """Ask Claude when to publish. Returns (datetime_utc, reasoning, confidence)."""
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    now = now_utc()
    hist_txt = json.dumps(history[-40:], indent=1) if history else "NONE YET"

    prompt = f"""You decide when to publish a YouTube Short. Answer in JSON only.

CURRENT TIME (UTC): {now.isoformat(timespec='minutes')}
VIDEO TOPIC: {video.get('youtube_title') or video.get('title')}
SOURCE TOPIC: {video.get('title')}

PAST RESULTS FROM THIS CHANNEL (publish hour -> views):
{hist_txt}

RULES:
- Choose a publish time between NOW and {MAX_DELAY_HOURS} hours from now.
- Time-sensitive news (breaking events, deaths, war, market moves) loses value
  fast -> publish very soon, even if the hour is not ideal.
- Evergreen/curiosity topics can wait for a high-traffic window.
- The audience is mostly US/EN. Consider their local time, not UTC.
- If PAST RESULTS is NONE YET or has fewer than 8 entries, you are GUESSING.
  Say so honestly in "reasoning" and set confidence to "low".
- Only claim a data-driven pattern if the history actually shows one.

Return ONLY this JSON:
{{"publish_in_hours": <number, 0 to {MAX_DELAY_HOURS}>,
  "reasoning": "<one short sentence>",
  "confidence": "low|medium|high"}}"""

    resp = client.messages.create(
        model="claude-sonnet-4-5", max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text = block.text
            break

    raw = re.sub(r"```(?:json)?|```", "", text).strip()
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0) if m else raw)

    hours = float(data.get("publish_in_hours", 2))
    hours = max(0.0, min(hours, MAX_DELAY_HOURS))
    when = now + timedelta(hours=hours)
    return when, str(data.get("reasoning", ""))[:200], str(data.get("confidence", "low"))


def schedule_video(youtube_id: str):
    videos = mv.load()
    target = next((v for v in videos if v.get("youtube_id") == youtube_id), None)
    if not target:
        alert(f"Video {youtube_id} nicht im Log gefunden", "❌")
        return

    history = build_history(videos)
    try:
        when, why, conf = predict_time(target, history)
    except Exception as e:
        when, why, conf = (now_utc() + timedelta(hours=2),
                           f"Prognose fehlgeschlagen ({e}) — Standard: in 2h", "low")

    target["approved"] = True
    target["scheduled_for"] = when.isoformat(timespec="minutes")
    target["schedule_reason"] = why
    target["schedule_confidence"] = conf
    target["predicted_at"] = now_utc().isoformat(timespec="minutes")
    mv.save(videos)

    local = when + timedelta(hours=2)   # rough CEST for the message
    note = "" if len(history) >= 8 else "\n⚠️ Wenig Verlaufsdaten — das ist noch eine Schätzung."
    alert(f"✅ Freigegeben: {target.get('youtube_title') or target.get('title')}\n\n"
          f"🕐 Geplant: {when.strftime('%d.%m. %H:%M')} UTC "
          f"(~{local.strftime('%H:%M')} DE)\n"
          f"💭 {why}\n"
          f"📊 Konfidenz: {conf}{note}",
          "🗓️")
    print(f"✅ scheduled {youtube_id} for {when.isoformat()} ({conf})")


# ------------------------------------------------------------ publish due ----

def publish_due():
    videos = mv.load()
    now = now_utc()
    due = []
    for v in videos:
        if not v.get("approved") or v.get("upload_status") == "public":
            continue
        ts = v.get("scheduled_for")
        if not ts:
            continue
        try:
            when = datetime.fromisoformat(ts)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if when <= now:
            due.append(v)

    if not due:
        print("ℹ️ Nichts fällig")
        return

    for v in due:
        yid = v["youtube_id"]
        try:
            mv.publish(yid)                     # flips to public + saves log
            fresh = mv.load()
            for e in fresh:
                if e.get("youtube_id") == yid:
                    e["published_at"] = now.isoformat(timespec="minutes")
            mv.save(fresh)
            print(f"🚀 published {yid}")
        except Exception as e:
            print(f"❌ publish {yid} failed: {e}")
            alert(f"Konnte {yid} nicht veröffentlichen: {e}", "❌")


# --------------------------------------------------------------- collect ----

def _fetch_retention(creds, video_ids):
    """Average view percentage per video (the metric that actually matters for
    Shorts). Needs the yt-analytics.readonly scope; degrades silently if absent."""
    if not video_ids:
        return {}
    try:
        from googleapiclient.discovery import build as _build
        ya = _build("youtubeAnalytics", "v2", credentials=creds)
        out = {}
        # the API only accepts a handful of filters at once
        for vid in video_ids[:40]:
            try:
                r = ya.reports().query(
                    ids="channel==MINE",
                    startDate="2020-01-01",
                    endDate=now_utc().strftime("%Y-%m-%d"),
                    metrics="averageViewPercentage,averageViewDuration",
                    filters=f"video=={vid}",
                ).execute()
                rows = r.get("rows") or []
                if rows and rows[0]:
                    out[vid] = {
                        "avg_view_pct": round(float(rows[0][0]), 1),
                        "avg_view_sec": round(float(rows[0][1]), 1),
                    }
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"ℹ️ Retention nicht verfügbar ({e}) — nur Views. "
              f"Dafür bräuchte es den Scope yt-analytics.readonly.")
        return {}


def collect_stats():
    """Pull real view counts so future predictions have ground truth."""
    videos = mv.load()
    live = [v for v in videos if v.get("upload_status") == "public" and v.get("youtube_id")]
    if not live:
        print("ℹ️ Keine öffentlichen Videos")
        return

    yt = mv.youtube_service()
    ids = [v["youtube_id"] for v in live]
    stats = {}
    for i in range(0, len(ids), 50):
        resp = yt.videos().list(part="statistics",
                                id=",".join(ids[i:i + 50])).execute()
        for item in resp.get("items", []):
            s = item.get("statistics", {})
            stats[item["id"]] = {
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            }

    updated = 0
    retention = _fetch_retention(mv.credentials(), ids)
    for v in videos:
        s = stats.get(v.get("youtube_id"))
        if not s:
            continue
        v["views"] = s["views"]
        v["likes"] = s["likes"]
        v["comments"] = s["comments"]
        r = retention.get(v.get("youtube_id"))
        if r:
            v["avg_view_pct"] = r["avg_view_pct"]
            v["avg_view_sec"] = r["avg_view_sec"]
        v["stats_updated"] = now_utc().isoformat(timespec="minutes")
        updated += 1
    mv.save(videos)
    extra = f", davon {len(retention)} mit Retention" if retention else ""
    print(f"✅ Stats für {updated} Video(s) aktualisiert{extra}")


if __name__ == "__main__":
    action = (os.getenv("ACTION") or "").strip().lower()
    if action == "schedule":
        yid = (os.getenv("YOUTUBE_ID") or "").strip()
        if not yid:
            raise SystemExit("YOUTUBE_ID missing")
        schedule_video(yid)
    elif action == "publish_due":
        publish_due()
    elif action == "collect":
        collect_stats()
    else:
        raise SystemExit(f"unknown ACTION: {action!r}")
