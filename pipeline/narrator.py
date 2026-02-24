"""
Per-scene TTS narration with mood-based pace.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pipeline.audio import concat_audio, get_duration
from pipeline.tts import tts
from pipeline.normalize import numbers_to_words
from pipeline.log import get_logger
from config import MOOD_PACE

log = get_logger(__name__)


def _narrate_one_scene(
    scene, target_lang: str, speaker: str, pace: float, output_dir: Path
) -> tuple[int, Path, float]:
    """Narrate a single scene. Thread-safe — uses per-scene file paths.

    Returns (scene_number, wav_path, duration).
    """
    scene_num = scene.scene_number
    cache_path = output_dir / f"scene_{scene_num:02d}_narration.wav"

    if cache_path.exists():
        dur = get_duration(cache_path)
        log.info(f"Scene {scene_num:02d}: narration cached ({dur:.1f}s)")
        return scene_num, cache_path, dur

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
    log.info(f"Scene {scene_num:02d}: narration generated ({dur:.1f}s)")
    return scene_num, cache_path, dur


def narrate_scenes(
    scenes: list,
    target_lang: str,
    speaker: str,
    mood: str,
    output_dir: Path,
    workers: int = 1,
) -> list[tuple[Path, float]]:
    """
    Generate one WAV per scene.
    Returns list of (wav_path, duration_seconds) in scene order.

    Args:
        workers: Number of parallel threads for TTS generation.

    Raises RuntimeError/APIError if TTS fails for any scene.
    """
    pace = MOOD_PACE.get(mood, 1.0)
    log.info(f"Mood: {mood} | Pace: {pace}x")

    if workers > 1:
        # Parallel narration — each scene uses its own file paths, no conflicts
        results_map = {}
        with ThreadPoolExecutor(max_workers=min(workers, len(scenes))) as executor:
            futures = {
                executor.submit(
                    _narrate_one_scene, scene, target_lang, speaker, pace, output_dir
                ): scene.scene_number
                for scene in scenes
            }
            for future in as_completed(futures):
                scene_num = futures[future]
                try:
                    num, path, dur = future.result()
                    results_map[num] = (path, dur)
                except Exception as e:
                    log.error(f"Scene {scene_num} narration failed: {e}")
                    raise

        # Return in scene order
        return [results_map[s.scene_number] for s in scenes]
    else:
        # Sequential (original behavior)
        results = []
        for scene in scenes:
            _, path, dur = _narrate_one_scene(
                scene, target_lang, speaker, pace, output_dir
            )
            results.append((path, dur))
        return results
