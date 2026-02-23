import os
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
CHUNK_SECS = 240  # 4 min per STT chunk (Sarvam safe limit)

# bulbul:v3 speakers (gender-neutral, work across all languages)
# Full list: aditya, ritu, ashutosh, priya, neha, rahul, pooja, rohan, simran, kavya, amit, dev
TTS_MODEL = "bulbul:v3"

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
