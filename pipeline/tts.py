"""Text-to-speech via Sarvam bulbul:v1."""

import base64
import time
import requests
from pathlib import Path

from config import HEADERS, TTS_MODEL


def tts(text: str, target_lang: str, speaker: str, out_base: Path) -> list[Path]:
    """
    Generate TTS audio from text.
    Splits into ≤490-char sentence batches.
    Returns list of generated WAV paths.
    """
    if not text.strip():
        return []

    # Split into safe batches at sentence boundaries
    sentences = [s.strip() for s in text.replace("।", ".").split(".") if s.strip()]
    batches, cur = [], ""
    for s in sentences:
        if len(cur) + len(s) + 2 <= 490:
            cur += s + ". "
        else:
            if cur:
                batches.append(cur.strip())
            cur = s + ". "
    if cur:
        batches.append(cur.strip())

    files = []
    url = "https://api.sarvam.ai/text-to-speech"
    for i, batch in enumerate(batches):
        resp = requests.post(
            url,
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "inputs": [batch],
                "target_language_code": target_lang,
                "speaker": speaker,
                "model": TTS_MODEL,
                "pace": 1.0,
                "speech_sample_rate": 22050,
            },
        )
        if resp.status_code != 200:
            print(f"  ✗ TTS error {resp.status_code}: {resp.text[:200]}")
            continue
        audio_b64 = resp.json()["audios"][0]
        out_path = Path(f"{out_base}_tts_{i:03d}.wav")
        out_path.write_bytes(base64.b64decode(audio_b64))
        files.append(out_path)
        time.sleep(0.1)

    return files
