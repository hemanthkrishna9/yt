"""Text-to-speech via Sarvam bulbul:v3."""

import base64
import time
import requests
from pathlib import Path

from config import HEADERS, TTS_MODEL, SARVAM_REQUEST_DELAY
from pipeline.log import get_logger
from pipeline.retry import retry, check_response, APIError, sarvam_limiter

log = get_logger(__name__)


@retry(max_attempts=4, base_delay=0.5)
def _tts_batch(batch: str, target_lang: str, speaker: str, pace: float) -> str:
    """Single TTS API call with retry. Returns base64 audio."""
    sarvam_limiter.wait()
    url = "https://api.sarvam.ai/text-to-speech"
    resp = requests.post(
        url,
        headers={**HEADERS, "Content-Type": "application/json"},
        json={
            "inputs": [batch],
            "target_language_code": target_lang,
            "speaker": speaker,
            "model": TTS_MODEL,
            "pace": pace,
            "speech_sample_rate": 22050,
        },
        timeout=30,
    )
    check_response(resp, "Sarvam TTS")
    return resp.json()["audios"][0]


def tts(text: str, target_lang: str, speaker: str, out_base: Path, pace: float = 1.0) -> list[Path]:
    """
    Generate TTS audio from text.
    Splits into <=490-char sentence batches.
    Returns list of generated WAV paths.

    Raises APIError if any batch fails after retries.
    """
    if not text.strip():
        return []

    # Split into safe batches at sentence boundaries
    sentences = [s.strip() for s in text.replace("\u0964", ".").split(".") if s.strip()]
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
    for i, batch in enumerate(batches):
        try:
            audio_b64 = _tts_batch(batch, target_lang, speaker, pace)
            out_path = Path(f"{out_base}_tts_{i:03d}.wav")
            out_path.write_bytes(base64.b64decode(audio_b64))
            files.append(out_path)
        except APIError:
            log.error(f"TTS failed on batch {i+1}/{len(batches)}",
                      extra={"api": "sarvam_tts", "chunk": i})
            raise
        time.sleep(SARVAM_REQUEST_DELAY)

    return files
