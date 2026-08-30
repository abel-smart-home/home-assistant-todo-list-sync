"""Todo List Sync integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .manager import TodoListSyncManager
from .repairs import clear_all_missing_list_issues
from .storage import SyncStorage

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Todo List Sync from a config entry."""

    manager = TodoListSyncManager(hass, entry)
    entry.runtime_data = manager
    await manager.async_setup()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Todo List Sync config entry."""

    manager: TodoListSyncManager = entry.runtime_data
    await manager.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove private shadow state and stale Repairs for a deleted entry."""

    await SyncStorage(hass, entry.entry_id).async_remove()
    clear_all_missing_list_issues(hass, entry_id=entry.entry_id)
