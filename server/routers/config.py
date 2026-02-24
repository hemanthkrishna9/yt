from fastapi import APIRouter
from config import LANGUAGES, SPEAKERS, THEMES, MOOD_PACE
from server.schemas import ConfigResponse

router = APIRouter()


@router.get("/config", response_model=ConfigResponse)
def get_config():
    return ConfigResponse(
        languages={code: name for code, (name, _) in LANGUAGES.items()},
        speakers=SPEAKERS,
        themes=THEMES,
        moods=list(MOOD_PACE.keys()),
    )
