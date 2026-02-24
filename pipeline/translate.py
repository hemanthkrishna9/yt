"""Translation via Sarvam mayura:v1."""

import time
import requests

from config import HEADERS, SARVAM_REQUEST_DELAY
from pipeline.log import get_logger
from pipeline.retry import retry, check_response, APIError, sarvam_limiter

log = get_logger(__name__)


@retry(max_attempts=4, base_delay=0.5)
def _translate_batch(batch: str, source_lang: str, target_lang: str) -> str:
    """Translate a single batch with retry."""
    sarvam_limiter.wait()
    url = "https://api.sarvam.ai/translate"
    resp = requests.post(
        url,
        headers={**HEADERS, "Content-Type": "application/json"},
        json={
            "input": batch,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "model": "mayura:v1",
            "enable_preprocessing": True,
        },
        timeout=30,
    )
    check_response(resp, "Sarvam Translate")
    return resp.json().get("translated_text", batch)


def translate(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text in safe 900-char batches.

    Raises APIError if any batch fails after retries.
    """
    if not text.strip():
        return ""

    # Split into ~900 char batches at word boundaries
    words = text.split()
    batches, cur = [], []
    for word in words:
        if sum(len(x) + 1 for x in cur) + len(word) > 900:
            batches.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        batches.append(" ".join(cur))

    translated = []
    for i, batch in enumerate(batches):
        try:
            result = _translate_batch(batch, source_lang, target_lang)
            translated.append(result)
        except APIError:
            log.error(f"Translation failed on batch {i+1}/{len(batches)}",
                      extra={"api": "sarvam_translate", "chunk": i})
            raise
        time.sleep(SARVAM_REQUEST_DELAY)

    return " ".join(translated)
