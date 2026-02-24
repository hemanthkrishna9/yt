"""
Retry with exponential backoff + jitter for API calls.
Thread-safe rate limiter for parallel workers.

Usage:
    from pipeline.retry import retry, sarvam_limiter

    @retry(max_attempts=4, base_delay=1.0, max_delay=30.0)
    def call_api():
        sarvam_limiter.wait()  # thread-safe rate limiting
        ...
"""

import time
import random
import functools
import threading
from pipeline.log import get_logger

log = get_logger(__name__)


class APIError(Exception):
    """Raised when an API call fails after all retries."""
    def __init__(self, message: str, status_code: int = None, api: str = None):
        self.status_code = status_code
        self.api = api
        super().__init__(message)


class RateLimiter:
    """Thread-safe token bucket rate limiter.

    Ensures no more than `rate` requests per minute across all threads.
    """
    def __init__(self, rate_per_minute: int):
        self.min_interval = 60.0 / rate_per_minute if rate_per_minute > 0 else 0
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self):
        """Block until it's safe to make another request."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self._last_call = time.monotonic()

    def update_rate(self, rate_per_minute: int):
        """Update the rate limit (e.g. after upgrading tier)."""
        with self._lock:
            self.min_interval = 60.0 / rate_per_minute if rate_per_minute > 0 else 0


# Global rate limiter — shared by all Sarvam API callers across threads
from config import SARVAM_RATE_LIMIT
sarvam_limiter = RateLimiter(SARVAM_RATE_LIMIT)


def retry(
    max_attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_statuses: tuple = (429, 500, 502, 503, 504),
    retryable_exceptions: tuple = (ConnectionError, TimeoutError, OSError),
):
    """
    Decorator: retry with exponential backoff + jitter.

    On 429 (rate limit), respects Retry-After header if present.
    Non-retryable HTTP errors (4xx except 429) raise immediately.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    result = fn(*args, **kwargs)
                    return result
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        break
                    delay = _calc_delay(attempt, base_delay, max_delay)
                    log.warning(
                        f"Retry {attempt}/{max_attempts} after {type(e).__name__}: {e} "
                        f"(waiting {delay:.1f}s)",
                        extra={"attempt": attempt},
                    )
                    time.sleep(delay)
                except APIError:
                    raise  # already structured, don't wrap again
                except Exception as e:
                    # Non-retryable — raise immediately
                    raise
            raise APIError(
                f"{fn.__name__} failed after {max_attempts} attempts: {last_exc}",
            )
        return wrapper
    return decorator


def _calc_delay(attempt: int, base: float, maximum: float) -> float:
    """Exponential backoff with full jitter."""
    exp_delay = base * (2 ** (attempt - 1))
    jittered = random.uniform(0, min(exp_delay, maximum))
    return max(0.1, jittered)


def check_response(resp, api_name: str, retryable_statuses=(429, 500, 502, 503, 504)):
    """
    Check an HTTP response — raise retryable or fatal errors.

    Call this inside a @retry-decorated function so retryable errors
    trigger automatic retry.
    """
    if resp.status_code == 200:
        return

    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                time.sleep(float(retry_after))
            except ValueError:
                pass
        raise ConnectionError(
            f"{api_name} rate limited (429): {resp.text[:200]}"
        )

    if resp.status_code in retryable_statuses:
        raise ConnectionError(
            f"{api_name} server error ({resp.status_code}): {resp.text[:200]}"
        )

    # Non-retryable (e.g. 400, 401, 403) — fail immediately
    raise APIError(
        f"{api_name} error ({resp.status_code}): {resp.text[:300]}",
        status_code=resp.status_code,
        api=api_name,
    )
