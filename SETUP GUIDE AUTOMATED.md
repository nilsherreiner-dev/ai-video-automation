# 🚀 AI VIDEO AUTOMATION - Complete Setup Guide

## Overview

This is a **100% Cloud-Based Automated Video Generation System**:
- ✅ Trends → Scripts → Voice → Video → YouTube (ALL AUTOMATIC)
- ✅ Runs daily via GitHub Actions (no server needed)
- ✅ Mobile-responsive Dashboard
- ✅ Telegram Alerts in real-time
- ✅ Zero manual work after setup

---

## 📋 Prerequisites (You Should Have)

- ✅ GitHub Account (you have this)
- ✅ API Keys saved:
  - `ELEVENLABS_API_KEY`
  - `NEWSAPI_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `ANTHROPIC_API_KEY` (for Claude)
  - `GOOGLE_AUTH_JSON` (the JSON file from Google Cloud)

---

## 🔧 SETUP STEPS (30 minutes)

### **Step 1: Create GitHub Repo** (5 min)

1. Go to github.com/new
2. Repo name: `ai-video-automation`
3. Description: "AI-powered automated YouTube video generation"
4. Make it **Public** (for GitHub Pages dashboard)
5. Create repo
6. Note your username (you'll need it)

### **Step 2: Upload Files to GitHub** (5 min)

1. Go to your new repo
2. Click "Add file" → "Create new file"
3. Create these files (copy from the scripts I provided):

```
ai-video-automation/
├── ai_video_engine.py (main automation)
├── requirements.txt (dependencies)
├── .github/
│   └── workflows/
│       └── daily_automation.yml (schedule)
├── Dashboard.jsx (web dashboard)
├── package.json (for React dashboard)
└── README.md (documentation)
```

**Easiest way:** Clone this repo locally (if you had a computer), or manually upload each file via GitHub web interface.

### **Step 3: Add Secrets to GitHub** (10 min)

This is **CRITICAL** - it's how your API keys are stored securely:

1. Go to your repo
2. Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret:

```
ELEVENLABS_API_KEY = your_key
NEWSAPI_KEY = your_key
YOUTUBE_API_KEY = your_key
TELEGRAM_BOT_TOKEN = your_bot_token
TELEGRAM_CHAT_ID = your_chat_id
ANTHROPIC_API_KEY = your_key
GOOGLE_AUTH_JSON = (paste entire JSON content)
```

**Security Note:** Secrets are ENCRYPTED and NOT visible in logs.

### **Step 4: Enable GitHub Actions** (2 min)

1. Go to your repo
2. Click "Actions" tab
3. It should auto-detect `daily_automation.yml`
4. Click "Enable"

Done! Automation will run daily at 9 AM UTC.

### **Step 5: Enable GitHub Pages (for Dashboard)** (5 min)

1. Settings → Pages
2. Source: "Deploy from branch"
3. Branch: "main"
4. Folder: "/dashboard/build"
5. Save

Your dashboard will be live at: `https://yourusername.github.io/ai-video-automation/`

---

## 🎯 How It Works (The Flow)

### **Daily Automation (Runs Automatically at 9 AM)**

```
GitHub Actions Triggers
  ↓
ai_video_engine.py starts
  ├─ 1. Fetch trending topics (NewsAPI)
  ├─ 2. Generate scripts (Claude)
  ├─ 3. Make voiceovers (ElevenLabs)
  ├─ 4. Assemble videos (FFmpeg)
  └─ 5. Upload to YouTube (YouTube API)
  ↓
Telegram Alert: "Video #1 uploaded ✅"
  ↓
Dashboard updates automatically
  ↓
Done! (No manual work needed)
```

---

## 📱 Dashboard Usage

**Your dashboard is live at:** `https://yourusername.github.io/ai-video-automation/`

**What you can do:**
- ✅ See all videos + performance metrics
- ✅ View trending performance over time
- ✅ Pause/Resume automation
- ✅ Monitor CTR, Views, Retention
- ✅ See scheduled videos

**Mobile friendly:** Works perfectly on phone!

---

## 🚨 First Run (Manual Test)

Before the daily schedule kicks in, you can test manually:

### **Option A: Test Locally** (if you have Python)
```bash
# On your computer:
git clone https://github.com/yourusername/ai-video-automation
cd ai-video-automation
pip install -r requirements.txt
python ai_video_engine.py
```

### **Option B: Test via GitHub Actions**
1. Go to Actions tab
2. Click "Daily AI Video Automation"
3. "Run workflow" button
4. Watch it run!
5. Check Telegram for alerts

---

## 📊 Monitoring & Control

### **Telegram Alerts** (automatic)
You'll get messages:
```
🚀 Daily automation started
📊 Found 5 trending topics

✅ Video #1 Ready
📌 Title: "Your Brain is TRICKING You"
📁 /output/video_1.mp4

📊 Daily automation completed
```

### **GitHub Actions Dashboard**
- Go to Actions tab
- See each run (blue = running, green = success, red = error)
- Click run to see detailed logs

### **YouTube Analytics**
- Your videos will be uploaded to your channel
- Monitor in YouTube Studio directly

---

## 🔧 Customization

### **Change upload time**
Edit `.github/workflows/daily_automation.yml`:
```yaml
cron: '0 9 * * *'  # 9 AM UTC
# Change to:
cron: '0 14 * * *'  # 2 PM UTC
```

### **Change video count**
Edit `ai_video_engine.py`:
```python
for idx, trend in enumerate(trends[:2]):  # Currently 2 videos/day
# Change 2 to: 5 (for 5 videos)
```

### **Change voice**
Edit `ai_video_engine.py`:
```python
"voice_id": "21m00Tcm4TlvDq8ikWAM"  # Bella (female)
# Other voices:
# - "EXAVITQu4eXMe7LCL94e" (Antoni, male)
# - "XB0fDUnXU5powFXDhCwa" (Ava, female)
```

---

## 🐛 Troubleshooting

### **"Workflow failed" error**
1. Click the failed run
2. Scroll to see error message
3. Usually API keys issue:
   - Check Secrets are added correctly
   - Make sure they're not expired
   - Test API keys manually

### **No videos appearing in YouTube**
- Check YouTube auth (Google Cloud credentials)
- Make sure channel is verified
- Check YouTube API quota

### **Telegram not getting alerts**
- Test: Send message to your bot manually
- Check TELEGRAM_CHAT_ID is correct
- Make sure bot token works

### **"FFmpeg not found"**
- The Ubuntu GitHub runner should have it
- If not: Add step to `daily_automation.yml`:
```yaml
- name: Install FFmpeg
  run: sudo apt-get install -y ffmpeg
```

---

## 💰 Cost Summary

**Monthly Costs (with full automation):**
```
ElevenLabs (Voice): €25
Runway AI (Optional video gen): €0 (using free stock footage)
NewsAPI (Free tier): €0
GitHub Actions: €0 (free)
YouTube API: €0
Telegram: €0
─────────────
TOTAL: ~€25/month
```

**One-time setup:** €0

---

## 🚀 What Happens After Setup?

**Day 1:**
- ✅ GitHub Actions configured
- ✅ Automation running

**Day 2:**
- ✅ First automated video generated
- ✅ You get Telegram alert
- ✅ Video appears on YouTube
- ✅ Dashboard shows metrics

**Week 1:**
- ✅ 7 videos uploaded automatically
- ✅ Real performance data
- ✅ You're monitoring (zero work)

**Week 4:**
- ✅ 28 videos uploaded
- ✅ Strong metrics coming in
- ✅ Optimization opportunities visible

---

## 📞 Support

**If something breaks:**
1. Check GitHub Actions logs (Actions tab)
2. Check error message (usually API key issue)
3. Verify secrets are correct
4. Test API keys manually

**Common fixes:**
- Delete secret, re-add it (copy-paste error?)
- Wait 5 min for secret changes to take effect
- Run workflow manually to test

---

## ✅ Checklist Before Going Live

- [ ] GitHub repo created
- [ ] All files uploaded
- [ ] All secrets added (6 total)
- [ ] GitHub Actions enabled
- [ ] GitHub Pages enabled
- [ ] Tested workflow manually once
- [ ] Got Telegram alert (proof it works)
- [ ] YouTube channels created
- [ ] Ready for daily automation

---

## 🎉 You're Done!

Your AI video automation is now live. Every day at 9 AM:
1. Trends are analyzed
2. Scripts are generated
3. Videos are created
4. Videos are uploaded to YouTube
5. You get Telegram alerts

**Zero manual work. Pure automation. 🚀**

Enjoy your hands-off YouTube channel! 📹✨
