"""
Validation pipeline for dubbed audio.

Checks:
  1. File exists and is non-empty
  2. Duration is within acceptable range of original
  3. STT on dubbed audio → back-translate to English → similarity with original
  4. Overall pass/fail verdict
"""

import difflib
from pathlib import Path

from pipeline.audio import get_duration
from pipeline.stt import transcribe
from pipeline.translate import translate


def word_overlap(text_a: str, text_b: str) -> float:
    """Simple word-level similarity ratio between two strings (0.0 to 1.0)."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / max(len(words_a), len(words_b))


def sequence_similarity(text_a: str, text_b: str) -> float:
    """SequenceMatcher ratio — order-aware similarity."""
    return difflib.SequenceMatcher(None, text_a.lower(), text_b.lower()).ratio()


def validate(
    original_audio: Path,
    dubbed_audio: Path,
    original_transcript: str,
    target_lang: str,
    source_lang: str = "en-IN",
) -> dict:
    """
    Run all validation checks. Returns a results dict with pass/fail.
    """
    results = {
        "checks": {},
        "passed": True,
        "verdict": "",
    }

    def check(name: str, passed: bool, detail: str):
        results["checks"][name] = {"passed": passed, "detail": detail}
        if not passed:
            results["passed"] = False

    print("\n  🔍 Validating dubbed audio...")

    # ── Check 1: File exists and non-empty ─────────────────────────────────
    if not dubbed_audio.exists() or dubbed_audio.stat().st_size < 1000:
        check("file_exists", False, f"File missing or too small: {dubbed_audio}")
        results["verdict"] = "FAIL — dubbed audio file invalid"
        return results
    check("file_exists", True, f"{dubbed_audio.name} ({dubbed_audio.stat().st_size // 1024} KB)")

    # ── Check 2: Duration reasonable ───────────────────────────────────────
    orig_dur = get_duration(original_audio)
    dub_dur  = get_duration(dubbed_audio)
    dur_ratio = dub_dur / orig_dur if orig_dur > 0 else 0
    # Accept if dubbed audio is between 50% and 200% of original duration
    dur_ok = 0.5 <= dur_ratio <= 2.0
    check("duration", dur_ok,
          f"Original: {orig_dur:.1f}s | Dubbed: {dub_dur:.1f}s | Ratio: {dur_ratio:.2f}x")

    # ── Check 3: STT on dubbed audio ───────────────────────────────────────
    print("  → STT on dubbed audio...")
    dubbed_transcript = transcribe(dubbed_audio, target_lang)
    if not dubbed_transcript.strip():
        check("stt_dubbed", False, "STT returned empty transcript for dubbed audio")
        results["verdict"] = "FAIL — dubbed audio has no detectable speech"
        return results
    check("stt_dubbed", True, f"Transcript: {dubbed_transcript[:120]}...")

    # ── Check 4: Back-translate to source language ─────────────────────────
    print("  → Back-translating to English...")
    back_translated = translate(dubbed_transcript, target_lang, source_lang)
    check("back_translate", bool(back_translated.strip()),
          f"Back-translated: {back_translated[:120]}...")

    # ── Check 5: Similarity with original ──────────────────────────────────
    word_sim = word_overlap(original_transcript, back_translated)
    seq_sim  = sequence_similarity(original_transcript, back_translated)
    avg_sim  = (word_sim + seq_sim) / 2

    # Pass threshold: >30% similarity (translation isn't word-for-word so this is lenient)
    sim_ok = avg_sim >= 0.30
    check("content_similarity", sim_ok,
          f"Word overlap: {word_sim:.0%} | Sequence: {seq_sim:.0%} | Avg: {avg_sim:.0%}")

    # ── Verdict ─────────────────────────────────────────────────────────────
    passed_count = sum(1 for c in results["checks"].values() if c["passed"])
    total = len(results["checks"])
    results["verdict"] = (
        f"{'PASS' if results['passed'] else 'FAIL'} — {passed_count}/{total} checks passed"
    )

    return results


def print_report(results: dict):
    """Pretty-print the validation report."""
    print("\n" + "─" * 60)
    print("  VALIDATION REPORT")
    print("─" * 60)
    for name, data in results["checks"].items():
        icon = "✅" if data["passed"] else "❌"
        print(f"  {icon} {name:<22} {data['detail']}")
    print("─" * 60)
    verdict = results["verdict"]
    icon = "✅" if results["passed"] else "❌"
    print(f"  {icon}  {verdict}")
    print("─" * 60)
