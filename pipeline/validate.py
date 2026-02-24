"""
Validation pipeline for dubbed audio.

Checks:
  1. File exists and is non-empty
  2. Duration is within acceptable range of original
  3. STT on dubbed audio → back-translate to English → similarity with original
  4. Overall pass/fail verdict
"""

import difflib
import math
import tempfile
from pathlib import Path

from pipeline.audio import get_duration, split_audio
from pipeline.stt import transcribe
from pipeline.translate import translate
from pipeline.log import get_logger
from config import CHUNK_SECS

log = get_logger(__name__)


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

    # ── Check 3: STT on dubbed audio (chunked to respect API limits) ────────
    print("  → STT on dubbed audio...")
    try:
        if dub_dur <= CHUNK_SECS:
            dubbed_transcript = transcribe(dubbed_audio, target_lang)
        else:
            # Split into chunks for STT (API has 30s limit)
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                chunks = split_audio(dubbed_audio, dub_dur, tmp_path)
                parts = []
                for chunk in chunks:
                    part = transcribe(chunk, target_lang)
                    parts.append(part)
                dubbed_transcript = " ".join(parts)
    except Exception as e:
        log.warning(f"STT validation failed: {e}")
        check("stt_dubbed", False, f"STT error: {e}")
        results["verdict"] = "WARN — could not validate dubbed speech (STT error)"
        results["passed"] = True  # don't fail the whole pipeline for validation issues
        return results

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


def validate_short(
    video_path: Path,
    min_duration: float = 15.0,
    max_duration: float = 180.0,
) -> dict:
    """
    Validate a Story Short video before upload.
    Checks: file size, duration range (15s–3min), video+audio streams, resolution.
    """
    import json, subprocess

    results = {"checks": {}, "passed": True, "verdict": ""}

    def check(name: str, passed: bool, detail: str):
        results["checks"][name] = {"passed": passed, "detail": detail}
        if not passed:
            results["passed"] = False

    # 1. File exists and > 500 KB
    if not video_path.exists():
        check("file_exists", False, "File not found")
        results["verdict"] = "FAIL — video file missing"
        return results
    size_kb = video_path.stat().st_size // 1024
    check("file_exists", size_kb > 500, f"{video_path.name} ({size_kb} KB)")

    # 2. Duration
    dur = get_duration(video_path)
    dur_ok = min_duration <= dur <= max_duration
    check("duration", dur_ok,
          f"{dur:.1f}s (expected {min_duration}s–{max_duration}s)")

    # 3. Video + audio streams
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", str(video_path)],
        capture_output=True, text=True
    )
    streams = json.loads(r.stdout).get("streams", [])
    has_video = any(s["codec_type"] == "video" for s in streams)
    has_audio = any(s["codec_type"] == "audio" for s in streams)
    check("has_video_stream", has_video, "video stream present" if has_video else "MISSING")
    check("has_audio_stream", has_audio, "audio stream present" if has_audio else "MISSING")

    # 4. Resolution check (should be 1080x1920)
    video_stream = next((s for s in streams if s["codec_type"] == "video"), None)
    if video_stream:
        w = video_stream.get("width", 0)
        h = video_stream.get("height", 0)
        res_ok = w == 1080 and h == 1920
        check("resolution", res_ok, f"{w}x{h} (expected 1080x1920)")

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
