#!/usr/bin/env python3
"""
Story Shorts — Generate YouTube Shorts from stories.

Usage:
  python story.py --text "Once upon a time..." --lang te-IN
  python story.py --theme aesop               --lang hi-IN --mood dramatic
  python story.py --theme panchatantra        --lang te-IN --no-upload
  python story.py --theme tenali              --lang ta-IN --speaker kavya
  python story.py --theme aesop --lang hi-IN --workers 4   # parallel scenes
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from config import LANGUAGES, MOOD_PACE
from pipeline.scraper import fetch_story
from pipeline.formatter import breakdown_story
from pipeline.imager import generate_scene_image
from pipeline.narrator import narrate_scenes
from pipeline.composer import make_scene_clip, stitch_clips, generate_srt, burn_subtitles
from pipeline.validate import validate_short, print_report
from pipeline.publisher import upload_short
from pipeline.log import get_logger
from pipeline.retry import APIError

log = get_logger(__name__)


def step(n: int, msg: str):
    print(f"\n{'─'*60}\n[Step {n}] {msg}\n{'─'*60}")


def _collect_intermediates(output_dir: Path) -> list[Path]:
    """Collect intermediate files that can be cleaned up."""
    intermediates = []
    # TTS segment WAVs (intermediate batches)
    intermediates.extend(output_dir.glob("narration_*_tts_*.wav"))
    # Individual scene clips (kept as stitched.mp4 -> short.mp4)
    intermediates.extend(output_dir.glob("clip_*.mp4"))
    # Stitched video (short.mp4 is the final)
    stitched = output_dir / "stitched.mp4"
    if stitched.exists():
        intermediates.append(stitched)
    # Filter complex debug file
    fc = output_dir / "filter_complex.txt"
    if fc.exists():
        intermediates.append(fc)
    return intermediates


def run_pipeline(
    story_text: str,
    story_title: str,
    target_lang: str,
    speaker: str,
    mood: str,
    output_dir: Path,
    no_upload: bool,
    keep_intermediates: bool = False,
    workers: int = 1,
) -> Path:

    # ── Step 1: Gemini scene breakdown ──────────────────────────────────────
    step(1, "Breaking story into scenes (Gemini)")
    breakdown_cache = output_dir / "breakdown.json"
    if breakdown_cache.exists():
        print("  -> Breakdown cached")
        from pipeline.formatter import StoryBreakdown
        breakdown = StoryBreakdown.model_validate_json(breakdown_cache.read_text())
    else:
        breakdown = breakdown_story(story_text, target_lang)
        breakdown_cache.write_text(breakdown.model_dump_json(indent=2), encoding="utf-8")

    print(f"  -> Title: {breakdown.title}")
    print(f"  -> Scenes: {len(breakdown.scenes)}")
    print(f"  -> Moral: {breakdown.moral}")

    scenes = breakdown.scenes
    n_scenes = len(scenes)
    effective_workers = min(workers, n_scenes)

    # ── Step 2: Generate images (parallelizable) ─────────────────────────────
    step(2, f"Generating {n_scenes} scene images (Imagen 3)"
         + (f" [{effective_workers} workers]" if effective_workers > 1 else ""))
    if effective_workers > 1:
        images = [None] * n_scenes
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {
                executor.submit(generate_scene_image, s.image_prompt,
                                s.scene_number, output_dir): i
                for i, s in enumerate(scenes)
            }
            for future in as_completed(futures):
                idx = futures[future]
                images[idx] = future.result()
    else:
        images = []
        for scene in scenes:
            img = generate_scene_image(scene.image_prompt, scene.scene_number, output_dir)
            images.append(img)

    # ── Step 3: TTS narration (parallelizable per scene) ──────────────────────
    step(3, f"Narrating scenes in {LANGUAGES[target_lang][0]} (Sarvam TTS)"
         + (f" [{effective_workers} workers]" if effective_workers > 1 else ""))
    narrations = narrate_scenes(scenes, target_lang, speaker, mood, output_dir,
                                workers=effective_workers)
    # narrations = [(wav_path, duration), ...]

    # ── Step 4: Build scene clips (Ken Burns, parallelizable) ─────────────────
    step(4, "Building scene clips with Ken Burns effect (FFmpeg)"
         + (f" [{effective_workers} workers]" if effective_workers > 1 else ""))
    if effective_workers > 1:
        clip_results = [None] * n_scenes
        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            futures = {}
            for i, (scene, img, (wav, dur)) in enumerate(zip(scenes, images, narrations)):
                future = executor.submit(make_scene_clip, img, wav, dur,
                                         scene.scene_number, output_dir)
                futures[future] = (i, dur)
            for future in as_completed(futures):
                idx, dur = futures[future]
                clip_results[idx] = (future.result(), dur)
        clips = [r[0] for r in clip_results]
        durations = [r[1] for r in clip_results]
    else:
        clips = []
        durations = []
        for scene, img, (wav, dur) in zip(scenes, images, narrations):
            clip = make_scene_clip(img, wav, dur, scene.scene_number, output_dir)
            clips.append(clip)
            durations.append(dur)

    # ── Step 5: Stitch clips + subtitles (sequential — depends on all clips) ──
    step(5, "Stitching clips + burning subtitles")
    stitched = stitch_clips(clips, durations, output_dir)
    srt = generate_srt(scenes, durations, output_dir)
    final_video = burn_subtitles(stitched, srt, output_dir)

    total_dur = sum(durations)
    print(f"  -> Final video: {final_video.name} ({total_dur:.1f}s)")

    # ── Step 6: Validate ────────────────────────────────────────────────────
    step(6, "Validating output video")
    val = validate_short(final_video)
    print_report(val)

    if not val["passed"]:
        print("⚠ Validation failed — video may have issues. Review before uploading.")

    # ── Step 7: YouTube upload ───────────────────────────────────────────────
    if no_upload:
        print("\n⏭  Skipping YouTube upload (--no-upload)")
    else:
        step(7, "Uploading to YouTube (private)")
        url = upload_short(
            video_path=final_video,
            title=breakdown.youtube_title,
            description=breakdown.youtube_description,
            tags=breakdown.youtube_tags,
        )
        (output_dir / "youtube_url.txt").write_text(url)

    # Cleanup intermediate files
    if not keep_intermediates:
        intermediates = _collect_intermediates(output_dir)
        if intermediates:
            cleaned = sum(f.stat().st_size for f in intermediates if f.exists())
            for f in intermediates:
                f.unlink(missing_ok=True)
            log.info(f"Cleaned up {len(intermediates)} intermediate files ({cleaned // 1024} KB)")

    print("\n" + "=" * 60)
    print("✅  DONE!")
    print(f"   Video         : {final_video}")
    print(f"   Subtitles     : {srt}")
    print(f"   Breakdown     : {breakdown_cache}")
    print(f"   Validation    : {val['verdict']}")
    if not no_upload:
        url_file = output_dir / "youtube_url.txt"
        if url_file.exists():
            print(f"   YouTube URL   : {url_file.read_text()}")
    print("=" * 60)

    return final_video


def main():
    parser = argparse.ArgumentParser(
        description="Generate YouTube Shorts from stories"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text",  help="Story text (paste directly)")
    group.add_argument("--theme", help="Auto-fetch theme. Options: aesop, panchatantra, tenali, jataka, vikram")

    parser.add_argument("--lang",      required=True,
                        help=f"Target language. Options: {', '.join(LANGUAGES)}")
    parser.add_argument("--speaker",   default=None,
                        help="TTS speaker name (auto-selected if not set)")
    parser.add_argument("--mood",      default="default",
                        help=f"Voice mood. Options: {', '.join(MOOD_PACE)}  (default: default)")
    parser.add_argument("--keyword",   default=None,
                        help="Filter keyword when using --theme (optional)")
    parser.add_argument("--no-upload", action="store_true",
                        help="Skip YouTube upload, produce local file only")
    parser.add_argument("--output",    default=None,
                        help="Output directory override")
    parser.add_argument("--keep-intermediates", action="store_true",
                        help="Keep intermediate files (clips, TTS segments) for debugging")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel workers for scene processing (default: 4)")

    args = parser.parse_args()

    # Validate language
    if args.lang not in LANGUAGES:
        print(f"✗ Unknown language: {args.lang}")
        print(f"  Valid options: {', '.join(LANGUAGES)}")
        sys.exit(1)

    # Validate mood
    if args.mood not in MOOD_PACE:
        print(f"✗ Unknown mood: {args.mood}")
        print(f"  Valid options: {', '.join(MOOD_PACE)}")
        sys.exit(1)

    speaker = args.speaker or LANGUAGES[args.lang][1]
    if not speaker:
        print(f"✗ No default speaker for {args.lang}. Use --speaker.")
        sys.exit(1)

    lang_name = LANGUAGES[args.lang][0]
    print("=" * 60)
    print("  Story Shorts")
    print(f"  Language: {lang_name}  |  Speaker: {speaker}  |  Mood: {args.mood}  |  Workers: {args.workers}")
    print("=" * 60)

    # ── Get story text ───────────────────────────────────────────────────────
    if args.text:
        story_text  = args.text.strip()
        story_title = "custom_story"
        print(f"\n  Story: {story_text[:80]}...")
    else:
        print(f"\n  Fetching '{args.theme}' story...")
        story_text, story_title = fetch_story(args.theme, args.keyword)
        if not story_text:
            print(f"\n❌  No results found for theme: '{args.theme}'")
            if args.keyword:
                print(f"   Keyword filter: '{args.keyword}'")
            print("   Available themes: aesop, panchatantra, tenali, jataka, vikram")
            sys.exit(0)
        print(f"  Story: {story_title}")
        print(f"  Text:  {story_text[:100]}...")

    # ── Setup output dir ─────────────────────────────────────────────────────
    if args.output:
        output_dir = Path(args.output)
    else:
        slug = story_title[:30].replace(" ", "_").replace("/", "_")
        ts   = datetime.now().strftime("%m%d_%H%M")
        output_dir = Path(f"output/story_{slug}_{ts}")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "story_text.txt").write_text(story_text, encoding="utf-8")

    try:
        run_pipeline(
            story_text=story_text,
            story_title=story_title,
            target_lang=args.lang,
            speaker=speaker,
            mood=args.mood,
            output_dir=output_dir,
            no_upload=args.no_upload,
            keep_intermediates=args.keep_intermediates,
            workers=args.workers,
        )
    except APIError as e:
        log.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
