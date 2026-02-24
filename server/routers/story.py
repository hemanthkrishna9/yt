from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from config import LANGUAGES, MOOD_PACE, THEMES
from server.auth.deps import get_current_user
from server.schemas import StoryRequest, JobResponse
from server import jobs

router = APIRouter()


def _run_story(text: str | None, theme: str | None, keyword: str | None,
               target_lang: str, speaker: str, mood: str,
               no_upload: bool, workers: int) -> Path:
    """Wrapper that handles story fetching + calls story.run_pipeline."""
    from pipeline.scraper import fetch_story
    from story import run_pipeline

    if text:
        story_text = text.strip()
        story_title = "custom_story"
    else:
        story_text, story_title = fetch_story(theme, keyword)
        if not story_text:
            raise ValueError(f"No story found for theme '{theme}'")

    slug = story_title[:30].replace(" ", "_").replace("/", "_")
    ts = datetime.now().strftime("%m%d_%H%M")
    output_dir = Path(f"output/story_{slug}_{ts}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "story_text.txt").write_text(story_text, encoding="utf-8")

    return run_pipeline(
        story_text=story_text,
        story_title=story_title,
        target_lang=target_lang,
        speaker=speaker,
        mood=mood,
        output_dir=output_dir,
        no_upload=no_upload,
        workers=workers,
    )


@router.post("/story", response_model=JobResponse)
def submit_story(req: StoryRequest, user: dict = Depends(get_current_user)):
    if not req.text and not req.theme:
        raise HTTPException(400, "Provide either text or theme")
    if req.theme and req.theme not in THEMES:
        raise HTTPException(400, f"Unknown theme: {req.theme}. Options: {THEMES}")
    if req.target_lang not in LANGUAGES:
        raise HTTPException(400, f"Unknown language: {req.target_lang}")
    if req.mood not in MOOD_PACE:
        raise HTTPException(400, f"Unknown mood: {req.mood}")

    speaker = req.speaker or LANGUAGES[req.target_lang][1]
    if not speaker:
        raise HTTPException(400, f"No default speaker for {req.target_lang}. Provide speaker.")

    job_id = jobs.submit_job("story", _run_story, {
        "text": req.text,
        "theme": req.theme,
        "keyword": req.keyword,
        "target_lang": req.target_lang,
        "speaker": speaker,
        "mood": req.mood,
        "no_upload": req.no_upload,
        "workers": req.workers,
    }, user_id=user["user_id"])

    return JobResponse(job_id=job_id, status="queued")
