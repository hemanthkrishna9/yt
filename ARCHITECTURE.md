# YT Dubber & Story Shorts — Architecture

## Overview

Two-service platform for Indian language content creators:
1. **Dubber** — translate any YouTube video to another Indian language
2. **Story Shorts** — generate YouTube Shorts from stories (user-written or public domain)

---

## Project Structure

```
yt/
├── dub.py                    # CLI: YouTube video dubbing
├── story.py                  # CLI: Story-to-Short video generator
├── config.py                 # Central config & API keys
├── requirements.txt
├── .env                      # API keys (gitignored)
├── client_secret.json        # YouTube OAuth2 (gitignored)
├── token.json                # YouTube OAuth2 token cache (gitignored)
├── ARCHITECTURE.md           # This file
│
└── pipeline/
    │
    │── Phase 1: Dubbing ──────────────────────────────────────
    ├── downloader.py          # yt-dlp YouTube download
    ├── audio.py               # FFmpeg: extract, split, concat, merge, Ken Burns
    ├── stt.py                 # Sarvam saarika:v2.5 — Speech to Text
    ├── translate.py           # Sarvam mayura:v1 — Translation
    ├── tts.py                 # Sarvam bulbul:v3 — Text to Speech
    ├── normalize.py           # Number → words ("2003" → "two thousand and three")
    ├── validate.py            # STT back-check, duration, similarity scoring
    │
    │── Phase 2: Story Shorts ─────────────────────────────────
    ├── scraper.py             # Fetch stories from public domain sites
    ├── formatter.py           # Gemini: scene breakdown + image prompts (JSON)
    ├── imager.py              # Imagen 3: generate scene images (9:16)
    ├── narrator.py            # Per-scene TTS with mood-based pace
    ├── composer.py            # FFmpeg: Ken Burns + xfade + SRT subtitles
    └── publisher.py           # YouTube Data API v3 upload
```

---

## Service 1: Dubber (`dub.py`)

### Flow
```
YouTube URL / Local file
        ↓
  [downloader.py]  yt-dlp download
        ↓
  [audio.py]       Extract mono 16kHz WAV, split into 4-min chunks
        ↓
  [stt.py]         Sarvam STT → English transcript (per chunk, cached)
        ↓
  [normalize.py]   Numbers to words
        ↓
  [translate.py]   Sarvam Translate → target language (cached per lang)
        ↓
  [tts.py]         Sarvam TTS → dubbed WAV audio
        ↓
  [audio.py]       Concat all TTS segments + merge into video
                   Video frames adjusted (setpts) to match audio duration
        ↓
  [validate.py]    STT dubbed audio → back-translate → similarity score
        ↓
        dubbed_{language}.mp4
```

### Key Decisions
- **Caching at every step** — STT, translate, TTS all cached; reruns are instant
- **Video speed adjustment** — `setpts` filter stretches/compresses video frames to match dubbed audio length (better than padding silence or distorting voice)
- **Number normalization** — numbers converted to words before translation so TTS reads them naturally
- **Language isolation** — all cache files keyed by target language code

### CLI
```bash
python dub.py --url "https://youtube.com/shorts/..." --target te-IN
python dub.py --file video.mp4 --source hi-IN --target ta-IN --speaker kavya
```

---

## Service 2: Story Shorts (`story.py`)

### Two Input Modes

**Mode A — User Story**
```
User pastes story text → pipeline
```

**Mode B — Auto Fetch**
```
Theme keyword → scraper.py → story text → pipeline
If no story found → "no results" and exit cleanly
```

### Full Pipeline Flow
```
Story Text (user or scraped)
        ↓
  [formatter.py]   Gemini: clean story + break into 5-8 scenes
                   Output: JSON {scene_number, narration, image_prompt, duration_hint}
                   Also generates: YouTube title, description, tags
        ↓
  [imager.py]      Imagen 3: one 9:16 image per scene
                   Style prefix + image_prompt → JPEG cached per scene
        ↓
  [narrator.py]    Sarvam TTS: narrate each scene in target language
                   Pace adjusted by mood (calm=0.85x, dramatic=1.0x, etc.)
        ↓
  [composer.py]    FFmpeg pipeline:
                   1. Ken Burns effect per image (zoompan filter)
                   2. Each image + narration audio → scene clip
                   3. All clips stitched with xfade crossfade (0.5s dissolve)
                   4. SRT subtitles generated from narration text + timings
                   5. Subtitles burned into final video
        ↓
  [validate.py]    Duration check (15s–180s), streams check, resolution check
        ↓
  [publisher.py]   YouTube Data API v3 upload (always private first)
        ↓
        short.mp4  +  youtube_url.txt
```

### Story Sources (Public Domain)

| Theme | Source | URL |
|-------|--------|-----|
| `aesop` | Project Gutenberg | gutenberg.org/files/21/21-0.txt |
| `panchatantra` | Project Gutenberg | gutenberg.org/files/12455/12455-0.txt |
| `tenali` | Internet Archive | archive.org/stream/StoriesOfTenaliRaman-English |
| `jataka` | Sacred-texts.com | sacred-texts.com/bud/j1/ |
| `vikram` | Project Gutenberg | gutenberg.org/files/1460/1460-0.txt |

- Sources cached locally, re-fetched after 7 days
- If network fails or theme not found → returns empty, CLI exits with "no results"

### Mood → TTS Pace

| Mood | Pace | Use case |
|------|------|----------|
| 😌 calm | 0.85x | Bedtime stories, gentle tales |
| 🤔 curious | 0.88x | Mystery, suspense |
| 😄 cheerful | 1.10x | Comedy, fun stories |
| 🔥 dramatic | 1.00x | Action, adventure |
| 😢 emotional | 0.75x | Sad, moving stories |

### CLI
```bash
python story.py --text "Once upon a time..." --lang te-IN --mood dramatic
python story.py --theme aesop --lang hi-IN
python story.py --theme panchatantra --lang te-IN --no-upload
python story.py --theme xyz --lang en-IN        # → "no results found"
```

---

## APIs Used

| API | Purpose | Model/Version |
|-----|---------|---------------|
| Sarvam AI | STT | saarika:v2.5 |
| Sarvam AI | Translation | mayura:v1 |
| Sarvam AI | TTS | bulbul:v3 |
| Google Gemini | Scene breakdown, metadata | gemini-2.0-flash |
| Google Imagen 3 | Image generation | imagen-3.0-generate-002 |
| YouTube Data API v3 | Video upload | v3 |

---

## Config & Secrets

```
.env file:
  SARVAM_API_KEY              — Sarvam AI
  GEMINI_API_KEY              — Google AI Studio
  YOUTUBE_CLIENT_SECRET_PATH  — path to client_secret.json

client_secret.json            — YouTube OAuth2 (from Google Cloud Console)
token.json                    — Auto-generated after first YouTube login
```

---

## Output Directory Layout

### Dubber
```
output/<video_title>/
├── audio_full.wav
├── chunk_000.wav
├── transcript_src_000.txt
├── transcript_tgt_te-IN_000.txt
├── tts_te-IN_000_tts_000.wav
├── dubbed_audio_te-IN.wav
└── dubbed_telugu.mp4
```

### Story Shorts
```
output/story_<theme>_<timestamp>/
├── story_text.txt
├── breakdown.json
├── scene_01.jpg … scene_08.jpg
├── narration_01.wav … narration_08.wav
├── clip_01.mp4 … clip_08.mp4
├── stitched.mp4
├── subtitles.srt
├── short.mp4
└── youtube_url.txt
```

---

## Future: SaaS Architecture

```
┌─────────────────────────────────────┐
│         Next.js Frontend            │
│  Paste URL | Choose language/mood   │
│  Story creator | Analytics          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│         FastAPI Backend             │
│  /dub  /story  /job/{id}  /auth     │
│  Razorpay payments | Supabase auth  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│     Azure Functions (Workers)       │
│  Dubbing pipeline | Story pipeline  │
│  Azure Blob Storage for files       │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
 Sarvam     Gemini    YouTube
  APIs      + Imagen    API
```

### Pricing (Planned)
| Plan | Price | Videos/month |
|------|-------|--------------|
| Starter | ₹999/mo | 30 |
| Creator | ₹2499/mo | 100 |
| Agency | ₹7999/mo | Unlimited |
