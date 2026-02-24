import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from config import LANGUAGES
from server.auth.deps import get_current_user
from server.schemas import DubRequest, JobResponse
from server import jobs

router = APIRouter()


def _run_dub(url: str | None, file_path: str | None, source_lang: str,
             target_lang: str, speaker: str, workers: int) -> Path:
    """Wrapper that handles download + calls dub.run_pipeline."""
    from pipeline.downloader import download_video
    from dub import run_pipeline

    if url:
        job_id = uuid.uuid4().hex[:8]
        download_dir = Path("output") / "download" / f"job_{job_id}"
        video_path, title = download_video(url, download_dir)
        output_dir = Path("output") / title[:50].replace(" ", "_").replace("/", "_")
        output_dir.mkdir(parents=True, exist_ok=True)
        final_video_path = output_dir / "source.mp4"
        if not final_video_path.exists():
            video_path.rename(final_video_path)
        video_path = final_video_path
        try:
            download_dir.rmdir()
        except OSError:
            pass
    else:
        video_path = Path(file_path)
        output_dir = Path(f"output/{video_path.stem}")
        output_dir.mkdir(parents=True, exist_ok=True)

    return run_pipeline(video_path, source_lang, target_lang, speaker,
                        output_dir, workers=workers)


@router.post("/dub", response_model=JobResponse)
def submit_dub(req: DubRequest, user: dict = Depends(get_current_user)):
    if not req.url and not req.file_path:
        raise HTTPException(400, "Provide either url or file_path")
    if req.target_lang not in LANGUAGES:
        raise HTTPException(400, f"Unknown target language: {req.target_lang}")
    if req.source_lang not in LANGUAGES:
        raise HTTPException(400, f"Unknown source language: {req.source_lang}")

    speaker = req.speaker or LANGUAGES[req.target_lang][1]
    if not speaker:
        raise HTTPException(400, f"No default speaker for {req.target_lang}. Provide speaker.")

    job_id = jobs.submit_job("dub", _run_dub, {
        "url": req.url,
        "file_path": req.file_path,
        "source_lang": req.source_lang,
        "target_lang": req.target_lang,
        "speaker": speaker,
        "workers": req.workers,
    }, user_id=user["user_id"])

    return JobResponse(job_id=job_id, status="queued")
