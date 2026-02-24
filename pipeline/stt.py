"""Speech-to-text via Sarvam saarika:v2.5."""

import requests
from pathlib import Path

from config import HEADERS
from pipeline.log import get_logger
from pipeline.retry import retry, check_response, APIError, sarvam_limiter

log = get_logger(__name__)


@retry(max_attempts=4, base_delay=1.0)
def _stt_request(chunk_path: Path, source_lang: str) -> str:
    """Single STT API call with retry."""
    sarvam_limiter.wait()
    url = "https://api.sarvam.ai/speech-to-text"
    with open(chunk_path, "rb") as f:
        resp = requests.post(
            url,
            headers=HEADERS,
            files={"file": (chunk_path.name, f, "audio/wav")},
            data={"model": "saarika:v2.5", "language_code": source_lang},
            timeout=60,
        )
    check_response(resp, "Sarvam STT")
    return resp.json().get("transcript", "")


def transcribe(chunk_path: Path, source_lang: str) -> str:
    """Transcribe a WAV chunk. Returns transcript string.

    Raises APIError if all retries fail.
    """
    try:
        transcript = _stt_request(chunk_path, source_lang)
        if not transcript.strip():
            log.warning(f"STT returned empty transcript for {chunk_path.name}",
                        extra={"api": "sarvam_stt", "path": str(chunk_path)})
        return transcript
    except APIError:
        log.error(f"STT failed for {chunk_path.name} after retries",
                  extra={"api": "sarvam_stt", "path": str(chunk_path)})
        raise
