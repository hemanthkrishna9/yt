#!/usr/bin/env python3
"""
YT Dubber — YouTube video dubbing CLI
Usage:
  python dub.py --url  "https://youtube.com/shorts/..."  --target te-IN
  python dub.py --file /path/to/video.mp4               --target hi-IN
  python dub.py --url  "..."  --source en-IN --target ta-IN --speaker thendral
  python dub.py --url  "..."  --target hi-IN --workers 8   # parallel chunks
"""

import argparse
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import LANGUAGES
from pipeline.downloader import download_video
from pipeline.audio import extract_audio, split_audio, concat_audio, merge_audio_video
from pipeline.stt import transcribe
from pipeline.normalize import numbers_to_words
from pipeline.translate import translate
from pipeline.tts import tts
from pipeline.validate import validate, print_report
from pipeline.log import get_logger
from pipeline.retry import APIError

log = get_logger(__name__)


def step(n: int, msg: str):
    print(f"\n{'─'*60}\n[Step {n}] {msg}\n{'─'*60}")


def _collect_intermediates(output_dir: Path, target_lang: str) -> list[Path]:
    """Collect intermediate files that can be cleaned up."""
    intermediates = []
    # Chunk WAVs
    intermediates.extend(output_dir.glob("chunk_*.wav"))
    # TTS segment WAVs
    intermediates.extend(output_dir.glob(f"tts_{target_lang}_*_tts_*.wav"))
    return intermediates


def _process_chunk(i: int, chunk: Path, source_lang: str, target_lang: str,
                   speaker: str, output_dir: Path) -> tuple[int, str, str, list[Path]]:
    """Process a single chunk: STT → normalize → translate → TTS.

    Returns (chunk_index, src_text, tgt_text, tts_files).
    Thread-safe — each chunk uses its own file paths.
    """
    cache_src = output_dir / f"transcript_src_{i:03d}.txt"
    cache_tgt = output_dir / f"transcript_tgt_{target_lang}_{i:03d}.txt"

    # STT
    if cache_src.exists():
        src_text = cache_src.read_text(encoding="utf-8")
        log.info(f"Chunk {i}: STT (cached)")
    else:
        log.info(f"Chunk {i}: STT transcribing...")
        src_text = transcribe(chunk, source_lang)
        src_text = numbers_to_words(src_text)
        cache_src.write_text(src_text, encoding="utf-8")

    # Translate
    if cache_tgt.exists():
        tgt_text = cache_tgt.read_text(encoding="utf-8")
        log.info(f"Chunk {i}: Translate (cached)")
    else:
        log.info(f"Chunk {i}: translating...")
        tgt_text = translate(src_text, source_lang, target_lang)
        cache_tgt.write_text(tgt_text, encoding="utf-8")

    # TTS
    log.info(f"Chunk {i}: generating TTS...")
    tts_files = tts(tgt_text, target_lang, speaker,
                    output_dir / f"tts_{target_lang}_{i:03d}")
    log.info(f"Chunk {i}: done ({len(tts_files)} TTS segments)")

    return i, src_text, tgt_text, tts_files


def run_pipeline(video_path: Path, source_lang: str, target_lang: str,
                 speaker: str, output_dir: Path, keep_intermediates: bool = False,
                 workers: int = 1):

    step(1, "Extracting audio")
    audio_path, duration = extract_audio(video_path, output_dir)

    step(2, "Splitting audio into chunks")
    chunks = split_audio(audio_path, duration, output_dir)

    n_chunks = len(chunks)
    effective_workers = min(workers, n_chunks)

    if effective_workers > 1:
        step(3, f"STT → Translate → TTS  ({n_chunks} chunk(s), {effective_workers} workers)")
        # Parallel processing — results collected by chunk index for correct ordering
        results = {}
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {
                executor.submit(_process_chunk, i, chunk, source_lang,
                                target_lang, speaker, output_dir): i
                for i, chunk in enumerate(chunks)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    log.error(f"Chunk {idx} failed: {e}")
                    raise

        # Reassemble in order
        transcripts_src = []
        transcripts_tgt = []
        all_tts_files = []
        for i in range(n_chunks):
            _, src_text, tgt_text, tts_files = results[i]
            transcripts_src.append(src_text)
            transcripts_tgt.append(tgt_text)
            all_tts_files.extend(tts_files)
            print(f"  Chunk {i+1}: SRC={src_text[:60]}... | TTS={len(tts_files)} segs")
    else:
        step(3, f"STT → Translate → TTS  ({n_chunks} chunk(s))")
        all_tts_files = []
        transcripts_src, transcripts_tgt = [], []

        for i, chunk in enumerate(chunks):
            print(f"\n  Chunk {i+1}/{n_chunks} ───────────────────")

            cache_src = output_dir / f"transcript_src_{i:03d}.txt"
            cache_tgt = output_dir / f"transcript_tgt_{target_lang}_{i:03d}.txt"

            # STT
            if cache_src.exists():
                src_text = cache_src.read_text(encoding="utf-8")
                print("  → STT: (cached)")
            else:
                print("  → STT: transcribing...")
                src_text = transcribe(chunk, source_lang)
                src_text = numbers_to_words(src_text)
                cache_src.write_text(src_text, encoding="utf-8")
            print(f"  → SRC: {src_text[:100]}...")
            transcripts_src.append(src_text)

            # Translate
            if cache_tgt.exists():
                tgt_text = cache_tgt.read_text(encoding="utf-8")
                print("  → Translate: (cached)")
            else:
                print("  → Translate: translating...")
                tgt_text = translate(src_text, source_lang, target_lang)
                cache_tgt.write_text(tgt_text, encoding="utf-8")
            print(f"  → TGT: {tgt_text[:100]}...")
            transcripts_tgt.append(tgt_text)

            # TTS
            print("  → TTS: generating speech...")
            tts_files = tts(tgt_text, target_lang, speaker,
                            output_dir / f"tts_{target_lang}_{i:03d}")
            all_tts_files.extend(tts_files)
            print(f"  → TTS: {len(tts_files)} segment(s)")

    # Save full transcripts (language-keyed)
    (output_dir / "transcript_source.txt").write_text(
        "\n\n".join(transcripts_src), encoding="utf-8")
    (output_dir / f"transcript_{target_lang}.txt").write_text(
        "\n\n".join(transcripts_tgt), encoding="utf-8")

    step(4, "Concatenating TTS audio")
    dubbed_audio = output_dir / f"dubbed_audio_{target_lang}.wav"
    result = concat_audio(all_tts_files, dubbed_audio)
    if not result:
        print("✗ TTS produced no audio. Check API key or speaker name.")
        sys.exit(1)
    print(f"  → Dubbed audio: {dubbed_audio}")

    step(5, "Merging dubbed audio into video")
    lang_name = LANGUAGES[target_lang][0].lower()
    final_video = output_dir / f"dubbed_{lang_name}.mp4"
    merge_audio_video(video_path, dubbed_audio, final_video)

    step(6, "Validating dubbed audio")
    original_transcript = " ".join(transcripts_src)
    original_audio = output_dir / "audio_full.wav"
    val_results = validate(
        original_audio=original_audio,
        dubbed_audio=dubbed_audio,
        original_transcript=original_transcript,
        target_lang=target_lang,
        source_lang=source_lang,
    )
    print_report(val_results)

    # Cleanup intermediate files
    if not keep_intermediates:
        intermediates = _collect_intermediates(output_dir, target_lang)
        if intermediates:
            cleaned = sum(f.stat().st_size for f in intermediates if f.exists())
            for f in intermediates:
                f.unlink(missing_ok=True)
            log.info(f"Cleaned up {len(intermediates)} intermediate files ({cleaned // 1024} KB)")

    print("\n" + "=" * 60)
    print("✅  DONE!")
    print(f"   Output video  : {final_video}")
    print(f"   Source text   : {output_dir / 'transcript_source.txt'}")
    print(f"   Target text   : {output_dir / f'transcript_{target_lang}.txt'}")
    print(f"   Validation    : {val_results['verdict']}")
    print("=" * 60)
    return final_video


def main():
    parser = argparse.ArgumentParser(description="Dub a YouTube video into any Indian language")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url",  help="YouTube video URL")
    group.add_argument("--file", help="Local video file path")

    parser.add_argument("--source",  default="en-IN",
                        help="Source language code (default: en-IN)")
    parser.add_argument("--target",  required=True,
                        help=f"Target language code. Options: {', '.join(LANGUAGES)}")
    parser.add_argument("--speaker", default=None,
                        help="TTS speaker name (auto-selected if not set)")
    parser.add_argument("--output",  default=None,
                        help="Output directory (default: output/<video_title>)")
    parser.add_argument("--keep-intermediates", action="store_true",
                        help="Keep intermediate files (chunks, TTS segments) for debugging")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel workers for chunk processing (default: 4)")

    args = parser.parse_args()

    # Validate languages
    if args.source not in LANGUAGES:
        print(f"✗ Unknown source language: {args.source}")
        print(f"  Valid options: {', '.join(LANGUAGES)}")
        sys.exit(1)
    if args.target not in LANGUAGES:
        print(f"✗ Unknown target language: {args.target}")
        print(f"  Valid options: {', '.join(LANGUAGES)}")
        sys.exit(1)

    # Auto-select speaker if not provided
    speaker = args.speaker or LANGUAGES[args.target][1]
    if not speaker:
        print(f"✗ No default speaker for {args.target}. Provide --speaker manually.")
        sys.exit(1)

    src_name = LANGUAGES[args.source][0]
    tgt_name = LANGUAGES[args.target][0]
    print("=" * 60)
    print("  YT Dubber")
    print(f"  {src_name} → {tgt_name}  |  Speaker: {speaker}  |  Workers: {args.workers}")
    print("=" * 60)

    # Get video file — each download gets a unique temp dir to prevent race conditions
    if args.url:
        print(f"\nDownloading: {args.url}")
        job_id = uuid.uuid4().hex[:8]
        download_dir = Path("output") / "download" / f"job_{job_id}"
        video_path, title = download_video(args.url, download_dir)
        output_dir = Path(args.output) if args.output else (
            Path("output") / title[:50].replace(" ", "_").replace("/", "_")
        )
        # Move video to final output dir
        output_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = output_dir / "source.mp4"
        if not final_video_path.exists():
            video_path.rename(final_video_path)
        video_path = final_video_path
        # Clean up empty download dir
        try:
            download_dir.rmdir()
        except OSError:
            pass
    else:
        video_path = Path(args.file)
        if not video_path.exists():
            print(f"✗ File not found: {args.file}")
            sys.exit(1)
        output_dir = Path(args.output or f"output/{video_path.stem}")
        output_dir.mkdir(parents=True, exist_ok=True)

    try:
        run_pipeline(video_path, args.source, args.target, speaker, output_dir,
                     keep_intermediates=args.keep_intermediates,
                     workers=args.workers)
    except APIError as e:
        log.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
