#!/usr/bin/env python3
"""
Dashboard actions: publish an unlisted video, or remove entries from the log.

Called by the manage.yml workflow (triggered from the dashboard).

  ACTION=publish  YOUTUBE_ID=abc123   -> set that video to public on YouTube
  ACTION=delete   RUN_ID=...  SLOT=2  -> remove that entry from data/videos.json
  ACTION=cleanup                      -> drop all entries that were never uploaded
"""

import os
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "data", "videos.json")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def alert(msg, emoji="📊"):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"{emoji} {msg}"},
            timeout=5)
    except Exception:
        pass


def load():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save(videos):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(videos, f, indent=2)


def credentials():
    """Authorized credentials (also used by the analytics client)."""
    raw = os.getenv("GOOGLE_AUTH_JSON")
    if not raw:
        raise RuntimeError("GOOGLE_AUTH_JSON not set")
    creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise RuntimeError("token JSON has no refresh_token")
        creds.refresh(Request())
    return creds


def youtube_service():
    return build("youtube", "v3", credentials=credentials())


def publish(youtube_id: str):
    """Flip an unlisted video to public."""
    yt = youtube_service()

    # need the current snippet: videos.update replaces the whole part
    resp = yt.videos().list(part="snippet,status", id=youtube_id).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"video {youtube_id} not found")
    snippet = items[0]["snippet"]

    yt.videos().update(
        part="status,snippet",
        body={
            "id": youtube_id,
            "snippet": {
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "categoryId": snippet.get("categoryId", "28"),
                "tags": snippet.get("tags", []),
            },
            "status": {
                "privacyStatus": "public",
                "madeForKids": False,
                "selfDeclaredMadeForKids": False,
            },
        },
    ).execute()

    videos = load()
    for v in videos:
        if v.get("youtube_id") == youtube_id:
            v["upload_status"] = "public"
    save(videos)

    url = f"https://www.youtube.com/watch?v={youtube_id}"
    print(f"✅ Published: {url}")
    alert(f"Video ist jetzt öffentlich\n{url}", "🚀")


def delete_entry(run_id: str, slot: str):
    """Remove one entry from the dashboard log (does NOT touch YouTube)."""
    videos = load()
    before = len(videos)
    videos = [v for v in videos
              if not (str(v.get("run_id")) == str(run_id)
                      and str(v.get("slot")) == str(slot))]
    save(videos)
    print(f"✅ Removed {before - len(videos)} entry/entries")


def cleanup():
    """Drop every entry that never made it to YouTube."""
    videos = load()
    before = len(videos)
    videos = [v for v in videos if v.get("youtube_id")]
    save(videos)
    print(f"✅ Cleanup: removed {before - len(videos)} un-uploaded entries")


if __name__ == "__main__":
    action = (os.getenv("ACTION") or "").strip().lower()
    yid = (os.getenv("YOUTUBE_ID") or "").strip()

    if action == "publish":
        if not yid:
            raise SystemExit("YOUTUBE_ID missing")
        publish(yid)

    elif action == "schedule":
        if not yid:
            raise SystemExit("YOUTUBE_ID missing")
        import scheduler
        scheduler.schedule_video(yid)

    elif action == "reject":
        if not yid:
            raise SystemExit("YOUTUBE_ID missing")
        try:
            youtube_service().videos().delete(id=yid).execute()
        except Exception as e:
            print(f"⚠️ YouTube delete: {e}")
        save([v for v in load() if v.get("youtube_id") != yid])
        print(f"🗑️ rejected {yid}")

    elif action == "delete":
        delete_entry(os.getenv("RUN_ID", ""), os.getenv("SLOT", ""))

    elif action == "cleanup":
        cleanup()

    elif action in ("sync", "prune"):
        import telegram_bot as tb
        print(tb.do_sync() if action == "sync" else tb.do_prune())

    elif action == "reflect":
        import brain
        brain.reflect()

    else:
        raise SystemExit(f"unknown ACTION: {action!r}")
