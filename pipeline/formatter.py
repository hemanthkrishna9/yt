"""
Gemini scene breakdown: story text → structured scenes + YouTube metadata.
"""

from pydantic import BaseModel, Field
from typing import List
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, LANGUAGES
from pipeline.log import get_logger
from pipeline.retry import retry, APIError

log = get_logger(__name__)


class Scene(BaseModel):
    scene_number: int
    narration: str = Field(description="Narration text for this scene, 1-3 sentences.")
    image_prompt: str = Field(
        description="Visual description for image generation. In English. "
                    "Include art style, characters, expressions, setting, colors. "
                    "No text/writing in the image. Portrait 9:16 orientation."
    )
    duration_hint: float = Field(
        description="Estimated narration duration in seconds."
    )


class StoryBreakdown(BaseModel):
    title: str
    moral: str = Field(description="One-sentence moral of the story.")
    scenes: List[Scene]
    youtube_title: str = Field(description="Catchy YouTube Shorts title, under 70 chars.")
    youtube_description: str = Field(description="2-3 sentence YouTube description.")
    youtube_tags: List[str] = Field(description="8-12 relevant tags.")


@retry(max_attempts=3, base_delay=2.0, max_delay=30.0,
       retryable_exceptions=(ConnectionError, TimeoutError, OSError, Exception))
def _call_gemini(prompt: str) -> str:
    """Call Gemini API with retry on transient failures."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StoryBreakdown,
        ),
    )
    return response.text


def breakdown_story(story_text: str, target_lang: str) -> StoryBreakdown:
    """
    Use Gemini to break a story into 5-8 scenes with image prompts.
    Narration is in the target language; image prompts always in English.

    Raises APIError on persistent failure.
    """
    lang_name = LANGUAGES.get(target_lang, ("English",))[0]

    prompt = f"""You are a YouTube Shorts scriptwriter specialising in Indian language content.

Break this story into 5-8 scenes for a 60-90 second vertical short video.

RULES:
- narration: Write in {lang_name}. Keep each scene to 1-3 short sentences. Natural spoken language.
- image_prompt: Always in English. Describe one vivid visual moment per scene.
  Include: art style (use "vibrant Indian folk art style, warm earthy tones"),
  main characters and their expressions, setting, time of day, colors.
  Never include any text or writing in the image description.
- duration_hint: Estimate how many seconds the narration will take when spoken aloud.
- moral: Write in {lang_name}.
- youtube_title: Engaging English title under 70 characters.
- youtube_tags: Mix of English and {lang_name} relevant tags.

STORY:
{story_text}
"""

    try:
        raw = _call_gemini(prompt)
    except Exception as e:
        raise APIError(
            f"Gemini scene breakdown failed: {e}", api="gemini"
        ) from e

    breakdown = StoryBreakdown.model_validate_json(raw)

    # Fallback: if narration looks like English when it shouldn't be, flag it
    if target_lang != "en-IN":
        for scene in breakdown.scenes:
            if scene.narration.isascii():
                log.warning(
                    f"Scene {scene.scene_number} narration may not be in {lang_name}",
                    extra={"scene": scene.scene_number, "lang": target_lang},
                )

    return breakdown
