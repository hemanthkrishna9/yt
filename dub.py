#!/usr/bin/env python3
"""
YT Dubber — YouTube video dubbing CLI
Usage:
  python dub.py --url  "https://youtube.com/shorts/..."  --target te-IN
  python dub.py --file /path/to/video.mp4               --target hi-IN
  python dub.py --url  "..."  --source en-IN --target ta-IN --speaker thendral
"""

import argparse
import sys
from pathlib import Path

from config import LANGUAGES
from pipeline.downloader import download_video
from pipeline.audio import extract_audio, split_audio, concat_audio, merge_audio_video
from pipeline.stt import transcribe
from pipeline.normalize import numbers_to_words
from pipeline.translate import translate
from pipeline.tts import tts
from pipeline.validate import validate, print_report


def step(n: int, msg: str):
    print(f"\n{'─'*60}\n[Step {n}] {msg}\n{'─'*60}")


def run_pipeline(video_path: Path, source_lang: str, target_lang: str,
                 speaker: str, output_dir: Path):

    step(1, "Extracting audio")
    audio_path, duration = extract_audio(video_path, output_dir)

    step(2, "Splitting audio into chunks")
    chunks = split_audio(audio_path, duration, output_dir)

    step(3, f"STT → Translate → TTS  ({len(chunks)} chunk(s))")
    all_tts_files = []
    transcripts_src, transcripts_tgt = [], []

    for i, chunk in enumerate(chunks):
        print(f"\n  Chunk {i+1}/{len(chunks)} ───────────────────")

        cache_src = output_dir / f"transcript_src_{i:03d}.txt"
        cache_tgt = output_dir / f"transcript_tgt_{target_lang}_{i:03d}.txt"

        # STT
        if cache_src.exists():
            src_text = cache_src.read_text(encoding="utf-8")
            print("  → STT: (cached)")
        else:
            print("  → STT: transcribing...")
            src_text = transcribe(chunk, source_lang)
            src_text = numbers_to_words(src_text)  # "2003" → "two thousand and three"
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

        # TTS (language-keyed to avoid cross-language cache collision)
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
    print(f"  {src_name} → {tgt_name}  |  Speaker: {speaker}")
    print("=" * 60)

    # Get video file
    if args.url:
        print(f"\nDownloading: {args.url}")
        base_output = Path("output") / "download"
        video_path, title = download_video(args.url, base_output)
        output_dir = Path("output") / title[:50].replace(" ", "_").replace("/", "_")
        # Move video to final output dir
        output_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = output_dir / "source.mp4"
        if not final_video_path.exists():
            video_path.rename(final_video_path)
        video_path = final_video_path
    else:
        video_path = Path(args.file)
        if not video_path.exists():
            print(f"✗ File not found: {args.file}")
            sys.exit(1)
        output_dir = Path(args.output or f"output/{video_path.stem}")
        output_dir.mkdir(parents=True, exist_ok=True)

    run_pipeline(video_path, args.source, args.target, speaker, output_dir)


if __name__ == "__main__":
    main()
