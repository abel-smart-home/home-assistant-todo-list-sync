"""Enable/disable switch platform for Todo List Sync."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    """Set up Todo List Sync switches."""

    manager: TodoListSyncManager = entry.runtime_data
    async_add_entities([TodoListSyncEnabledSwitch(manager)])


class TodoListSyncEnabledSwitch(TodoListSyncEntity, SwitchEntity):
    """Enable or disable the synchronization engine."""

    _attr_translation_key = "enabled"
    _attr_icon = "mdi:sync-circle"

    def __init__(self, manager: TodoListSyncManager) -> None:
        """Initialize the switch."""

        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_enabled"

    @property
    def is_on(self) -> bool:
        """Return whether synchronization is enabled."""

        return self.manager.enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable synchronization."""

        await self.manager.async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable synchronization."""

        await self.manager.async_set_enabled(False)
