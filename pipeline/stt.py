"""Speech-to-text via Sarvam saarika:v2.5."""

import requests
from pathlib import Path

from config import HEADERS


def transcribe(chunk_path: Path, source_lang: str) -> str:
    """Transcribe a WAV chunk. Returns transcript string."""
    url = "https://api.sarvam.ai/speech-to-text"
    with open(chunk_path, "rb") as f:
        resp = requests.post(
            url,
            headers=HEADERS,
            files={"file": (chunk_path.name, f, "audio/wav")},
            data={"model": "saarika:v2.5", "language_code": source_lang},
        )
    if resp.status_code != 200:
        print(f"  ✗ STT error {resp.status_code}: {resp.text[:200]}")
        return ""
    return resp.json().get("transcript", "")
