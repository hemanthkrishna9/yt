"""
YouTube Data API v3 upload.
OAuth2 with token caching — browser login only needed once.
"""

import pickle
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import YOUTUBE_CLIENT_SECRET, YOUTUBE_TOKEN_CACHE
from pipeline.log import get_logger
from pipeline.retry import retry, APIError

log = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_youtube_client():
    creds = None
    token_path = Path(YOUTUBE_TOKEN_CACHE)

    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(YOUTUBE_CLIENT_SECRET).exists():
                raise FileNotFoundError(
                    f"YouTube client secret not found: {YOUTUBE_CLIENT_SECRET}\n"
                    "Download it from Google Cloud Console -> APIs -> OAuth 2.0 credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRET, SCOPES)
            # Headless server support
            if sys.stdout.isatty():
                creds = flow.run_local_server(port=0)
            else:
                creds = flow.run_console()

        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


@retry(max_attempts=3, base_delay=5.0, max_delay=60.0,
       retryable_exceptions=(ConnectionError, TimeoutError, OSError, Exception))
def _upload_with_retry(youtube, body, media) -> dict:
    """Upload video with resumable upload + retry on transient errors."""
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    log.info("Uploading to YouTube (private)...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"\r  \u2192 Upload progress: {pct}%", end="", flush=True)
    print()
    return response


def upload_short(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: str = "private",  # always private first — user reviews before publishing
) -> str:
    """
    Upload video to YouTube.
    Returns the YouTube video URL.
    Always uploads as private — creator promotes manually.

    Raises APIError on persistent failure.
    """
    youtube = _get_youtube_client()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags[:15],
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024,  # 1MB chunks
    )

    try:
        response = _upload_with_retry(youtube, body, media)
    except Exception as e:
        raise APIError(
            f"YouTube upload failed: {e}", api="youtube"
        ) from e

    video_id = response["id"]
    url = f"https://www.youtube.com/shorts/{video_id}"
    log.info(f"Uploaded: {url}")
    return url
