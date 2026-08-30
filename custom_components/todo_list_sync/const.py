"""Constants for Todo List Sync."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

DOMAIN = "todo_list_sync"
NAME = "Todo List Sync"
VERSION = "0.1.4"

CONF_PRIMARY_ENTITY = "primary_entity"
CONF_SECONDARY_ENTITY = "secondary_entity"
CONF_CONFLICT_POLICY = "conflict_policy"
CONF_VERIFICATION_INTERVAL = "verification_interval"
CONF_REFRESH_ON_RECONNECT = "refresh_on_reconnect"

DEFAULT_CONFLICT_POLICY = "primary"
DEFAULT_VERIFICATION_INTERVAL = 30
DEFAULT_REFRESH_ON_RECONNECT = True
MIN_VERIFICATION_INTERVAL = 30
MAX_VERIFICATION_INTERVAL = 1440
VERIFICATION_STEP = 30

DEBOUNCE_SECONDS = 1.5
CONFIRM_TIMEOUT_SECONDS = 8.0
CONFIRM_POLL_SECONDS = 0.4

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = DOMAIN

PLATFORMS = ["sensor", "button", "switch"]


class ConflictPolicy(StrEnum):
    """Conflict policy for true concurrent changes."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class SyncStatus(StrEnum):
    """Runtime synchronization state."""

    INITIALIZING = "initializing"
    SYNCHRONIZED = "synchronized"
    SYNCING = "syncing"
    WAITING_PRIMARY = "waiting_primary"
    WAITING_SECONDARY = "waiting_secondary"
    DISABLED = "disabled"
    ERROR = "error"


def verification_delta(minutes: int) -> timedelta:
    """Return the verification interval as a timedelta."""

    return timedelta(minutes=max(MIN_VERIFICATION_INTERVAL, minutes))
