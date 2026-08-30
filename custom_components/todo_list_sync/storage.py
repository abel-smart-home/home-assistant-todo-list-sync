"""Persistent shadow storage for Todo List Sync."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY_PREFIX, STORAGE_VERSION
from .model import SyncItem


class SyncStorage:
    """Persist synchronization metadata and the last common list state."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage."""

        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}.{entry_id}",
            private=True,
        )

    async def async_load(self) -> dict[str, Any]:
        """Load stored state, returning safe defaults when not initialized."""

        data = await self._store.async_load() or {}
        raw_shadow = data.get("shadow", {})
        shadow: dict[str, SyncItem] = {}
        if isinstance(raw_shadow, dict):
            for key, value in raw_shadow.items():
                if isinstance(key, str) and isinstance(value, dict):
                    shadow[key] = SyncItem.from_storage(value)

        return {
            "initialized": bool(data.get("initialized", False)),
            "enabled": bool(data.get("enabled", True)),
            "shadow": shadow,
            "last_sync": data.get("last_sync"),
            "last_error": data.get("last_error"),
            "last_periodic_verification": data.get("last_periodic_verification"),
            "last_periodic_verification_attempt": data.get(
                "last_periodic_verification_attempt"
            ),
            "last_periodic_verification_result": data.get(
                "last_periodic_verification_result"
            ),
            "last_periodic_refresh_mode": data.get("last_periodic_refresh_mode"),
            "periodic_verification_count": int(
                data.get("periodic_verification_count", 0) or 0
            ),
        }

    async def async_save(
        self,
        *,
        initialized: bool,
        enabled: bool,
        shadow: dict[str, SyncItem],
        last_sync: str | None,
        last_error: str | None,
        last_periodic_verification: str | None,
        last_periodic_verification_attempt: str | None,
        last_periodic_verification_result: str | None,
        last_periodic_refresh_mode: str | None,
        periodic_verification_count: int,
    ) -> None:
        """Persist the synchronization state immediately."""

        await self._store.async_save(
            {
                "initialized": initialized,
                "enabled": enabled,
                "shadow": {key: item.to_storage() for key, item in shadow.items()},
                "last_sync": last_sync,
                "last_error": last_error,
                "last_periodic_verification": last_periodic_verification,
                "last_periodic_verification_attempt": (
                    last_periodic_verification_attempt
                ),
                "last_periodic_verification_result": (
                    last_periodic_verification_result
                ),
                "last_periodic_refresh_mode": last_periodic_refresh_mode,
                "periodic_verification_count": periodic_verification_count,
            }
        )
