"""Diagnostics support for Todo List Sync."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .manager import TodoListSyncManager


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return privacy-preserving diagnostics without list contents."""

    manager: TodoListSyncManager = entry.runtime_data
    return {
        "entry": {
            "title": entry.title,
            "options": dict(entry.options),
        },
        "runtime": manager.diagnostics,
    }
