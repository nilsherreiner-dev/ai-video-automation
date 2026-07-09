# 🤖 AI Video Automation System

**100% Automated YouTube Video Generation using AI**

Generate, produce, and upload viral YouTube Shorts automatically every day—zero manual work required.

## ✨ Features

- 🧠 **AI Script Generation** - Claude generates trending video scripts
- 🎤 **Voice Synthesis** - ElevenLabs creates professional voiceovers
- 🎬 **Video Assembly** - FFmpeg assembles videos automatically
- 📺 **YouTube Upload** - Auto-uploads to your channel
- 📊 **Live Dashboard** - Mobile & desktop analytics dashboard
- 🔔 **Telegram Alerts** - Real-time notifications
- ⚙️ **Zero Manual Work** - Fully hands-off operation
- 💰 **Cheap** - ~€25/month total cost

## 🚀 Quick Start

### Prerequisites
- GitHub Account
- API Keys (ElevenLabs, NewsAPI, YouTube, Telegram, Claude)
- 30 minutes for setup

### Setup (5 Steps)

1. **Fork/Clone this repo**
   ```bash
   git clone https://github.com/yourusername/ai-video-automation
   cd ai-video-automation
   ```

2. **Add GitHub Secrets** (Settings → Secrets)
   - `ELEVENLABS_API_KEY`
   - `NEWSAPI_KEY`
   - `YOUTUBE_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_AUTH_JSON`

3. **Enable GitHub Actions**
   - Go to Actions tab
   - Click "Enable"

4. **Enable GitHub Pages**
   - Settings → Pages
   - Deploy from main branch

5. **Manual test**
   - Actions tab → "Daily AI Video Automation" → "Run workflow"

**Done!** Your automation is live. Videos generate daily at 9 AM UTC.

---

## 📁 Project Structure

```
ai-video-automation/
├── ai_video_engine.py          # Main automation engine
├── Dashboard.jsx                # React dashboard component
├── requirements.txt             # Python dependencies
├── package.json                 # NPM dependencies
├── .github/
│   └── workflows/
│       └── daily_automation.yml # GitHub Actions schedule
├── SETUP_GUIDE_AUTOMATED.md     # Detailed setup instructions
└── README.md                    # This file
```

---

## 🔄 How It Works

### Daily Automation Flow

```
9 AM UTC (Daily)
  ↓
GitHub Actions Trigger
  ↓
1. Fetch Trending Topics (NewsAPI)
2. Generate Scripts (Claude AI)
3. Create Voiceovers (ElevenLabs)
4. Assemble Videos (FFmpeg)
5. Upload to YouTube (YouTube API)
6. Update Dashboard Metrics
7. Send Telegram Alert
  ↓
Videos Live on YouTube ✅
```

### Manual Trigger

You can manually run the automation anytime:
1. Go to Actions tab
2. Click "Daily AI Video Automation"
3. "Run workflow" button
4. Watch it generate videos in real-time

---

## 📊 Dashboard

**Live at:** `https://yourusername.github.io/ai-video-automation/`

### Features:
- 📈 Real-time view counts & engagement
- 📱 Fully responsive (mobile & desktop)
- ▶️ Pause/Resume automation
- 📅 Scheduled videos preview
- 🔔 Recent activity feed

### Mobile View:
- Optimized for small screens
- One-column layout
- Touch-friendly buttons
- Swipe to navigate

---

## 🎯 Configuration

### Change Video Upload Time

Edit `.github/workflows/daily_automation.yml`:
```yaml
cron: '0 9 * * *'  # Current: 9 AM UTC
cron: '0 14 * * *' # Change to: 2 PM UTC
```

### Change Videos Per Day

Edit `ai_video_engine.py`:
```python
for idx, trend in enumerate(trends[:2]):  # Currently 2 videos
# Change 2 to: 5  # For 5 videos per day
```

### Change Voice

Edit `ai_video_engine.py`:
```python
"voice_id": "21m00Tcm4TlvDq8ikWAM"  # Bella
# Other options:
# "EXAVITQu4eXMe7LCL94e" # Antoni (male)
# "XB0fDUnXU5powFXDhCwa" # Ava (female)
```

---

## 💰 Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| ElevenLabs | €25/mo | Voice synthesis |
| NewsAPI | €0 | Free tier (100 req/day) |
| GitHub Actions | €0 | Free for public repos |
| YouTube API | €0 | Free tier |
| Runway AI | €0-30 | Optional video generation |
| **Total** | **€25/mo** | |

---

## 🐛 Troubleshooting

### Videos not uploading?
1. Check YouTube OAuth is configured
2. Verify channel ID in settings
3. Check API quota in Google Cloud Console

### Telegram alerts not working?
1. Test bot manually: @BotFather /start
2. Verify TELEGRAM_CHAT_ID is correct
3. Check token is valid

### GitHub Actions failing?
1. Click failed run in Actions tab
2. Scroll to see error message
3. Usually: Missing secret or invalid API key
4. Add/fix secret and retry

### FFmpeg errors?
The runner installs FFmpeg automatically. If issues:
```yaml
- name: Install FFmpeg
  run: sudo apt-get install -y ffmpeg
```

---

## 🔐 Security

- ✅ API keys stored in GitHub Secrets (encrypted)
- ✅ Never exposed in logs or code
- ✅ Secrets only visible to repo owner
- ✅ Can be rotated anytime
- ✅ Auto-disable if leaked (configure in ElevenLabs)

---

## 📈 Performance Tips

1. **Start with 2 videos/day** - Test, then scale
2. **Monitor CTR** - Some topics perform better
3. **Check retention** - Adjust script length if needed
4. **A/B test hooks** - Different openings work for different topics
5. **Track comments** - See what audience wants

---

## 🎓 What You Learn

By setting this up, you'll understand:
- ✅ GitHub Actions & CI/CD
- ✅ API integration (6+ different APIs)
- ✅ Cloud-based automation
- ✅ Python scripting
- ✅ React dashboards
- ✅ YouTube API
- ✅ Telegram bots

---

## 🚀 Next Steps

1. **Week 1:** Let it run, collect data
2. **Week 2:** Analyze performance, optimize
3. **Week 3:** Scale to more videos per day
4. **Week 4:** Add custom hooks/strategies
5. **Month 2:** Monetize with ads/sponsors

---

## 📞 Support & Issues

### GitHub Issues
Have a bug? [Create an issue](../../issues)

### Logs
- Check GitHub Actions → workflow run → logs
- Error messages usually very clear
- Copy error, search in SETUP_GUIDE_AUTOMATED.md

### Common Errors

| Error | Fix |
|-------|-----|
| `404 Not Found` (API) | Check API key in secrets |
| `timeout` | API server slow, will retry |
| `FFmpeg not found` | Reinstall: `apt-get install ffmpeg` |
| `YouTube quota exceeded` | Wait 24h, reduce videos/day |

---

## 📄 License

MIT - Use freely, modify as needed

---

## 🎉 Credits

Built with:
- **Claude (Anthropic)** - AI Script generation
- **ElevenLabs** - Voice synthesis
- **YouTube API** - Video hosting
- **GitHub Actions** - Automation
- **React & Recharts** - Dashboard

---

## 🌟 Star this repo if it helped!

Every star motivates me to add more features. Consider starring if you find this useful! ⭐

---

**Questions? Check SETUP_GUIDE_AUTOMATED.md for detailed instructions!**

Happy automating! 🚀
