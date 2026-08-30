"""Base entities for Todo List Sync."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, NAME, VERSION
from .manager import TodoListSyncManager, update_signal


class TodoListSyncEntity(Entity):
    """Base entity attached to one synchronization pair."""

    _attr_has_entity_name = True

    def __init__(self, manager: TodoListSyncManager) -> None:
        """Initialize the entity."""

        self.manager = manager
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, manager.entry.entry_id)},
            name=manager.entry.title,
            manufacturer="Todo List Sync",
            model="Bidirectional to-do synchronizer",
            sw_version=VERSION,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime updates."""

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                update_signal(self.manager.entry.entry_id),
                self._handle_manager_update,
            )
        )

    @callback
    def _handle_manager_update(self) -> None:
        """Write fresh manager data to Home Assistant."""

        self.async_write_ha_state()
