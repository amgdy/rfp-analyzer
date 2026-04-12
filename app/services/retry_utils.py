"""Retry utilities for resilient OpenAI / Azure API calls.

Provides a centralized retry wrapper used by all agent modules
(scoring, criteria extraction, comparison) to handle transient
failures such as rate-limits, timeouts, and intermittent server errors.
"""

import asyncio
import logging
from typing import TypeVar

from .logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# ── Configuration ────────────────────────────────────────────────
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 2.0
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF_SECONDS = 30.0

# Exceptions that should trigger a retry.
# We match broadly on common transient error messages and HTTP status
# codes rather than tying to a specific SDK exception class.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

_RETRYABLE_SUBSTRINGS = (
    "rate limit",
    "rate_limit",
    "throttl",
    "timeout",
    "timed out",
    "connection",
    "server error",
    "internal error",
    "service unavailable",
    "bad gateway",
    "gateway timeout",
    "temporarily unavailable",
    "overloaded",
    "capacity",
    "too many requests",
    "retry",
    "empty response",
)


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception looks transient and worth retrying."""
    # Check for an HTTP status code attribute (common in Azure / Openai SDKs)
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status is not None:
        try:
            if int(status) in _RETRYABLE_STATUS_CODES:
                return True
        except (ValueError, TypeError):
            pass

    # Fall back to substring matching on the error message
    msg = str(exc).lower()
    return any(sub in msg for sub in _RETRYABLE_SUBSTRINGS)


async def run_with_retry(
    coro_factory,
    *,
    description: str = "OpenAI call",
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF_SECONDS,
    backoff_multiplier: float = BACKOFF_MULTIPLIER,
    max_backoff: float = MAX_BACKOFF_SECONDS,
):
    """Execute an async operation with exponential-backoff retry.

    Parameters
    ----------
    coro_factory:
        A *callable* (zero-arg) that returns an awaitable each time it is
        called, e.g. ``lambda: agent.run(prompt)``.  A fresh coroutine is
        created on every attempt so the retry is safe.
    description:
        Human-readable label used in log messages.
    max_retries:
        Maximum number of *retries* (attempts = max_retries + 1).
    initial_backoff:
        Seconds to wait before the first retry.
    backoff_multiplier:
        Multiplier applied to the backoff after each retry.
    max_backoff:
        Upper cap on the backoff duration.

    Returns
    -------
    The return value of the awaited coroutine on the first successful attempt.

    Raises
    ------
    The last exception encountered when all attempts are exhausted.
    """
    backoff = initial_backoff
    last_exc: BaseException | None = None

    for attempt in range(1, max_retries + 2):  # max_retries+1 total attempts; range is exclusive
        try:
            return await coro_factory()
        except Exception as exc:
            last_exc = exc
            if attempt > max_retries or not _is_retryable(exc):
                logger.error(
                    "%s failed (attempt %d/%d, non-retryable): %s",
                    description,
                    attempt,
                    max_retries + 1,
                    exc,
                )
                raise

            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs …",
                description,
                attempt,
                max_retries + 1,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * backoff_multiplier, max_backoff)

    # Should not be reachable, but just in case:
    raise last_exc  # type: ignore[misc]
