"""Provider refresh helpers for Todo List Sync.

The integration is generic, but Home Assistant 2026.8.x Alexa Devices keeps its
full to-do-list refresh helper on the config-entry runtime coordinator. We use
feature detection rather than importing Alexa internals so this optimization can
fail gracefully if Home Assistant changes that implementation later.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)


async def async_refresh_todo_provider(
    hass: HomeAssistant,
    entity_id: str,
    *,
    allow_config_entry_reload: bool = False,
) -> str:
    """Try to obtain a fresh provider-side copy of a to-do entity.

    Returns a diagnostic mode string:
      * ``alexa_full_sync`` when the Alexa Devices runtime helper was used.
      * ``config_entry_reload`` when a generic config-entry reload was used.
      * ``cache_only`` when no safe provider refresh mechanism is known.

    Periodic verification never performs a generic config-entry reload. That
    fallback is reserved for reconnect recovery because reloading an entire
    integration can be much heavier than refreshing one list cache.
    """

    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry is None or not registry_entry.config_entry_id:
        return "cache_only"

    config_entry = hass.config_entries.async_get_entry(registry_entry.config_entry_id)
    if config_entry is None:
        return "cache_only"

    runtime_data: Any = getattr(config_entry, "runtime_data", None)
    full_sync = getattr(runtime_data, "sync_todo_list_items", None)

    # Alexa Devices 2026.8.x exposes this coordinator coroutine. We intentionally
    # duck-type it instead of importing private Alexa implementation classes.
    if registry_entry.platform == "alexa_devices" and callable(full_sync):
        try:
            await full_sync()
            notify = getattr(runtime_data, "async_update_listeners", None)
            if callable(notify):
                notify()
            return "alexa_full_sync"
        except Exception:  # noqa: BLE001 - provider exceptions vary by HA version
            _LOGGER.exception("Provider full refresh failed for %s", entity_id)
            raise

    if allow_config_entry_reload:
        await hass.config_entries.async_reload(config_entry.entry_id)
        return "config_entry_reload"

    return "cache_only"
