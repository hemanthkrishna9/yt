#!/usr/bin/env python3
"""
Story Shorts — Generate YouTube Shorts from stories.

Usage:
  python story.py --text "Once upon a time..." --lang te-IN
  python story.py --theme aesop               --lang hi-IN --mood dramatic
  python story.py --theme panchatantra        --lang te-IN --no-upload
  python story.py --theme tenali              --lang ta-IN --speaker kavya
  python story.py --theme xyz                 --lang en-IN   # → no results
"""

import argparse
import json
import sys
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


def step(n: int, msg: str):
    print(f"\n{'─'*60}\n[Step {n}] {msg}\n{'─'*60}")


def run_pipeline(
    story_text: str,
    story_title: str,
    target_lang: str,
    speaker: str,
    mood: str,
    output_dir: Path,
    no_upload: bool,
) -> Path:

    # ── Step 1: Gemini scene breakdown ──────────────────────────────────────
    step(1, "Breaking story into scenes (Gemini)")
    breakdown_cache = output_dir / "breakdown.json"
    if breakdown_cache.exists():
        print("  → Breakdown cached")
        from pipeline.formatter import StoryBreakdown
        breakdown = StoryBreakdown.model_validate_json(breakdown_cache.read_text())
    else:
        breakdown = breakdown_story(story_text, target_lang)
        breakdown_cache.write_text(breakdown.model_dump_json(indent=2), encoding="utf-8")

    print(f"  → Title: {breakdown.title}")
    print(f"  → Scenes: {len(breakdown.scenes)}")
    print(f"  → Moral: {breakdown.moral}")

    scenes = breakdown.scenes

    # ── Step 2: Generate images ──────────────────────────────────────────────
    step(2, f"Generating {len(scenes)} scene images (Imagen 3)")
    images = []
    for scene in scenes:
        img = generate_scene_image(scene.image_prompt, scene.scene_number, output_dir)
        images.append(img)

    # ── Step 3: TTS narration ────────────────────────────────────────────────
    step(3, f"Narrating scenes in {LANGUAGES[target_lang][0]} (Sarvam TTS)")
    narrations = narrate_scenes(scenes, target_lang, speaker, mood, output_dir)
    # narrations = [(wav_path, duration), ...]

    # ── Step 4: Build scene clips (Ken Burns) ────────────────────────────────
    step(4, "Building scene clips with Ken Burns effect (FFmpeg)")
    clips = []
    durations = []
    for scene, img, (wav, dur) in zip(scenes, images, narrations):
        clip = make_scene_clip(img, wav, dur, scene.scene_number, output_dir)
        clips.append(clip)
        durations.append(dur)

    # ── Step 5: Stitch clips + subtitles ────────────────────────────────────
    step(5, "Stitching clips + burning subtitles")
    stitched = stitch_clips(clips, durations, output_dir)
    srt = generate_srt(scenes, durations, output_dir)
    final_video = burn_subtitles(stitched, srt, output_dir)

    total_dur = sum(durations)
    print(f"  → Final video: {final_video.name} ({total_dur:.1f}s)")

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
    group.add_argument("--theme", help=f"Auto-fetch theme. Options: aesop, panchatantra, tenali, jataka, vikram")

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
    print(f"  Language: {lang_name}  |  Speaker: {speaker}  |  Mood: {args.mood}")
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
            print(f"   Available themes: aesop, panchatantra, tenali, jataka, vikram")
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

    run_pipeline(
        story_text=story_text,
        story_title=story_title,
        target_lang=args.lang,
        speaker=speaker,
        mood=args.mood,
        output_dir=output_dir,
        no_upload=args.no_upload,
    )


if __name__ == "__main__":
    main()
