"""In-memory job store + background thread runner."""

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from server.progress import ProgressCapture


@dataclass
class JobState:
    id: str
    type: str  # "dub" or "story"
    status: str = "queued"  # queued | running | completed | failed
    progress: ProgressCapture = field(default_factory=ProgressCapture)
    output_path: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    user_id: int | None = None


_jobs: dict[str, JobState] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> JobState | None:
    with _lock:
        return _jobs.get(job_id)


def list_jobs() -> list[JobState]:
    with _lock:
        return list(_jobs.values())


def submit_job(job_type: str, run_fn, kwargs: dict, user_id: int | None = None) -> str:
    """Create a job and run `run_fn(**kwargs)` in a background thread.

    `run_fn` must return a Path (the output video file).
    """
    job_id = uuid.uuid4().hex[:12]
    job = JobState(id=job_id, type=job_type, user_id=user_id)

    with _lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=_run_job, args=(job, run_fn, kwargs), daemon=True
    )
    thread.start()
    return job_id


def _run_job(job: JobState, run_fn, kwargs: dict):
    job.status = "running"
    try:
        with job.progress:
            result = run_fn(**kwargs)
        if isinstance(result, Path):
            job.output_path = str(result)
        elif isinstance(result, str):
            job.output_path = result
        job.status = "completed"
    except Exception as e:
        job.error = f"{type(e).__name__}: {e}"
        job.status = "failed"
        traceback.print_exc()
