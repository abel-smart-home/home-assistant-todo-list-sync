"""Todo List Sync integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .manager import TodoListSyncManager

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

