"""Normalize text before translation — converts numbers to words so TTS reads them correctly."""

import re
from num2words import num2words


def numbers_to_words(text: str) -> str:
    """
    Replace all numbers in text with their English word equivalents.
    Examples:
      2003  → "two thousand and three"
      Brett Lee took 5 wickets → "Brett Lee took five wickets"
      150.5 → "one hundred and fifty point five"
    """
    def replace_match(m):
        raw = m.group(0).replace(",", "")  # remove thousand separators
        try:
            if "." in raw:
                return num2words(float(raw))
            else:
                return num2words(int(raw))
        except Exception:
            return m.group(0)  # fallback: keep original

    # Match integers (with optional commas) and decimals
    return re.sub(r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|\b\d+(?:\.\d+)?\b", replace_match, text)
