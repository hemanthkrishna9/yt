import os
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
CHUNK_SECS = 25  # Sarvam STT limit is 30s; use 25s for safety margin

# bulbul:v3 speakers (gender-neutral, work across all languages)
# Full list: aditya, ritu, ashutosh, priya, neha, rahul, pooja, rohan, simran, kavya, amit, dev
TTS_MODEL = "bulbul:v3"

# ── Sarvam API rate limits ────────────────────────────────────────────────
# Tier: starter=60/min, pro=200/min, business=1000/min
# Set via env var or defaults to starter tier
SARVAM_RATE_LIMIT = int(os.getenv("SARVAM_RATE_LIMIT", "60"))  # requests per minute
SARVAM_REQUEST_DELAY = 60.0 / SARVAM_RATE_LIMIT  # seconds between requests

# Supported languages: code -> (display name, default TTS speaker)
LANGUAGES = {
    "en-IN": ("English",    None),
    "hi-IN": ("Hindi",      "priya"),
    "te-IN": ("Telugu",     "priya"),
    "ta-IN": ("Tamil",      "priya"),
    "kn-IN": ("Kannada",    "priya"),
    "ml-IN": ("Malayalam",  "priya"),
    "bn-IN": ("Bengali",    "priya"),
    "mr-IN": ("Marathi",    "priya"),
    "gu-IN": ("Gujarati",   "priya"),
    "pa-IN": ("Punjabi",    "priya"),
    "od-IN": ("Odia",       "priya"),
}

HEADERS = {"api-subscription-key": SARVAM_API_KEY}

# ── Phase 2: Story Shorts ──────────────────────────────────────────────────
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL          = "gemini-2.0-flash-lite"
IMAGEN_MODEL          = "imagen-3.0-generate-002"

YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "client_secret.json")
YOUTUBE_TOKEN_CACHE   = "token.json"

# Mood -> TTS pace multiplier
MOOD_PACE = {
    "calm":       0.85,
    "curious":    0.88,
    "cheerful":   1.10,
    "dramatic":   1.00,
    "emotional":  0.75,
    "default":    1.00,
}

# All bulbul:v3 speakers
SPEAKERS = [
    "aditya", "ritu", "ashutosh", "priya", "neha", "rahul",
    "pooja", "rohan", "simran", "kavya", "amit", "dev",
]

# Story themes for auto-fetch
THEMES = ["aesop", "panchatantra", "tenali", "jataka", "vikram"]
