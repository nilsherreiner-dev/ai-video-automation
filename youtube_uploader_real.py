#!/usr/bin/env python3
"""
YouTube Video Uploader - REAL UPLOAD
Uses Google OAuth2 to upload videos to YouTube channel
"""

import os
import json
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

# ============================================================================
# CONFIG
# ============================================================================

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "youtube_token.pickle")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "google_auth.json")

# ============================================================================
# TELEGRAM ALERTS
# ============================================================================

def send_telegram_alert(message: str, emoji: str = "📊"):
    """Send alert to user via Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": f"{emoji} {message}"}
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"✅ Telegram: {message}")
        else:
            print(f"⚠️ Telegram error: {response.text}")
    except Exception as e:
        print(f"⚠️ Telegram failed: {e}")

# ============================================================================
# YOUTUBE AUTHENTICATION
# ============================================================================

def get_youtube_service():
    """Get authenticated YouTube service"""
    try:
        creds = None
        
        # Primary path (GitHub Actions): authorized_user JSON from secret
        google_auth_json = os.getenv("GOOGLE_AUTH_JSON")
        if google_auth_json:
            creds_data = json.loads(google_auth_json)
            creds = Credentials.from_authorized_user_info(creds_data, YOUTUBE_SCOPES)
            # An empty/expired access token is normal — refresh with the refresh_token
            if not creds.valid:
                if creds.refresh_token:
                    creds.refresh(Request())
                else:
                    print("❌ Credentials have no refresh_token — regenerate the token JSON")
                    send_telegram_alert("YouTube auth: token JSON missing refresh_token", "❌")
                    return None
        else:
            # Local fallback: cached token or interactive flow (needs a browser)
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, 'rb') as token:
                    creds = pickle.load(token)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                elif os.path.exists(CREDENTIALS_FILE):
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_FILE, YOUTUBE_SCOPES)
                    creds = flow.run_local_server(port=0)
                else:
                    print("❌ No credentials found!")
                    return None
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        # Build YouTube service
        youtube = build('youtube', 'v3', credentials=creds)
        print("✅ YouTube authentication successful")
        return youtube
    
    except Exception as e:
        print(f"❌ YouTube authentication error: {e}")
        send_telegram_alert(f"YouTube auth failed: {e}", "❌")
        return None

# ============================================================================
# UPLOAD VIDEO
# ============================================================================

def upload_video(youtube, video_path: str, title: str, description: str, tags: list, category_id: str = "28"):
    """Upload video to YouTube"""
    try:
        if not os.path.exists(video_path):
            print(f"❌ Video file not found: {video_path}")
            send_telegram_alert(f"Video file not found: {video_path}", "❌")
            return False
        
        file_size = os.path.getsize(video_path)
        print(f"\n📹 Uploading video:")
        print(f"   Title: {title}")
        print(f"   File: {video_path}")
        print(f"   Size: {file_size / (1024*1024):.1f} MB")
        
        # Prepare video metadata
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en"
            },
            "status": {
                "privacyStatus": "public",
                "madeForKids": False,
                "selfDeclaredMadeForKids": False,
                "embeddable": True
            }
        }
        
        # Upload with resumable media
        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024  # 10 MB chunks
        )
        
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        # Execute upload with progress
        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    print(f"   📤 Upload progress: {int(status.progress() * 100)}%")
            except Exception as e:
                print(f"❌ Upload error: {e}")
                send_telegram_alert(f"Upload error: {e}", "❌")
                return False
        
        video_id = response['id']
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        print(f"✅ Video uploaded successfully!")
        print(f"   Video ID: {video_id}")
        print(f"   URL: {video_url}")
        
        send_telegram_alert(
            f"🎬 VIDEO UPLOADED TO YOUTUBE!\n"
            f"📌 {title}\n"
            f"🔗 {video_url}",
            "🎬"
        )
        
        return video_id
    
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        send_telegram_alert(f"Upload failed: {e}", "❌")
        return False

# ============================================================================
# MAIN - UPLOAD ALL VIDEOS FROM OUTPUT
# ============================================================================

def _mark_uploaded(slot: int, youtube_id: str):
    """Write the YouTube id + status back into data/videos.json (for the dashboard)."""
    try:
        data_file = os.path.join(SCRIPT_DIR, "data", "videos.json")
        if not os.path.exists(data_file):
            return
        with open(data_file) as f:
            videos = json.load(f)
        # update the most recent entry for this slot that is still pending
        for entry in reversed(videos):
            if entry.get("slot") == slot and entry.get("upload_status") != "uploaded":
                entry["youtube_id"] = youtube_id
                entry["upload_status"] = "uploaded"
                break
        with open(data_file, "w") as f:
            json.dump(videos, f, indent=2)
        print(f"✅ Dashboard updated (slot {slot} → {youtube_id})")
    except Exception as e:
        print(f"⚠️ Could not update dashboard log: {e}")


def upload_all_videos():
    """Upload all generated videos from output directory"""
    output_dir = os.path.join(SCRIPT_DIR, "output")
    
    if not os.path.exists(output_dir):
        print("❌ No output directory found")
        return
    
    # Find all .mp4 files
    videos = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    
    if not videos:
        print("⚠️ No videos to upload")
        return
    
    # Authenticate
    youtube = get_youtube_service()
    if not youtube:
        print("❌ Could not authenticate with YouTube")
        return

    # NOTE: no channels().list() call here — it needs the youtube.readonly scope.
    # Uploads go to the channel that authorized the token, so it is not needed.
    
    # Load video metadata
    metadata_file = os.path.join(output_dir, "videos_log.json")
    metadata_map = {}
    if os.path.exists(metadata_file):
        with open(metadata_file, "r") as f:
            videos_data = json.load(f)
            for v in videos_data:
                metadata_map[v.get("id")] = v
    
    # Upload each video
    uploaded_count = 0
    for video_file in sorted(videos):
        try:
            # Extract video ID from filename
            video_id = int(video_file.split("_")[1].split(".")[0])
            
            # Get metadata
            metadata = metadata_map.get(video_id, {})
            title = metadata.get("title", f"Trending Video #{video_id}")
            description = (
                f"{metadata.get('trend', 'Trending viral video')}\n\n"
                "🤖 AI-generated content | Subscribe for daily viral videos!\n"
                "#viral #trending #shorts #ai #facts"
            )
            tags = ["viral", "trending", "AI", "shorts", "facts", "NeuronOv3rload"]
            
            video_path = os.path.join(output_dir, video_file)

            # Upload
            yt_id = upload_video(youtube, video_path, title, description, tags)
            if yt_id:
                uploaded_count += 1
                _mark_uploaded(video_id, yt_id)

        except Exception as e:
            print(f"⚠️ Error processing {video_file}: {e}")
            continue
    
    print(f"\n{'='*80}")
    print(f"✅ Upload complete: {uploaded_count}/{len(videos)} videos uploaded")
    print(f"{'='*80}")
    
    send_telegram_alert(
        f"✅ Upload batch complete!\n"
        f"📊 {uploaded_count}/{len(videos)} videos uploaded to YouTube",
        "✅"
    )

if __name__ == "__main__":
    upload_all_videos()
