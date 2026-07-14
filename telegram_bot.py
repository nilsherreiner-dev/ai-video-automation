#!/usr/bin/env python3
"""
Telegram control bot (polling, runs on a schedule via GitHub Actions).

Reads pending updates, handles the inline buttons sent after each upload:
  publish:<youtube_id>       -> make the unlisted video public
  reject:<youtube_id>        -> delete the video from YouTube + drop the log entry

Also supports typed commands:
  /pending    -> list videos waiting for review
  /publish <youtube_id>
"""

import os
import json
import requests

import manage_videos as mv

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API = f"https://api.telegram.org/bot{TOKEN}"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OFFSET_FILE = os.path.join(SCRIPT_DIR, "data", "tg_offset.json")


def _load_offset() -> int:
    try:
        with open(OFFSET_FILE) as f:
            return int(json.load(f).get("offset", 0))
    except Exception:
        return 0


def _save_offset(offset: int):
    os.makedirs(os.path.dirname(OFFSET_FILE), exist_ok=True)
    with open(OFFSET_FILE, "w") as f:
        json.dump({"offset": offset}, f)


def send(text: str, buttons=None):
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": False}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": buttons}
    try:
        requests.post(f"{API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ send failed: {e}")


def answer_callback(cb_id: str, text: str):
    try:
        requests.post(f"{API}/answerCallbackQuery",
                      json={"callback_query_id": cb_id, "text": text},
                      timeout=10)
    except Exception:
        pass


def handle_publish(youtube_id: str) -> str:
    try:
        mv.publish(youtube_id)
        return f"🚀 Veröffentlicht: https://youtu.be/{youtube_id}"
    except Exception as e:
        return f"❌ Konnte nicht veröffentlichen: {e}"


def handle_reject(youtube_id: str) -> str:
    """Delete the video from YouTube entirely and drop it from the log."""
    try:
        yt = mv.youtube_service()
        yt.videos().delete(id=youtube_id).execute()
        videos = [v for v in mv.load() if v.get("youtube_id") != youtube_id]
        mv.save(videos)
        return f"🗑️ Video gelöscht ({youtube_id})"
    except Exception as e:
        return f"❌ Konnte nicht löschen: {e}"


def do_sync() -> str:
    """Ask YouTube what is really true and fix the dashboard log.

    - entries whose video no longer exists  -> removed
    - entries whose video is public/unlisted -> status corrected
    """
    videos = mv.load()
    with_id = [v for v in videos if v.get("youtube_id")]
    if not with_id:
        return "Nichts zu synchronisieren."

    try:
        yt = mv.youtube_service()
        ids = [v["youtube_id"] for v in with_id]
        privacy = {}
        for i in range(0, len(ids), 50):
            resp = yt.videos().list(part="status",
                                    id=",".join(ids[i:i + 50])).execute()
            for item in resp.get("items", []):
                privacy[item["id"]] = item["status"].get("privacyStatus", "unknown")
    except Exception as e:
        return f"❌ Konnte YouTube nicht abfragen: {e}"

    kept, removed, fixed = [], 0, 0
    for v in videos:
        yid = v.get("youtube_id")
        if not yid:
            kept.append(v)          # never uploaded: /cleanup handles those
            continue
        if yid not in privacy:
            removed += 1            # video no longer on YouTube
            continue
        status = privacy[yid]       # public | unlisted | private
        if v.get("upload_status") != status:
            v["upload_status"] = status
            fixed += 1
        kept.append(v)

    mv.save(kept)

    pub = sum(1 for v in kept if v.get("upload_status") == "public")
    wait = sum(1 for v in kept
               if v.get("youtube_id") and v.get("upload_status") != "public")
    return (f"🔄 Sync fertig.\n"
            f"• {fixed} Status korrigiert\n"
            f"• {removed} gelöschte Videos entfernt\n"
            f"• {pub} öffentlich, {wait} warten auf Freigabe")


def do_cleanup() -> str:
    """Remove log entries that were never uploaded (no YouTube video)."""
    videos = mv.load()
    before = len(videos)
    kept = [v for v in videos if v.get("youtube_id")]
    mv.save(kept)
    removed = before - len(kept)
    return (f"🧹 {removed} Eintrag/Einträge entfernt (nie hochgeladen).\n"
            f"Im Dashboard verbleiben: {len(kept)}")


def do_prune() -> str:
    """Remove entries whose YouTube video no longer exists (deleted by hand)."""
    videos = mv.load()
    with_id = [v for v in videos if v.get("youtube_id")]
    if not with_id:
        return "Nichts zu prüfen."
    try:
        yt = mv.youtube_service()
        ids = [v["youtube_id"] for v in with_id]
        alive = set()
        for i in range(0, len(ids), 50):
            resp = yt.videos().list(part="id", id=",".join(ids[i:i + 50])).execute()
            alive.update(item["id"] for item in resp.get("items", []))
    except Exception as e:
        return f"❌ Konnte YouTube nicht abfragen: {e}"

    kept = [v for v in videos
            if not v.get("youtube_id") or v["youtube_id"] in alive]
    removed = len(videos) - len(kept)
    mv.save(kept)
    return (f"🧹 {removed} Eintrag/Einträge entfernt "
            f"(Video existiert nicht mehr auf YouTube).\n"
            f"Im Dashboard verbleiben: {len(kept)}")


def list_pending() -> str:
    pending = [v for v in mv.load()
               if v.get("youtube_id")
               and v.get("upload_status") not in ("public",)]
    if not pending:
        return "✅ Nichts offen — alles veröffentlicht oder weg."
    lines = [f"⏳ {len(pending)} warten auf Freigabe:"]
    for v in pending:
        lines.append(f"\n• {v.get('youtube_title') or v.get('title')}\n"
                     f"  https://youtu.be/{v['youtube_id']}\n"
                     f"  /publish {v['youtube_id']}")
    lines.append("\n(Tipp: /sync gleicht zuerst mit YouTube ab)")
    return "\n".join(lines)


def main():
    if not TOKEN or not CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing")
        return

    offset = _load_offset()
    try:
        r = requests.get(f"{API}/getUpdates",
                         params={"offset": offset + 1, "timeout": 0},
                         timeout=20)
        updates = r.json().get("result", [])
    except Exception as e:
        print(f"❌ getUpdates failed: {e}")
        return

    if not updates:
        print("ℹ️ Keine neuen Updates")
        return

    max_id = offset
    for upd in updates:
        max_id = max(max_id, upd.get("update_id", 0))

        # --- inline button presses ---
        cb = upd.get("callback_query")
        if cb:
            data = (cb.get("data") or "").strip()
            print(f"→ callback: {data}")
            if data.startswith("publish:"):
                msg = handle_publish(data.split(":", 1)[1])
            elif data.startswith("reject:"):
                msg = handle_reject(data.split(":", 1)[1])
            else:
                msg = f"Unbekannte Aktion: {data}"
            answer_callback(cb.get("id", ""), msg[:190])
            send(msg)
            continue

        # --- typed commands ---
        text = ((upd.get("message") or {}).get("text") or "").strip()
        if not text:
            continue
        print(f"→ message: {text}")
        if text.startswith("/pending"):
            send(list_pending())
        elif text.startswith("/sync"):
            send(do_sync())
        elif text.startswith("/cleanup"):
            send(do_cleanup())
        elif text.startswith("/prune"):
            send(do_prune())
        elif text.startswith("/publish"):
            parts = text.split()
            if len(parts) >= 2:
                send(handle_publish(parts[1]))
            else:
                send("Nutzung: /publish <youtube_id>")
        elif text.startswith("/help") or text.startswith("/start"):
            send("Befehle:\n"
                 "/sync — Dashboard mit YouTube abgleichen (Status + gelöschte)\n"
                 "/pending — Videos, die auf Freigabe warten\n"
                 "/cleanup — nie hochgeladene Einträge entfernen\n"
                 "/prune — Einträge ohne YouTube-Video entfernen\n"
                 "/publish <id> — Video öffentlich schalten")

    _save_offset(max_id)
    print(f"✅ {len(updates)} Update(s) verarbeitet")


if __name__ == "__main__":
    main()
