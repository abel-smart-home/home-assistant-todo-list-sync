"""Retry policy regression tests."""

from custom_components.todo_list_sync.const import RETRY_DELAYS_SECONDS
from custom_components.todo_list_sync.retry import next_retry_delay


def test_retry_schedule_is_bounded() -> None:
    assert RETRY_DELAYS_SECONDS == (5.0, 15.0, 60.0)
    assert next_retry_delay(0) == 5.0
    assert next_retry_delay(1) == 15.0
    assert next_retry_delay(2) == 60.0
    assert next_retry_delay(3) is None
    assert next_retry_delay(99) is None
