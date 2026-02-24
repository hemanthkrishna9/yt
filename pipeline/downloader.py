"""Download video from YouTube URL or use a local file."""

import yt_dlp
from pathlib import Path

from pipeline.log import get_logger

log = get_logger(__name__)


def download_video(url: str, output_dir: Path) -> tuple[Path, str]:
    """
    Download a YouTube video to output_dir.
    Returns (video_path, title).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "video")

    video_path = output_dir / "source.mp4"
    if not video_path.exists():
        raise FileNotFoundError(f"Download failed — file not found: {video_path}")

    log.info(f"Downloaded: {title}")
    return video_path, title
