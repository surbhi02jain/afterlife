"""The one place a google-genai client is created and called.

`generate()` wraps client.models.generate_content with:
  - a per-model requests-per-minute throttle (GEMINI_RPM; the free tier allows only a few RPM), and
  - a bounded wait-and-retry on 429 that honours the retry delay Gemini sends back, and
  - network failures (timeouts, dropped connections) raised as GeminiUnreachable.
Other errors are raised unchanged; callers turn them into user-facing messages.
"""

import logging
import re
import threading
import time
from collections import defaultdict, deque
from datetime import date
from functools import lru_cache

import httpx
from google import genai
from google.genai import errors, types

from app.config import get_settings

log = logging.getLogger("afterlife.gemini")

MAX_429_RETRIES = 3
MAX_429_WAIT_SECONDS = 70


class GeminiNotConfigured(RuntimeError):
    pass


class GeminiUnreachable(RuntimeError):
    """The request never got a reply (timeout, connection reset). Message is safe to show the user."""


class GeminiDailyLimitReached(GeminiUnreachable):
    """This instance used today's Gemini allowance. A subclass so every caller already shows it to the family."""


class DailyBudget:
    """Gemini calls per calendar day; 0 = no limit. A public URL on a billed key must not have an open-ended bill.
    shortcut: counted per instance in memory, so the real ceiling is the limit x max instances (3) and resets on
    restart; for one shared ceiling, also set a daily quota on the API key in the Cloud Console."""

    def __init__(self, limit: int):
        self.limit, self._day, self._used = limit, None, 0
        self._lock = threading.Lock()

    def spend(self) -> None:
        if self.limit <= 0:
            return
        with self._lock:
            today = date.today()
            if self._day != today:
                self._day, self._used = today, 0
            if self._used >= self.limit:
                raise GeminiDailyLimitReached("Afterlife has reached today's limit for reading documents and looking "
                                              "for what's missing. Please try again tomorrow; everything so far is saved.")
            self._used += 1


@lru_cache(maxsize=1)
def get_daily_budget() -> DailyBudget:
    return DailyBudget(get_settings().gemini_daily_limit)


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiNotConfigured("GEMINI_API_KEY is not set. Add it to .env or the environment.")
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=120_000,  # milliseconds
            # 429s are handled in generate() so we can wait as long as the server asks.
            retry_options=types.HttpRetryOptions(
                attempts=5, initial_delay=2.0, max_delay=20.0, exp_base=2.0,  # 503 "high demand" spikes pass quickly
                http_status_codes=[500, 502, 503, 504],
            ),
        ),
    )


class RateLimiter:
    """Sliding one-minute window per model. rpm <= 0 disables throttling."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self._calls: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, model: str) -> None:
        if self.rpm <= 0:
            return
        while True:
            with self._lock:
                window = self._calls[model]
                now = time.monotonic()
                while window and now - window[0] >= 60:
                    window.popleft()
                if len(window) < self.rpm:
                    window.append(now)
                    return
                wait = 60 - (now - window[0]) + 0.1
            log.info("rate limit: waiting %.1fs for %s", wait, model)
            time.sleep(wait)


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_settings().gemini_rpm)


def retry_delay_seconds(exc: errors.APIError) -> float | None:
    """Pull the server's suggested delay out of a 429 ('retryDelay': '56s' or 'retry in 56.2s')."""
    for detail in (exc.details or {}).get("error", {}).get("details", []) if isinstance(exc.details, dict) else []:
        delay = detail.get("retryDelay") if isinstance(detail, dict) else None
        if delay and delay.endswith("s"):
            return float(delay[:-1])
    match = re.search(r"retry in ([\d.]+)s", exc.message or "")
    return float(match.group(1)) if match else None


def generate(client, *, model: str, contents, config: types.GenerateContentConfig):
    limiter = get_rate_limiter()
    for attempt in range(MAX_429_RETRIES + 1):
        get_daily_budget().spend()
        limiter.acquire(model)
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except httpx.TransportError as exc:
            raise GeminiUnreachable(f"Couldn't reach Gemini ({type(exc).__name__}). Please try again.") from exc
        except errors.APIError as exc:
            if exc.code != 429 or attempt == MAX_429_RETRIES:
                raise
            delay = retry_delay_seconds(exc)
            if delay is None or delay > MAX_429_WAIT_SECONDS:
                raise  # daily quota or unknown: waiting won't help, surface it
            log.warning("429 from %s, waiting %.1fs (attempt %d)", model, delay, attempt + 1)
            time.sleep(delay + 1)
