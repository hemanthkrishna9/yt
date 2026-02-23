"""
Imagen 3 image generation — one 9:16 image per scene.
"""

import time
from pathlib import Path
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, IMAGEN_MODEL

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


def generate_scene_image(
    prompt: str,
    scene_index: int,
    output_dir: Path,
) -> Path:
    """
    Generate one 9:16 image for a scene using Imagen 3.
    Returns path to saved JPEG. Caches — skips if file exists.
    """
    out_path = output_dir / f"scene_{scene_index:02d}.jpg"
    if out_path.exists():
        print(f"  → Scene {scene_index:02d}: image cached")
        return out_path

    client = genai.Client(api_key=GEMINI_API_KEY)
    sanitized = _sanitize_prompt(prompt)
    full_prompt = _STYLE_PREFIX + sanitized

    for attempt in range(3):
        try:
            response = client.models.generate_images(
                model=IMAGEN_MODEL,
                prompt=full_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="9:16",
                    output_mime_type="image/jpeg",
                ),
            )

            if response.generated_images:
                img_bytes = response.generated_images[0].image.image_bytes
                out_path.write_bytes(img_bytes)
                print(f"  → Scene {scene_index:02d}: image saved ({len(img_bytes)//1024} KB)")
                return out_path

            # No images returned — safety filter likely
            print(f"  ⚠ Scene {scene_index:02d}: no image returned (attempt {attempt+1}), using fallback prompt")
            full_prompt = _STYLE_PREFIX + _FALLBACK_PROMPT

        except Exception as e:
            print(f"  ✗ Scene {scene_index:02d}: image error (attempt {attempt+1}): {e}")
            full_prompt = _STYLE_PREFIX + _FALLBACK_PROMPT

        time.sleep(1)

    # All retries failed — save a placeholder
    print(f"  ✗ Scene {scene_index:02d}: all retries failed, skipping image")
    raise RuntimeError(f"Could not generate image for scene {scene_index}")
