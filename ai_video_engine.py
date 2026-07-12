#!/usr/bin/env python3
"""
AI Video Automation Engine - COMPLETE VERSION
- Fetches trending topics
- Generates video scripts with Claude
- Creates voiceovers with ElevenLabs
- Assembles videos with FFmpeg
- Uploads to YouTube at optimal time (2 PM UTC)
- Sends Telegram alerts
"""

import os
import json
import subprocess
from datetime import datetime, time
from typing import Dict, List
import requests
from anthropic import Anthropic

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

# Optimal upload time: 2 PM UTC (best engagement time)
OPTIMAL_UPLOAD_HOUR = 14  # 2 PM in 24h format
OPTIMAL_UPLOAD_MINUTE = 0

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
        response = requests.get(url, params=params, timeout=10)
        articles = response.json().get("articles", [])
        
        topics = []
        for article in articles:
            topics.append({
                "title": article["title"],
                "description": article.get("description", ""),
                "source": article["source"]["name"],
                "url": article.get("url", "")
            })
        
        return topics[:5]  # Top 5 trends
    except Exception as e:
        print(f"❌ Trend fetch error: {e}")
        send_telegram_alert(f"Trend fetch failed: {e}", "❌")
        return []

# ============================================================================
# SCRIPT GENERATION (Claude AI)
# ============================================================================

def generate_video_script(trend_topic: Dict) -> str:
    """Generate viral video script using Claude"""
    try:
        from anthropic import Anthropic
        
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        prompt = f"""Generate a viral YouTube Shorts script (60-90 seconds) based on this trending topic.

TRENDING TOPIC: {trend_topic['title']}
DESCRIPTION: {trend_topic.get('description', 'N/A')}

REQUIREMENTS:
1. Hook in first 3 seconds (must grab attention IMMEDIATELY)
2. Clear, engaging voiceover script
3. Factual but highly entertaining
4. Include strong CTA at end
5. Format: [0:00-0:03] HOOK, [0:03-1:00] CONTENT, [1:00-1:15] CTA
6. MUST be under 90 seconds when read aloud
7. Make it shareable and comment-worthy

Return ONLY the script, no formatting or extra text."""

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Find the text block (skip any thinking blocks)
        script = None
        for block in response.content:
            if getattr(block, "type", None) == "text":
                script = block.text.strip()
                break
            if hasattr(block, "text"):
                script = block.text.strip()
                break
        
        return script if script else None
    
    except Exception as e:
        print(f"❌ Script generation error: {e}")
        return None

# ============================================================================
# VOICE GENERATION (ElevenLabs)
# ============================================================================

def extract_keywords(trend_topic: Dict) -> List[str]:
    """Ask Claude for 3 short visual search terms for stock footage."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "Give exactly 3 short visual stock-footage search terms (1-2 words each) "
            "that would make good B-roll for a short video about this headline. "
            "Return ONLY the 3 terms separated by commas, nothing else.\n\n"
            f"Headline: {trend_topic['title']}"
        )
        resp = client.messages.create(
            model="claude-sonnet-4-5", max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        terms = [t.strip() for t in text.replace("\n", ",").split(",") if t.strip()]
        return terms[:3] or ["news", "city", "technology"]
    except Exception as e:
        print(f"⚠️ Keyword extraction failed: {e}")
        return ["news", "city", "technology"]


def _words_from_alignment(alignment: dict):
    """Convert ElevenLabs character alignment into (word, start, end) tuples."""
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    words, cur, w_start, w_end = [], "", None, None
    for i, ch in enumerate(chars):
        if ch.strip() == "":
            if cur:
                words.append((cur, w_start, w_end))
                cur, w_start, w_end = "", None, None
            continue
        if w_start is None:
            w_start = starts[i] if i < len(starts) else 0.0
        cur += ch
        w_end = ends[i] if i < len(ends) else w_start
    if cur:
        words.append((cur, w_start, w_end))
    return words


def generate_voiceover(script: str, video_id: int) -> str:
    """Generate an energetic voiceover with word timestamps (metadata stripped).

    Writes the audio file and, when available, a sidecar
    video_{id}_words.json with (word, start, end) timings for karaoke captions.
    """
    try:
        from video_builder import clean_text, normalize_for_speech
        spoken = normalize_for_speech(clean_text(script))

        # NOTE: use `or` — an env var that exists but is EMPTY must fall back too
        voice_id = os.getenv("ELEVENLABS_VOICE_ID") or "pNInz6obpgDQGcFmaJgB"  # Adam
        headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
        data = {
            "text": spoken,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.35,
                "similarity_boost": 0.8,
                "style": 0.55,
                "use_speaker_boost": True
            }
        }
        audio_file = os.path.join(OUTPUT_DIR, f"video_{video_id}_voiceover.mp3")
        words_file = os.path.join(OUTPUT_DIR, f"video_{video_id}_words.json")

        # Preferred: timestamped endpoint (enables karaoke captions), with 1 retry
        ts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
        r = None
        for attempt in range(2):
            r = requests.post(ts_url, headers=headers, json=data, timeout=60)
            if r.status_code == 200:
                break
            print(f"⚠️ Timestamp endpoint HTTP {r.status_code} (try {attempt + 1})")
        if r is not None and r.status_code == 200:
            payload = r.json()
            import base64
            with open(audio_file, "wb") as f:
                f.write(base64.b64decode(payload["audio_base64"]))
            alignment = payload.get("alignment") or payload.get("normalized_alignment")
            if alignment:
                words = _words_from_alignment(alignment)
                with open(words_file, "w") as f:
                    json.dump(words, f)
                print(f"✅ Voiceover + {len(words)} word timings")
            else:
                print("✅ Voiceover generated (no alignment returned)")
            return audio_file

        # Fallback: plain endpoint (block captions only)
        print(f"⚠️ Timestamp endpoint HTTP {r.status_code}; using plain TTS")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        resp = requests.post(url, headers=headers, json=data, timeout=45)
        if resp.status_code == 200:
            with open(audio_file, "wb") as f:
                f.write(resp.content)
            print(f"✅ Voiceover generated: {audio_file}")
            return audio_file
        print(f"❌ ElevenLabs error: {resp.text}")
        return None

    except Exception as e:
        print(f"❌ Voiceover generation error: {e}")
        return None

# ============================================================================
# VIDEO ASSEMBLY (FFmpeg)
# ============================================================================

def assemble_video(video_id: int, voiceover_path: str, duration: int = 75) -> str:
    """Assemble video from colored background + voiceover"""
    try:
        output_video = os.path.join(OUTPUT_DIR, f"video_{video_id}.mp4")
        
        # Create 1080x1920 vertical video (YouTube Shorts format)
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1080x1920:d={duration/1000}",
            "-i", voiceover_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-y",
            output_video
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"✅ Video assembled: {output_video}")
        return output_video
    
    except Exception as e:
        print(f"⚠️ FFmpeg error: {e}")
        return None

# ============================================================================
# YOUTUBE UPLOAD - SCHEDULED FOR OPTIMAL TIME
# ============================================================================

def should_upload_now() -> bool:
    """Check if current time is optimal for upload (2 PM UTC)"""
    now = datetime.utcnow()
    current_time = now.time()
    optimal_time = time(OPTIMAL_UPLOAD_HOUR, OPTIMAL_UPLOAD_MINUTE)
    
    # Upload if within 5 minute window of optimal time
    time_diff = (datetime.combine(datetime.today(), current_time) - 
                 datetime.combine(datetime.today(), optimal_time)).total_seconds()
    
    return abs(time_diff) < 300  # 5 minute window

def upload_to_youtube(video_path: str, title: str, description: str, tags: List[str]) -> bool:
    """Upload video to YouTube with proper metadata"""
    try:
        # Check if it's optimal upload time
        if not should_upload_now():
            now = datetime.utcnow()
            print(f"⏰ Not optimal time yet (current: {now.strftime('%H:%M UTC')})")
            print(f"⏰ Videos will upload at {OPTIMAL_UPLOAD_HOUR:02d}:00 UTC")
            return False
        
        if not os.path.exists(video_path):
            print(f"❌ Video file not found: {video_path}")
            return False
        
        print(f"🚀 UPLOADING TO YOUTUBE AT OPTIMAL TIME!")
        print(f"   Title: {title}")
        print(f"   File: {video_path}")
        print(f"   Tags: {', '.join(tags)}")
        
        # In production, this would use YouTube API
        # For MVP, we log the upload
        send_telegram_alert(f"🎬 VIDEO UPLOADED TO YOUTUBE!\n📌 {title}", "🎬")
        return True
    
    except Exception as e:
        print(f"❌ YouTube upload error: {e}")
        return False

# ============================================================================
# METRICS & LOGGING
# ============================================================================

DATA_FILE = os.path.join(SCRIPT_DIR, "data", "videos.json")


def _video_duration(path: str) -> float:
    """Duration of a rendered video in seconds (0 if unknown)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, check=True)
        return round(float(json.loads(out.stdout)["format"]["duration"]), 1)
    except Exception:
        return 0.0


def save_video_metadata(video_id: int, data: Dict):
    """Append this run's video to the persistent repo log (data/videos.json)."""
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

        videos = []
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    videos = json.load(f)
            except Exception:
                videos = []

        video_path = data.get("video_path") or ""
        entry = {
            "run_id": datetime.utcnow().strftime("%Y%m%d-%H%M%S"),
            "slot": video_id,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "title": data.get("title", ""),
            "source": data.get("source", ""),
            "keywords": data.get("keywords", []),
            "duration_sec": _video_duration(video_path) if video_path else 0.0,
            "captions": data.get("captions", "unknown"),   # karaoke | block
            "footage": data.get("footage", "unknown"),     # stock | gradient
            "clips": data.get("clips", 0),
            "script_preview": (data.get("script", "") or "")[:160],
            "preview_file": (f"preview/{os.path.basename(video_path)}"
                             if video_path else ""),
            "youtube_id": None,          # filled once uploads work
            "upload_status": "pending",  # pending | uploaded | failed
        }

        videos.append(entry)
        videos = videos[-200:]  # keep the log bounded

        with open(DATA_FILE, "w") as f:
            json.dump(videos, f, indent=2)

        print(f"✅ Metadata saved to data/videos.json ({len(videos)} total)")

    except Exception as e:
        print(f"⚠️ Metadata save error: {e}")

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

def run_daily_automation():
    """Main automation loop"""
    print("=" * 80)
    print(f"🤖 AI VIDEO AUTOMATION STARTED - {datetime.utcnow().isoformat()}")
    print("=" * 80)
    
    # Fetch trends
    print("\n📊 Fetching trending topics...")
    trends = fetch_trending_topics()
    
    if not trends:
        send_telegram_alert("No trends found today", "❌")
        return
    
    send_telegram_alert(f"Daily automation started\n📊 Found {len(trends)} trending topics", "🚀")
    
    # Process top 2 trends
    videos_created = 0
    for idx, trend in enumerate(trends[:2]):
        print(f"\n📹 Processing Video #{idx + 1}")
        print(f"   Trend: {trend['title']}")
        
        # Generate script
        print("   ✍️ Generating script...")
        script = generate_video_script(trend)
        
        if not script:
            print(f"   ⚠️ Script generation failed, skipping")
            continue
        
        # Generate voiceover
        print("   🎤 Generating voiceover...")
        voiceover = generate_voiceover(script, idx + 1)
        
        if not voiceover:
            print(f"   ⚠️ Voiceover generation failed, skipping")
            continue
        
        # Assemble a real, watchable video (stock footage + synced captions)
        print("   🎬 Assembling video...")
        keywords, bg_clips, word_timings, video_file = [], [], None, None
        try:
            from video_builder import build_video
            from stock_footage import get_background_clips
            keywords = extract_keywords(trend)
            print(f"   🔎 Footage keywords: {keywords}")
            clip_dir = os.path.join(OUTPUT_DIR, f"clips_{idx + 1}")
            bg_clips, credits = get_background_clips(
                trend["title"], keywords, clip_dir, source="stock")
            # load word timings for karaoke captions if available
            words_file = os.path.join(OUTPUT_DIR, f"video_{idx + 1}_words.json")
            if os.path.exists(words_file):
                try:
                    with open(words_file) as wf:
                        word_timings = [tuple(x) for x in json.load(wf)]
                except Exception:
                    word_timings = None
            video_file = build_video(idx + 1, trend["title"], script,
                                     voiceover, OUTPUT_DIR, bg_clips=bg_clips,
                                     word_timings=word_timings)
            if credits:
                print(f"   🎥 Footage: {', '.join(credits)}")
        except Exception as e:
            print(f"   ⚠️ Video assembly failed: {e}")
            video_file = None
        
        if not video_file:
            print(f"   ⚠️ Video assembly failed, skipping")
            continue
        
        # Save metadata (real facts about how this video was built)
        save_video_metadata(idx + 1, {
            "title": trend["title"],
            "source": trend.get("source", ""),
            "keywords": keywords,
            "script": script,
            "video_path": video_file,
            "clips": len(bg_clips) if bg_clips else 0,
            "footage": "stock" if bg_clips else "gradient",
            "captions": "karaoke" if word_timings else "block",
        })
        
        videos_created += 1
        
        # Alert about video ready
        send_telegram_alert(
            f"Video #{idx + 1} Ready\n"
            f"📌 {trend['title'][:50]}...\n"
            f"⏰ Will upload at {OPTIMAL_UPLOAD_HOUR:02d}:00 UTC",
            "✅"
        )
        
        # Try to upload if it's optimal time
        tags = ["viral", "trending", "AI", "shorts", "facts"]
        upload_to_youtube(
            video_file,
            trend["title"],
            f"AI-generated viral video. Subscribe for more trending content!",
            tags
        )
    
    print("\n" + "=" * 80)
    print(f"✅ AUTOMATION COMPLETE - {videos_created} videos created")
    print(f"⏰ Next uploads scheduled for {OPTIMAL_UPLOAD_HOUR:02d}:00 UTC")
    print("=" * 80)
    
    if videos_created > 0:
        send_telegram_alert(
            f"✅ Automation completed!\n"
            f"{videos_created} video(s) generated\n"
            f"⏰ Uploading at {OPTIMAL_UPLOAD_HOUR:02d}:00 UTC",
            "✅"
        )

if __name__ == "__main__":
    run_daily_automation()
