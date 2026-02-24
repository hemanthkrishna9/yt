"""
Fetch public domain stories by theme.
Sources: Project Gutenberg, Internet Archive, Sacred-texts.com
Stories cached locally for 7 days.
"""

import re
import time
import random
import pickle
import requests
from pathlib import Path
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from filelock import FileLock

from pipeline.log import get_logger

log = get_logger(__name__)

CACHE_DIR = Path("output/.story_cache")
CACHE_TTL_DAYS = 7
HEADERS = {"User-Agent": "StoryShorts-Pipeline/1.0 (educational use)"}

SOURCES = {
    "aesop": {
        "url": "https://www.gutenberg.org/files/21/21-0.txt",
        "type": "gutenberg_title_case",
    },
    "panchatantra": {
        "url": "https://www.gutenberg.org/files/12455/12455-0.txt",
        "type": "gutenberg_title_case",
    },
    "vikram": {
        "url": "https://www.gutenberg.org/files/1460/1460-0.txt",
        "type": "gutenberg_title_case",
    },
    "tenali": {
        "url": "https://archive.org/stream/StoriesOfTenaliRaman-English/story-tenali_djvu.txt",
        "type": "gutenberg_title_case",
    },
    "jataka": {
        "url": "https://www.sacred-texts.com/bud/j1/",
        "type": "jataka_index",
    },
}


def _cache_path(theme: str) -> tuple[Path, Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{theme}.txt", CACHE_DIR / f"{theme}_index.pkl"


def _is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(days=CACHE_TTL_DAYS)


def _fetch_text(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    # Detect encoding
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def _parse_gutenberg(raw: str) -> dict[str, str]:
    """
    Split a Gutenberg plain text into {title: story_body}.
    Handles Title Case story titles followed by blank lines + body text.
    """
    # Strip Project Gutenberg header/footer
    start = raw.find("*** START OF")
    end   = raw.find("*** END OF")
    if start != -1:
        raw = raw[raw.find("\n", start):]
    if end != -1:
        raw = raw[:end]

    stories = {}
    lines = raw.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # A story title: Title Case, 3-80 chars, not a sentence (no period mid-line)
        if (
            3 < len(line) <= 80
            and re.match(r'^[A-Z][A-Za-z ,\'\-&]+$', line)
            and not line.isupper()          # skip ALL CAPS headers
            and "." not in line             # skip sentences
            and sum(1 for c in line if c.isupper()) >= 1
        ):
            # Check next line is blank (title followed by empty line)
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                # Collect body until next candidate title or 2000 chars
                body_lines = []
                j = i + 2
                while j < len(lines):
                    next_line = lines[j].strip()
                    # Stop at next title candidate
                    if (
                        3 < len(next_line) <= 80
                        and re.match(r'^[A-Z][A-Za-z ,\'\-&]+$', next_line)
                        and not next_line.isupper()
                        and j + 1 < len(lines) and lines[j + 1].strip() == ""
                    ):
                        break
                    body_lines.append(lines[j])
                    j += 1

                body = " ".join(b.strip() for b in body_lines if b.strip())
                body = re.sub(r'\s+', ' ', body).strip()

                if 80 <= len(body) <= 3000:
                    stories[line] = body[:2000]
                i = j
                continue
        i += 1

    return stories


def _parse_jataka(index_url: str) -> dict[str, str]:
    """Scrape Jataka story index and fetch a sample of stories."""
    resp = requests.get(index_url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "lxml")
    links = [a["href"] for a in soup.find_all("a", href=True)
             if re.match(r"j1\d{3}\.htm", a["href"])]

    stories = {}
    for link in links[:30]:  # fetch first 30 to build cache
        url = index_url + link
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            s = BeautifulSoup(r.text, "lxml")
            title_tag = s.find("h3") or s.find("h2") or s.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else link
            paras = s.find_all("p")
            body = " ".join(p.get_text(" ", strip=True) for p in paras[:8])
            if 100 <= len(body) <= 3000:
                stories[title] = body[:2000]
            time.sleep(0.5)
        except Exception:
            continue

    return stories


def _build_index(theme: str) -> dict[str, str]:
    """Download and parse stories for a theme. Cache results with file locking."""
    src = SOURCES[theme]
    txt_path, idx_path = _cache_path(theme)
    lock_path = idx_path.with_suffix(".lock")

    if src["type"] == "jataka_index":
        stories = _parse_jataka(src["url"])
    else:
        if not _is_fresh(txt_path):
            log.info(f"Downloading {theme} stories from {src['url']}...")
            raw = _fetch_text(src["url"])
            txt_path.write_text(raw, encoding="utf-8")
        else:
            raw = txt_path.read_text(encoding="utf-8")

        stories = _parse_gutenberg(raw)

    with FileLock(lock_path, timeout=30):
        with open(idx_path, "wb") as f:
            pickle.dump(stories, f)

    log.info(f"Cached {len(stories)} stories for theme '{theme}'")
    return stories


def _load_index(theme: str) -> dict[str, str]:
    _, idx_path = _cache_path(theme)
    lock_path = idx_path.with_suffix(".lock")
    if _is_fresh(idx_path):
        with FileLock(lock_path, timeout=30):
            with open(idx_path, "rb") as f:
                return pickle.load(f)
    return _build_index(theme)


def fetch_story(theme: str, keyword: str = None) -> tuple[str, str]:
    """
    Fetch a story for the given theme.
    Returns (story_text, title) or ("", "") if not found.

    Args:
        theme:   one of aesop, panchatantra, tenali, jataka, vikram
        keyword: optional filter keyword to match in title
    """
    theme = theme.lower().strip()

    if theme not in SOURCES:
        log.warning(f"Unknown theme '{theme}'. Available: {', '.join(SOURCES)}")
        return "", ""

    try:
        stories = _load_index(theme)
    except Exception as e:
        log.error(f"Failed to fetch stories: {e}")
        return "", ""

    if not stories:
        return "", ""

    # Filter by keyword if given
    if keyword:
        filtered = {t: s for t, s in stories.items()
                    if keyword.lower() in t.lower() or keyword.lower() in s.lower()}
        if not filtered:
            log.info(f"No stories found for keyword '{keyword}' in theme '{theme}'")
            return "", ""
        stories = filtered

    # Pick a random story
    title = random.choice(list(stories.keys()))
    return stories[title], title
