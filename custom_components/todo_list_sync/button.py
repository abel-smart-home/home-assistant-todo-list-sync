"""Button platform for Todo List Sync."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import TodoListSyncEntity
from .manager import TodoListSyncManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Todo List Sync buttons."""

    manager: TodoListSyncManager = entry.runtime_data
    async_add_entities([TodoListSyncNowButton(manager)])


class TodoListSyncNowButton(TodoListSyncEntity, ButtonEntity):
    """Force an immediate provider refresh and reconciliation."""

    _attr_translation_key = "sync_now"
    _attr_icon = "mdi:sync"

    def __init__(self, manager: TodoListSyncManager) -> None:
        """Initialize the button."""

        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_sync_now"

    async def async_press(self) -> None:
        """Request immediate synchronization."""

        await self.manager.async_manual_sync()
