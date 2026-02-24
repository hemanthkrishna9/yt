import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from server.auth.deps import get_current_user, get_user_from_query
from server.schemas import JobResponse
from server import jobs

router = APIRouter()


def _check_ownership(job: jobs.JobState, user_id: int):
    if job.user_id is not None and job.user_id != user_id:
        raise HTTPException(403, "Not your job")


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _check_ownership(job, user["user_id"])
    return JobResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress.lines[:],
        output_path=job.output_path,
        error=job.error,
    )


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, user: dict = Depends(get_user_from_query)):
    """SSE endpoint streaming progress lines in real-time."""
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _check_ownership(job, user["user_id"])

    async def event_stream():
        sent = 0
        while True:
            lines = job.progress.lines[:]
            if len(lines) > sent:
                for line in lines[sent:]:
                    yield f"data: {line}\n\n"
                sent = len(lines)

            if job.status in ("completed", "failed"):
                if job.status == "failed" and job.error:
                    yield f"event: error\ndata: {job.error}\n\n"
                yield f"event: done\ndata: {job.status}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/jobs/{job_id}/download")
def download_job(job_id: str, user: dict = Depends(get_user_from_query)):
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    _check_ownership(job, user["user_id"])
    if job.status != "completed" or not job.output_path:
        raise HTTPException(400, "Job not completed or no output available")
    return FileResponse(
        job.output_path,
        media_type="video/mp4",
        filename=f"{job.type}_{job_id}.mp4",
    )
