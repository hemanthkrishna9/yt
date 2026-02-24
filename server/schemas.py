from pydantic import BaseModel


class DubRequest(BaseModel):
    url: str | None = None
    file_path: str | None = None
    source_lang: str = "en-IN"
    target_lang: str
    speaker: str | None = None
    workers: int = 4


class StoryRequest(BaseModel):
    text: str | None = None
    theme: str | None = None
    keyword: str | None = None
    target_lang: str
    speaker: str | None = None
    mood: str = "default"
    no_upload: bool = True
    workers: int = 4


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: list[str] = []
    output_path: str | None = None
    error: str | None = None


class ConfigResponse(BaseModel):
    languages: dict[str, str]
    speakers: list[str]
    themes: list[str]
    moods: list[str]
