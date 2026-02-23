"""Translation via Sarvam mayura:v1."""

import time
import requests

from config import HEADERS


def translate(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text in safe 900-char batches."""
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
    url = "https://api.sarvam.ai/translate"
    for batch in batches:
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
        )
        if resp.status_code != 200:
            print(f"  ✗ Translate error {resp.status_code}: {resp.text[:200]}")
            translated.append(batch)  # fallback: keep original
        else:
            translated.append(resp.json().get("translated_text", batch))
        time.sleep(0.2)

    return " ".join(translated)
