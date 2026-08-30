"""Diagnostic sensor platform for Todo List Sync."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
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
    """Set up Todo List Sync sensors."""

    manager: TodoListSyncManager = entry.runtime_data
    async_add_entities([TodoListSyncStatusSensor(manager)])


class TodoListSyncStatusSensor(TodoListSyncEntity, SensorEntity):
    """Expose synchronization status and non-sensitive counters."""

    _attr_translation_key = "status"
    _attr_icon = "mdi:playlist-check"

    def __init__(self, manager: TodoListSyncManager) -> None:
        """Initialize the status sensor."""

        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        """Return synchronization state."""

        return self.manager.status.value

    @property
    def extra_state_attributes(self) -> dict:
        """Return runtime diagnostics without list contents."""

        return self.manager.diagnostics
