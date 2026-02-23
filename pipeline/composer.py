"""
FFmpeg video composition:
  1. Ken Burns effect per scene image
  2. Each image + narration audio → scene clip
  3. All clips stitched with xfade crossfade
  4. SRT subtitle generation
  5. Subtitle burn into final video
"""

import random
import shutil
import subprocess
from pathlib import Path

FPS        = 24
FADE_DUR   = 0.5   # crossfade duration between clips (seconds)
RESOLUTION = "1080x1920"  # 9:16 for Shorts


def _run(args: list[str]):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error:\n{result.stderr[-800:]}")
    return result


# Ken Burns motion presets — randomly assigned per scene for variety
_KB_PRESETS = [
    # zoom in from center
    "z='min(zoom+0.0007,1.3)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # zoom out from center
    "z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.0010))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # pan left to right
    "z='1.2':x='iw*0.1+on*iw*0.0003':y='ih/2-(ih/zoom/2)'",
    # pan right to left
    "z='1.2':x='iw*0.2-on*iw*0.0003':y='ih/2-(ih/zoom/2)'",
    # pan top to bottom
    "z='1.2':x='iw/2-(iw/zoom/2)':y='ih*0.05+on*ih*0.0003'",
]


def make_scene_clip(
    image_path: Path,
    audio_path: Path,
    duration: float,
    scene_index: int,
    output_dir: Path,
) -> Path:
    """Build one scene clip: Ken Burns image + narration audio."""
    out = output_dir / f"clip_{scene_index:02d}.mp4"
    if out.exists():
        print(f"  → Clip {scene_index:02d}: cached")
        return out

    frames = int((duration + 0.5) * FPS)
    kb = random.choice(_KB_PRESETS)

    vf = (
        f"scale=4000:-1,"
        f"zoompan={kb}:d={frames}:s={RESOLUTION}:fps={FPS},"
        f"format=yuv420p"
    )

    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(FPS), "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration + 0.2),
        "-shortest",
        str(out),
    ])
    print(f"  → Clip {scene_index:02d}: created ({duration:.1f}s)")
    return out


def stitch_clips(clip_paths: list[Path], durations: list[float], output_dir: Path) -> Path:
    """Chain clips with xfade dissolve transitions."""
    out = output_dir / "stitched.mp4"
    n = len(clip_paths)

    if n == 1:
        shutil.copy(clip_paths[0], out)
        return out

    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]

    vfilter_parts = []
    afilter_parts = []
    cumulative = 0.0
    last_v = "0:v"
    last_a = "0:a"

    for i in range(1, n):
        offset = cumulative + durations[i - 1] - FADE_DUR
        cumulative = offset + FADE_DUR
        nv = f"v{i}"
        na = f"a{i}"
        vfilter_parts.append(
            f"[{last_v}][{i}:v]xfade=transition=dissolve:"
            f"duration={FADE_DUR}:offset={offset:.3f}[{nv}]"
        )
        afilter_parts.append(
            f"[{last_a}][{i}:a]acrossfade=d={FADE_DUR}[{na}]"
        )
        last_v = nv
        last_a = na

    filter_complex = ";".join(vfilter_parts + afilter_parts)

    # Save filter for debugging
    (output_dir / "filter_complex.txt").write_text(filter_complex)

    _run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{last_v}]", "-map", f"[{last_a}]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(out),
    ])
    return out


def _fmt_srt_time(secs: float) -> str:
    h  = int(secs // 3600)
    m  = int((secs % 3600) // 60)
    s  = int(secs % 60)
    ms = int((secs - int(secs)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str, max_chars: int = 38) -> str:
    """Wrap long lines for subtitle readability."""
    words = text.split()
    lines, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 <= max_chars:
            line += ("" if not line else " ") + w
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return "\n".join(lines)


def generate_srt(scenes: list, durations: list[float], output_dir: Path) -> Path:
    """Generate SRT subtitle file from scenes + timing."""
    srt_path = output_dir / "subtitles.srt"
    lines = []
    t = 0.0
    for i, (scene, dur) in enumerate(zip(scenes, durations)):
        start = _fmt_srt_time(t)
        end   = _fmt_srt_time(t + dur - 0.1)
        text  = _wrap(scene.narration)
        lines.append(f"{i + 1}\n{start} --> {end}\n{text}\n")
        t += dur - FADE_DUR  # account for xfade overlap
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return srt_path


def burn_subtitles(video_path: Path, srt_path: Path, output_dir: Path) -> Path:
    """Burn SRT subtitles into video."""
    out = output_dir / "short.mp4"
    style = (
        "FontSize=16,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=40"
    )
    # Escape path for ffmpeg subtitles filter
    srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")
    _run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"subtitles={srt_escaped}:force_style='{style}'",
        "-c:a", "copy",
        str(out),
    ])
    return out
