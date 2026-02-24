"""
Imagen 3 image generation — one 9:16 image per scene.
"""

from pathlib import Path
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, IMAGEN_MODEL
from pipeline.log import get_logger
from pipeline.retry import retry, APIError

log = get_logger(__name__)

# Words that commonly trigger Imagen 3 safety filters in folk stories
_BLOCKED_WORDS = [
    "demon", "battle", "kill", "war", "blood", "weapon", "fight",
    "death", "dead", "murder", "evil", "devil", "hell",
]

_STYLE_PREFIX = (
    "vibrant Indian folk art style, warm earthy tones, "
    "children's book illustration, safe for all ages, "
    "detailed and colorful, "
)

_FALLBACK_PROMPT = (
    "A beautiful Indian village scene at golden hour, "
    "lush green trees, children playing, warm and inviting atmosphere, "
    "vibrant colors, Indian folk art style"
)


def _sanitize_prompt(prompt: str) -> str:
    """Replace words that trigger safety filters with safer alternatives."""
    replacements = {
        "demon":   "mystical creature",
        "battle":  "challenge",
        "kill":    "defeat",
        "war":     "conflict",
        "blood":   "struggle",
        "weapon":  "tool",
        "fight":   "confrontation",
        "death":   "end",
        "dead":    "fallen",
        "murder":  "crime",
        "evil":    "cunning",
        "devil":   "trickster",
        "hell":    "dark place",
    }
    result = prompt
    for bad, good in replacements.items():
        result = result.replace(bad, good).replace(bad.capitalize(), good.capitalize())
    return result


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0,
       retryable_exceptions=(ConnectionError, TimeoutError, OSError, RuntimeError, Exception))
def _generate_image(full_prompt: str) -> bytes:
    """Call Imagen 3 API with retry. Returns image bytes."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_images(
        model=IMAGEN_MODEL,
        prompt=full_prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="9:16",
            output_mime_type="image/jpeg",
        ),
    )
    if not response.generated_images:
        raise RuntimeError("No image returned (safety filter likely triggered)")
    return response.generated_images[0].image.image_bytes


def generate_scene_image(
    prompt: str,
    scene_index: int,
    output_dir: Path,
) -> Path:
    """
    Generate one 9:16 image for a scene using Imagen 3.
    Returns path to saved JPEG. Caches — skips if file exists.

    Tries sanitized prompt first, falls back to generic prompt on failure.
    Raises APIError if all attempts fail.
    """
    out_path = output_dir / f"scene_{scene_index:02d}.jpg"
    if out_path.exists():
        log.info(f"Scene {scene_index:02d}: image cached")
        return out_path

    sanitized = _sanitize_prompt(prompt)
    full_prompt = _STYLE_PREFIX + sanitized

    try:
        img_bytes = _generate_image(full_prompt)
    except Exception:
        log.warning(f"Scene {scene_index:02d}: primary prompt failed, trying fallback",
                    extra={"scene": scene_index})
        try:
            img_bytes = _generate_image(_STYLE_PREFIX + _FALLBACK_PROMPT)
        except Exception as e:
            raise APIError(
                f"Could not generate image for scene {scene_index}: {e}",
                api="imagen3",
            ) from e

    out_path.write_bytes(img_bytes)
    log.info(f"Scene {scene_index:02d}: image saved ({len(img_bytes)//1024} KB)",
             extra={"scene": scene_index})
    return out_path
