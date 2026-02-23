"""
Per-scene TTS narration with mood-based pace.
"""

from pathlib import Path

from pipeline.audio import concat_audio, get_duration
from pipeline.tts import tts
from pipeline.normalize import numbers_to_words
from config import MOOD_PACE


def narrate_scenes(
    scenes: list,
    target_lang: str,
    speaker: str,
    mood: str,
    output_dir: Path,
) -> list[tuple[Path, float]]:
    """
    Generate one WAV per scene.
    Returns list of (wav_path, duration_seconds).
    """
    pace = MOOD_PACE.get(mood, 1.0)
    print(f"  → Mood: {mood} | Pace: {pace}x")
    results = []

    for scene in scenes:
        scene_num = scene.scene_number
        cache_path = output_dir / f"scene_{scene_num:02d}_narration.wav"

        if cache_path.exists():
            dur = get_duration(cache_path)
            print(f"  → Scene {scene_num:02d}: narration cached ({dur:.1f}s)")
            results.append((cache_path, dur))
            continue

        text = numbers_to_words(scene.narration)
        wav_files = tts(
            text=text,
            target_lang=target_lang,
            speaker=speaker,
            out_base=output_dir / f"narration_{scene_num:02d}",
            pace=pace,
        )

        if not wav_files:
            raise RuntimeError(f"TTS produced no audio for scene {scene_num}")

        # Merge multi-batch TTS into single file
        if len(wav_files) > 1:
            concat_audio(wav_files, cache_path)
        else:
            wav_files[0].rename(cache_path)

        dur = get_duration(cache_path)
        print(f"  → Scene {scene_num:02d}: narration generated ({dur:.1f}s)")
        results.append((cache_path, dur))

    return results
