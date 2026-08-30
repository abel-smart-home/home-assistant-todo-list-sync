"""Pure retry helpers for Todo List Sync."""

from __future__ import annotations

from .const import RETRY_DELAYS_SECONDS


def next_retry_delay(current_attempt: int) -> float | None:
    """Return the next bounded retry delay.

    ``current_attempt`` is the number of automatic retries already scheduled for
    the current failure sequence. ``None`` means the retry budget is exhausted.
    """

    current_attempt = max(current_attempt, 0)
    if current_attempt >= len(RETRY_DELAYS_SECONDS):
        return None
    return RETRY_DELAYS_SECONDS[current_attempt]
