"""Data models for Todo List Sync."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

STATUS_NEEDS_ACTION = "needs_action"
STATUS_COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class SyncItem:
    """A normalized logical to-do item."""

    summary: str
    status: str = STATUS_NEEDS_ACTION
    uid: str | None = None

    def to_storage(self) -> dict[str, Any]:
        """Serialize the item for Home Assistant storage."""

        data = asdict(self)
        data.pop("uid", None)
        return data

    @classmethod
    def from_storage(cls, data: dict[str, Any]) -> "SyncItem":
        """Deserialize a shadow item."""

        return cls(
            summary=str(data.get("summary", "")),
            status=str(data.get("status", STATUS_NEEDS_ACTION)),
        )
