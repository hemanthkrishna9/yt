"""Audio extraction, splitting, and merging using ffmpeg."""

import json
import math
import subprocess
from pathlib import Path

from config import CHUNK_SECS


def run(args: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{result.stderr[-500:]}")
    return result


def get_duration(path: Path) -> float:
    r = run(["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)])
    return float(json.loads(r.stdout)["format"]["duration"])


def extract_audio(video_path: Path, output_dir: Path) -> tuple[Path, float]:
    """Extract mono 16kHz WAV from video."""
    audio_path = output_dir / "audio_full.wav"
    if audio_path.exists():
        print("  → Audio already extracted, skipping")
    else:
        run(["ffmpeg", "-y", "-i", str(video_path),
             "-vn", "-ar", "16000", "-ac", "1", str(audio_path)])
    duration = get_duration(audio_path)
    print(f"  → Duration: {duration / 60:.1f} min")
    return audio_path, duration


def split_audio(audio_path: Path, duration: float, output_dir: Path) -> list[Path]:
    """Split audio into CHUNK_SECS chunks for STT."""
    num_chunks = math.ceil(duration / CHUNK_SECS)
    print(f"  → {num_chunks} chunk(s) of {CHUNK_SECS}s each")
    chunks = []
    for i in range(num_chunks):
        cp = output_dir / f"chunk_{i:03d}.wav"
        if not cp.exists():
            run(["ffmpeg", "-y", "-i", str(audio_path),
                 "-ss", str(i * CHUNK_SECS), "-t", str(CHUNK_SECS),
                 "-ar", "16000", "-ac", "1", str(cp)])
        chunks.append(cp)
    return chunks


def concat_audio(file_list: list[Path], output_path: Path) -> Path | None:
    """Concatenate multiple WAV files into one."""
    if not file_list:
        return None
    list_file = output_path.parent / "_concat_list.txt"
    list_file.write_text("\n".join(f"file '{Path(p).resolve()}'" for p in file_list))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(list_file), "-ar", "22050", "-ac", "1", str(output_path)])
    list_file.unlink()
    return output_path


def merge_audio_video(video_path: Path, audio_path: Path, output_path: Path) -> Path:
    """
    Replace video's audio track with dubbed audio.
    Adjusts video frame speed to exactly match dubbed audio duration:
      - Dubbed audio shorter → video slows down to fill it
      - Dubbed audio longer  → video speeds up to match it
    Result: audio and video always end at exactly the same time.
    """
    video_dur = get_duration(video_path)
    audio_dur = get_duration(audio_path)

    if audio_dur == 0:
        raise RuntimeError("Dubbed audio file is empty")

    # pts_factor > 1 = slow down video, < 1 = speed up video
    pts_factor = audio_dur / video_dur
    print(f"  → Video: {video_dur:.1f}s | Dubbed audio: {audio_dur:.1f}s | "
          f"Video speed: {1/pts_factor:.2f}x")

    run(["ffmpeg", "-y",
         "-i", str(video_path),
         "-i", str(audio_path),
         "-filter:v", f"setpts={pts_factor:.6f}*PTS",  # adjust frame timing
         "-map", "0:v:0",
         "-map", "1:a:0",
         "-shortest",
         str(output_path)])
    return output_path
