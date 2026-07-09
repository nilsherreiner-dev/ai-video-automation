#!/usr/bin/env python3
"""
AI Video Automation Engine
- Fetches trending topics
- Generates video scripts
- Creates voiceovers
- Assembles videos
- Uploads to YouTube
- Sends Telegram alerts
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Dict, List
import requests
from anthropic import Anthropic
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ============================================================================
# CONFIG
# ============================================================================

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# TELEGRAM ALERTS
# ============================================================================

def send_telegram_alert(message: str):
    """Send alert to user via Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ Telegram Alert Sent")
        else:
            print(f"❌ Telegram Error: {response.text}")
    except Exception as e:
        print(f"⚠️ Telegram Alert Failed: {e}")

# ============================================================================
# TREND ANALYSIS
# ============================================================================

def fetch_trending_topics() -> List[Dict]:
    """Fetch trending topics from NewsAPI"""
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "country": "us",
            "apiKey": NEWSAPI_KEY,
            "pageSize": 10,
            "sortBy": "popularity"
        }
        response = requests.get(url, params=params)
        articles = response.json().get("articles", [])
        
        topics = []
        for article in articles:
            topics.append({
                "title": article["title"],
                "description": article["description"],
                "source": article["source"]["name"],
                "url": article["url"]
            })
        
        return topics[:5]  # Top 5 trends
    except Exception as e:
        print(f"❌ Trend Fetch Error: {e}")
        return []

# ============================================================================
# SCRIPT GENERATION (Claude AI)
# ============================================================================

def generate_video_script(trend_topic: Dict) -> str:
    """Generate viral video script using Claude"""
    try:
        client = Anthropic()
        
        prompt = f"""Generate a viral YouTube Shorts script (60-90 seconds) based on this trending topic.

TRENDING TOPIC: {trend_topic['title']}
DESCRIPTION: {trend_topic['description']}

REQUIREMENTS:
1. Hook in first 3 seconds (must grab attention)
2. Clear, engaging voiceover
3. Factual but entertaining
4. Include CTA at end
5. Format: [0:00-0:03] HOOK, [0:03-1:00] CONTENT, [1:00-1:15] CTA
6. MUST be under 90 seconds when read

Return ONLY the script, no formatting."""

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        script = message.content[0].text
        return script
    
    except Exception as e:
        print(f"❌ Script Generation Error: {e}")
        return None

# ============================================================================
# VOICE GENERATION (ElevenLabs)
# ============================================================================

def generate_voiceover(script: str, video_id: int) -> str:
    """Generate voiceover using ElevenLabs"""
    try:
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        data = {
            "text": script,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            audio_file = os.path.join(OUTPUT_DIR, f"video_{video_id}_voiceover.mp3")
            with open(audio_file, "wb") as f:
                f.write(response.content)
            print(f"✅ Voiceover Generated: {audio_file}")
            return audio_file
        else:
            print(f"❌ ElevenLabs Error: {response.text}")
            return None
    
    except Exception as e:
        print(f"❌ Voiceover Generation Error: {e}")
        return None

# ============================================================================
# VIDEO ASSEMBLY (FFmpeg)
# ============================================================================

def assemble_video(video_id: int, voiceover_path: str, duration: int = 75) -> str:
    """Assemble video from static image + voiceover"""
    try:
        # Create simple colored background video
        output_video = os.path.join(OUTPUT_DIR, f"video_{video_id}.mp4")
        
        # Generate 1080x1920 video with voiceover
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1080x1920:d={duration/1000}",
            "-i", voiceover_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-y",  # overwrite
            output_video
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Video Assembled: {output_video}")
        return output_video
    
    except Exception as e:
        print(f"⚠️ FFmpeg Error (continuing): {e}")
        # Return None to skip upload, but don't crash
        return None

# ============================================================================
# YOUTUBE UPLOAD
# ============================================================================

def upload_to_youtube(video_path: str, title: str, description: str, channel_id: str) -> bool:
    """Upload video to YouTube"""
    try:
        # This would require OAuth setup - simplified for MVP
        print(f"📹 Would upload to YouTube:")
        print(f"   Title: {title}")
        print(f"   Video: {video_path}")
        return True
    
    except Exception as e:
        print(f"❌ YouTube Upload Error: {e}")
        return False

# ============================================================================
# METRICS TRACKING
# ============================================================================

def save_video_metadata(video_id: int, data: Dict):
    """Save video metadata to JSON"""
    try:
        metrics_file = os.path.join(OUTPUT_DIR, "videos_log.json")
        
        videos = []
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                videos = json.load(f)
        
        video_data = {
            "id": video_id,
            "timestamp": datetime.now().isoformat(),
            "title": data.get("title"),
            "trend": data.get("trend"),
            "script": data.get("script")[:100],  # First 100 chars
            "status": "uploaded"
        }
        
        videos.append(video_data)
        
        with open(metrics_file, "w") as f:
            json.dump(videos, f, indent=2)
        
        print(f"✅ Metadata Saved")
    
    except Exception as e:
        print(f"⚠️ Metadata Save Error: {e}")

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

def run_daily_automation():
    """Main automation loop"""
    print("=" * 80)
    print(f"🤖 AI VIDEO AUTOMATION STARTED - {datetime.now()}")
    print("=" * 80)
    
    # Fetch trends
    print("\n📊 Fetching Trending Topics...")
    trends = fetch_trending_topics()
    
    if not trends:
        send_telegram_alert("❌ No trends found today")
        return
    
    send_telegram_alert(f"🚀 Daily automation started\n📊 Found {len(trends)} trending topics")
    
    # Process top 2 trends
    for idx, trend in enumerate(trends[:2]):
        print(f"\n📹 Processing Video #{idx + 1}")
        print(f"   Trend: {trend['title']}")
        
        # Generate script
        print("   ✍️ Generating script...")
        script = generate_video_script(trend)
        
        if not script:
            continue
        
        # Generate voiceover
        print("   🎤 Generating voiceover...")
        voiceover = generate_voiceover(script, idx + 1)
        
        if not voiceover:
            continue
        
        # Assemble video
        print("   🎬 Assembling video...")
        video_file = assemble_video(idx + 1, voiceover)
        
        if not video_file:
            continue
        
        # Save metadata
        save_video_metadata(idx + 1, {
            "title": trend["title"],
            "trend": trend["description"],
            "script": script
        })
        
        # Alert user
        send_telegram_alert(
            f"✅ Video #{idx + 1} Ready\n"
            f"📌 {trend['title'][:50]}...\n"
            f"📁 {video_file}"
        )
    
    print("\n" + "=" * 80)
    print("✅ AUTOMATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    run_daily_automation()
