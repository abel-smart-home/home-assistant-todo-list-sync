"""Runtime synchronization manager for Todo List Sync."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from homeassistant.components.todo import TodoListEntity
from homeassistant.components.todo.const import (
    DATA_COMPONENT,
    TodoListEntityFeature,
)
from homeassistant.components.todo.const import DOMAIN as TODO_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONFLICT_POLICY,
    CONF_PRIMARY_ENTITY,
    CONF_REFRESH_ON_RECONNECT,
    CONF_SECONDARY_ENTITY,
    CONF_VERIFICATION_INTERVAL,
    CONFIRM_POLL_SECONDS,
    CONFIRM_TIMEOUT_SECONDS,
    DEBOUNCE_SECONDS,
    DEFAULT_CONFLICT_POLICY,
    DEFAULT_REFRESH_ON_RECONNECT,
    DEFAULT_VERIFICATION_INTERVAL,
    MIN_VERIFICATION_INTERVAL,
    ConflictPolicy,
    SyncStatus,
    verification_delta,
)
from .model import STATUS_COMPLETED, STATUS_NEEDS_ACTION, SyncItem
from .refresh import async_refresh_todo_provider
from .repairs import clear_missing_list_issue, create_missing_list_issue
from .retry import next_retry_delay
from .storage import SyncStorage
from .sync_engine import (
    build_safe_initial_target,
    count_semantic_differences,
    normalize_summary,
    reconcile_three_way,
    semantic_signature,
    semantic_state,
)

_LOGGER = logging.getLogger(__name__)

_REQUIRED_FEATURES = (
    TodoListEntityFeature.CREATE_TODO_ITEM
    | TodoListEntityFeature.UPDATE_TODO_ITEM
    | TodoListEntityFeature.DELETE_TODO_ITEM
)


class SyncFailure(HomeAssistantError):
    """Privacy-safe synchronization failure with structured diagnostics."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        operation: str | None = None,
        side: str | None = None,
    ) -> None:
        """Initialize a structured failure without list item content."""

        super().__init__(message)
        self.category = category
        self.operation = operation
        self.side = side


def update_signal(entry_id: str) -> str:
    """Return the dispatcher signal for a config entry."""

    return f"todo_list_sync_{entry_id}_update"


class TodoListSyncManager:
    """Keep two Home Assistant to-do entities synchronized."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""

        self.hass = hass
        self.entry = entry
        self.primary_entity_id = str(entry.data[CONF_PRIMARY_ENTITY])
        self.secondary_entity_id = str(entry.data[CONF_SECONDARY_ENTITY])

        self._storage = SyncStorage(hass, entry.entry_id)
        self._shadow: dict[str, SyncItem] = {}
        self._initialized = False
        self._enabled = True
        self._last_sync: str | None = None
        self._last_attempt: str | None = None
        self._last_error_category: str | None = None
        self._last_error_operation: str | None = None
        self._last_error_side: str | None = None
        self._last_error_type: str | None = None
        self._status = SyncStatus.INITIALIZING
        self._pending_primary_to_secondary = 0
        self._pending_secondary_to_primary = 0
        self._conflicts_last_sync = 0
        self._last_refresh_mode = "none"
        self._last_periodic_verification: str | None = None
        self._last_periodic_verification_attempt: str | None = None
        self._last_periodic_verification_result: str | None = None
        self._last_periodic_refresh_mode: str | None = None
        self._periodic_verification_count = 0

        self._retry_attempt = 0
        self._retry_count_total = 0
        self._last_retry: str | None = None
        self._last_retry_result: str | None = None

        self._sync_lock = asyncio.Lock()
        self._debounce_task: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None
        self._retry_task: asyncio.Task | None = None
        self._pending_refresh_secondary = False
        self._pending_allow_reload = False
        self._pending_periodic_verification = False
        self._pending_reason = "startup"
        self._rerun_requested = False
        self._suppress_events = 0

        self._post_start_unsubscribe: Callable[[], None] | None = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._todo_unsubscribers: list[Callable[[], None]] = []
        self._todo_item_signatures: dict[str, tuple[tuple[str, str], ...]] = {}

    @property
    def conflict_policy(self) -> ConflictPolicy:
        """Return configured conflict policy."""

        value = self.entry.options.get(CONF_CONFLICT_POLICY, DEFAULT_CONFLICT_POLICY)
        try:
            return ConflictPolicy(value)
        except ValueError:
            return ConflictPolicy.PRIMARY

    @property
    def verification_interval(self) -> int:
        """Return verification interval in minutes, enforcing the hard minimum."""

        value = int(
            self.entry.options.get(
                CONF_VERIFICATION_INTERVAL, DEFAULT_VERIFICATION_INTERVAL
            )
        )
        return max(MIN_VERIFICATION_INTERVAL, value)

    @property
    def refresh_on_reconnect(self) -> bool:
        """Return whether the secondary provider should refresh after reconnect."""

        return bool(
            self.entry.options.get(
                CONF_REFRESH_ON_RECONNECT, DEFAULT_REFRESH_ON_RECONNECT
            )
        )

    @property
    def enabled(self) -> bool:
        """Return whether synchronization is enabled."""

        return self._enabled

    @property
    def status(self) -> SyncStatus:
        """Return current status."""

        return self._status

    @property
    def diagnostics(self) -> dict[str, Any]:
        """Return non-sensitive runtime diagnostics."""

        return {
            "status": self._status.value,
            "initialized": self._initialized,
            "enabled": self._enabled,
            "primary_entity": self.primary_entity_id,
            "secondary_entity": self.secondary_entity_id,
            "primary_available": self._is_entity_available(self.primary_entity_id),
            "secondary_available": self._is_entity_available(self.secondary_entity_id),
            "verification_interval_minutes": self.verification_interval,
            "conflict_policy": self.conflict_policy.value,
            "refresh_on_reconnect": self.refresh_on_reconnect,
            "shadow_item_count": len(self._shadow),
            "pending_primary_to_secondary": self._pending_primary_to_secondary,
            "pending_secondary_to_primary": self._pending_secondary_to_primary,
            "conflicts_last_sync": self._conflicts_last_sync,
            "last_refresh_mode": self._last_refresh_mode,
            "last_periodic_verification": self._last_periodic_verification,
            "last_periodic_verification_attempt": (
                self._last_periodic_verification_attempt
            ),
            "last_periodic_verification_result": (
                self._last_periodic_verification_result
            ),
            "last_periodic_refresh_mode": self._last_periodic_refresh_mode,
            "periodic_verification_count": self._periodic_verification_count,
            "retry_attempt": self._retry_attempt,
            "retry_count_total": self._retry_count_total,
            "last_retry": self._last_retry,
            "last_retry_result": self._last_retry_result,
            "last_sync": self._last_sync,
            "last_attempt": self._last_attempt,
            "last_error": self._last_error_category,
            "last_error_category": self._last_error_category,
            "last_error_operation": self._last_error_operation,
            "last_error_side": self._last_error_side,
            "last_error_type": self._last_error_type,
        }

    async def async_setup(self) -> None:
        """Load persistent data and start listeners."""

        stored = await self._storage.async_load()
        self._initialized = bool(stored["initialized"])
        self._enabled = bool(stored["enabled"])
        self._shadow = dict(stored["shadow"])
        self._last_sync = stored["last_sync"]
        self._last_error_category = stored["last_error_category"]
        self._last_error_operation = stored["last_error_operation"]
        self._last_error_side = stored["last_error_side"]
        self._last_error_type = stored["last_error_type"]
        self._last_periodic_verification = stored["last_periodic_verification"]
        self._last_periodic_verification_attempt = stored[
            "last_periodic_verification_attempt"
        ]
        self._last_periodic_verification_result = stored[
            "last_periodic_verification_result"
        ]
        self._last_periodic_refresh_mode = stored["last_periodic_refresh_mode"]
        self._periodic_verification_count = stored["periodic_verification_count"]
        self._retry_count_total = stored["retry_count_total"]
        self._last_retry = stored["last_retry"]
        self._last_retry_result = stored["last_retry_result"]

        self._bind_state_listeners()
        self._bind_todo_item_listeners()
        self._bind_periodic_verification()
        self._bind_post_start_verification()

        if not self._enabled:
            self._set_status(SyncStatus.DISABLED)
            return

        # When the integration is added while HA is already running, perform the
        # startup safety pass immediately. During a boot, the post-start callback
        # below performs the same fresh-provider pass after all integrations had a
        # chance to load, avoiding a normal startup race.
        if self.hass.state is CoreState.running:
            self.async_request_sync(
                "startup",
                refresh_secondary=True,
                allow_reload=False,
                immediate=True,
            )

    async def async_shutdown(self) -> None:
        """Stop listeners and outstanding work."""

        for unsubscribe in self._todo_unsubscribers:
            with suppress(Exception):
                unsubscribe()
        self._todo_unsubscribers.clear()

        if self._post_start_unsubscribe is not None:
            with suppress(Exception):
                self._post_start_unsubscribe()
            self._post_start_unsubscribe = None

        for unsubscribe in self._unsubscribers:
            with suppress(Exception):
                unsubscribe()
        self._unsubscribers.clear()

        for task in (self._debounce_task, self._sync_task, self._retry_task):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable or disable synchronization and persist the switch state."""

        self._enabled = enabled
        if enabled:
            self._clear_error()
            self._cancel_retry("reset")
            self._set_status(SyncStatus.INITIALIZING)
            self.async_request_sync("enabled", refresh_secondary=True, immediate=True)
        else:
            self._cancel_retry("disabled")
            self._set_status(SyncStatus.DISABLED)
        await self._async_save()

    def async_request_sync(
        self,
        reason: str,
        *,
        refresh_secondary: bool = False,
        allow_reload: bool = False,
        immediate: bool = False,
        periodic_verification: bool = False,
        from_retry: bool = False,
    ) -> None:
        """Debounce and schedule a synchronization pass."""

        if not self._enabled:
            return

        if not from_retry and self._retry_task and not self._retry_task.done():
            self._cancel_retry("superseded")

        self._pending_reason = reason
        self._pending_refresh_secondary |= refresh_secondary
        self._pending_allow_reload |= allow_reload
        if reason == "periodic_verification" or periodic_verification:
            # Keep this flag separate from the human-readable reason. A normal
            # item event can arrive while the periodic pass is queued and replace
            # _pending_reason, but it must not erase the pending safety check.
            self._pending_periodic_verification = True

        # Never cancel an active reconciliation. Changes that arrive while a pass
        # is running are coalesced into one follow-up pass.
        if self._sync_task and not self._sync_task.done():
            self._rerun_requested = True
            return

        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        delay = 0.0 if immediate else DEBOUNCE_SECONDS
        self._debounce_task = self.hass.async_create_task(
            self._async_delayed_sync(delay),
            f"todo_list_sync_debounce_{self.entry.entry_id}",
        )

    async def async_manual_sync(self) -> None:
        """Run a user-requested full verification immediately."""

        if not self._enabled:
            return
        self.async_request_sync(
            "manual", refresh_secondary=True, allow_reload=False, immediate=True
        )

    async def _async_delayed_sync(self, delay: float) -> None:
        """Wait for the debounce window and then synchronize."""

        if delay:
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

        refresh_secondary = self._pending_refresh_secondary
        allow_reload = self._pending_allow_reload
        periodic_verification = self._pending_periodic_verification
        reason = self._pending_reason
        self._pending_refresh_secondary = False
        self._pending_allow_reload = False
        self._pending_periodic_verification = False

        self._sync_task = self.hass.async_create_task(
            self._async_sync(
                reason,
                refresh_secondary=refresh_secondary,
                allow_reload=allow_reload,
                periodic_verification=periodic_verification,
            ),
            f"todo_list_sync_{self.entry.entry_id}",
        )
        try:
            await self._sync_task
        except asyncio.CancelledError:
            return
        finally:
            self._sync_task = None

        if self._rerun_requested and self._enabled:
            self._rerun_requested = False
            # A real event/follow-up makes any delayed automatic retry obsolete.
            if self._retry_task and not self._retry_task.done():
                self._cancel_retry("superseded")
            self._debounce_task = self.hass.async_create_task(
                self._async_delayed_sync(DEBOUNCE_SECONDS),
                f"todo_list_sync_debounce_{self.entry.entry_id}",
            )

    def _bind_post_start_verification(self) -> None:
        """Request a fresh startup pass once Home Assistant is fully running."""

        if self.hass.state is CoreState.running:
            return

        @callback
        def _started(_event: Event) -> None:
            # Home Assistant consumes async_listen_once listeners before invoking
            # their callback. Clear our local reference so a later config-entry
            # unload does not try to remove the already-consumed listener again.
            self._post_start_unsubscribe = None
            if self._enabled:
                self.async_request_sync(
                    "startup",
                    refresh_secondary=True,
                    allow_reload=False,
                    immediate=True,
                )

        self._post_start_unsubscribe = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _started
        )

    def _bind_state_listeners(self) -> None:
        """Listen for provider availability transitions."""

        @callback
        def _state_changed(event: Event) -> None:
            if self._suppress_events or not self._enabled:
                return
            old_state: State | None = event.data.get("old_state")
            new_state: State | None = event.data.get("new_state")
            entity_id = event.data.get("entity_id")

            old_available = old_state is not None and old_state.state not in {
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }
            new_available = new_state is not None and new_state.state not in {
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            }

            side = "primary" if entity_id == self.primary_entity_id else "secondary"

            # Repairs track entity existence, not provider connectivity. Clear the
            # issue as soon as the entity returns even if it is still unavailable,
            # and create it when an existing state entry is actually removed.
            if (old_state is None) != (new_state is None):
                self._update_missing_repair(side, entity_id)

            # To-do content changes are handled by async_subscribe_updates().
            # Ignore ordinary state/attribute churn while availability is unchanged
            # so provider refreshes do not cause redundant reconciliations.
            if old_available == new_available:
                return

            if new_available:
                refresh_secondary = (
                    entity_id == self.secondary_entity_id and self.refresh_on_reconnect
                )
                self.async_request_sync(
                    f"{side}_reconnected",
                    refresh_secondary=refresh_secondary,
                    allow_reload=refresh_secondary,
                    immediate=True,
                )
                return

            self.async_request_sync(f"{side}_unavailable", immediate=True)

        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                [self.primary_entity_id, self.secondary_entity_id],
                _state_changed,
            )
        )

    def _bind_todo_item_listeners(self) -> None:
        """Subscribe to meaningful to-do item changes without provider-refresh noise."""

        for unsubscribe in self._todo_unsubscribers:
            with suppress(Exception):
                unsubscribe()
        self._todo_unsubscribers.clear()

        for entity_id in (self.primary_entity_id, self.secondary_entity_id):
            entity = self._get_todo_entity(entity_id)
            if entity is None:
                self._todo_item_signatures.pop(entity_id, None)
                continue

            self._todo_item_signatures[entity_id] = self._todo_item_signature(entity)

            @callback
            def _items_changed(_items: Any, *, _entity_id: str = entity_id) -> None:
                current_entity = self._get_todo_entity(_entity_id)
                if current_entity is None:
                    self._todo_item_signatures.pop(_entity_id, None)
                    return

                signature = self._todo_item_signature(current_entity)
                previous = self._todo_item_signatures.get(_entity_id)
                self._todo_item_signatures[_entity_id] = signature

                # Keep the cache fresh even for our own provider writes, but do not
                # recursively schedule synchronization while events are suppressed.
                if self._suppress_events or not self._enabled:
                    return
                if signature == previous:
                    return

                self.async_request_sync("todo_items_changed")

            self._todo_unsubscribers.append(
                entity.async_subscribe_updates(_items_changed)
            )

    def _todo_item_signature(
        self, entity: TodoListEntity
    ) -> tuple[tuple[str, str], ...]:
        """Return the stable semantic signature relevant to synchronization."""

        snapshot = self._snapshot_entity(entity, tracked_keys=set(self._shadow))
        return semantic_signature(snapshot)

    def _bind_periodic_verification(self) -> None:
        """Run a full safety verification no more often than configured."""

        @callback
        def _periodic(_now: Any) -> None:
            if not self._enabled:
                return
            self.async_request_sync(
                "periodic_verification",
                refresh_secondary=True,
                allow_reload=False,
                immediate=True,
                periodic_verification=True,
            )

        self._unsubscribers.append(
            async_track_time_interval(
                self.hass,
                _periodic,
                verification_delta(self.verification_interval),
            )
        )

    async def _async_sync(
        self,
        reason: str,
        *,
        refresh_secondary: bool,
        allow_reload: bool,
        periodic_verification: bool,
    ) -> None:
        """Perform one synchronization pass."""

        if not self._enabled:
            self._set_status(SyncStatus.DISABLED)
            return

        async with self._sync_lock:
            self._last_attempt = dt_util.utcnow().isoformat()
            effective_reason = (
                "periodic_verification" if periodic_verification else reason
            )
            if periodic_verification:
                self._last_periodic_verification_attempt = self._last_attempt
                self._last_periodic_verification_result = "running"
                self._last_periodic_refresh_mode = "not_run"
            self._set_status(SyncStatus.SYNCING)
            _LOGGER.debug("Starting Todo List Sync pass: %s", effective_reason)

            try:
                self._bind_todo_item_listeners()
                self._update_missing_repairs()

                if not self._is_entity_available(self.primary_entity_id):
                    self._update_pending_when_unavailable(primary_available=False)
                    self._set_status(SyncStatus.WAITING_PRIMARY)
                    self._cancel_retry("waiting_primary")
                    if periodic_verification:
                        self._last_periodic_verification_result = "waiting_primary"
                        await self._async_save()
                    return

                if not self._is_entity_available(self.secondary_entity_id):
                    self._update_pending_when_unavailable(primary_available=True)
                    self._set_status(SyncStatus.WAITING_SECONDARY)
                    self._cancel_retry("waiting_secondary")
                    if periodic_verification:
                        self._last_periodic_verification_result = "waiting_secondary"
                        await self._async_save()
                    return

                if refresh_secondary:
                    await self._async_refresh_secondary(allow_reload=allow_reload)
                    if periodic_verification:
                        self._last_periodic_refresh_mode = self._last_refresh_mode
                    # A config-entry reload can replace the underlying Todo entity.
                    self._bind_todo_item_listeners()

                if not self._initialized:
                    await self._async_initial_sync()
                else:
                    await self._async_reconcile()

                was_retrying = self._retry_attempt > 0
                self._clear_error()
                if was_retrying:
                    self._last_retry_result = "recovered"
                self._retry_attempt = 0
                if self._retry_task and not self._retry_task.done():
                    self._retry_task.cancel()
                self._retry_task = None

                if periodic_verification:
                    self._last_periodic_verification = dt_util.utcnow().isoformat()
                    self._last_periodic_verification_result = "synchronized"
                    self._periodic_verification_count += 1
                # Persist cleared error/retry metadata as well as any periodic
                # result. This prevents an old error from reappearing after restart.
                await self._async_save()
                self._set_status(SyncStatus.SYNCHRONIZED)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - provider errors are heterogeneous
                self._record_error(err)
                if periodic_verification:
                    self._last_periodic_verification_result = "error"
                    if (
                        self._last_periodic_refresh_mode == "not_run"
                        and refresh_secondary
                    ):
                        self._last_periodic_refresh_mode = "error"
                self._set_status(SyncStatus.ERROR)
                # Do not log raw provider exception messages or chained service
                # payloads: shopping-list summaries can be embedded in them.
                _LOGGER.error(
                    "Todo List Sync failed during %s: "
                    "category=%s type=%s side=%s operation=%s",
                    effective_reason,
                    self._last_error_category,
                    self._last_error_type,
                    self._last_error_side,
                    self._last_error_operation,
                )

                if self._rerun_requested:
                    self._retry_attempt = 0
                    self._last_retry_result = "superseded"
                else:
                    self._schedule_retry(periodic_verification=periodic_verification)
                await self._async_save()

    async def _async_refresh_secondary(self, *, allow_reload: bool) -> None:
        """Refresh the secondary provider before a safety reconciliation."""

        self._suppress_events += 1
        try:
            try:
                mode = await async_refresh_todo_provider(
                    self.hass,
                    self.secondary_entity_id,
                    allow_config_entry_reload=allow_reload,
                )
            except Exception as err:
                raise SyncFailure(
                    "Secondary provider refresh failed",
                    category="provider_refresh_failed",
                    operation="refresh",
                    side="secondary",
                ) from err
            self._last_refresh_mode = mode
        finally:
            self._suppress_events -= 1

    async def _async_initial_sync(self) -> None:
        """Perform the first non-destructive synchronization."""

        primary_entity = self._require_todo_entity(self.primary_entity_id)
        secondary_entity = self._require_todo_entity(self.secondary_entity_id)
        self._validate_entity_features(primary_entity, self.primary_entity_id)
        self._validate_entity_features(secondary_entity, self.secondary_entity_id)

        primary = self._snapshot_entity(
            primary_entity, tracked_keys=set(), active_only=True
        )
        secondary = self._snapshot_entity(
            secondary_entity, tracked_keys=set(), active_only=True
        )
        desired = build_safe_initial_target(primary, secondary)

        await self._apply_target(
            self.primary_entity_id,
            primary,
            desired,
            allow_delete=False,
            tracked_keys=set(desired),
        )
        await self._apply_target(
            self.secondary_entity_id,
            secondary,
            desired,
            allow_delete=False,
            tracked_keys=set(desired),
        )

        if not await self._confirm_target(
            self.primary_entity_id, desired, tracked_keys=set(desired), subset_ok=True
        ):
            raise SyncFailure(
                "Primary list did not confirm the initial merge",
                category="confirmation_timeout",
                operation="initial_confirm",
                side="primary",
            )
        if not await self._confirm_target(
            self.secondary_entity_id,
            desired,
            tracked_keys=set(desired),
            subset_ok=True,
            refresh_on_timeout=True,
        ):
            raise SyncFailure(
                "Secondary list did not confirm the initial merge",
                category="confirmation_timeout",
                operation="initial_confirm",
                side="secondary",
            )

        self._shadow = desired
        self._initialized = True
        self._pending_primary_to_secondary = 0
        self._pending_secondary_to_primary = 0
        self._conflicts_last_sync = 0
        self._last_sync = dt_util.utcnow().isoformat()

        # The initial confirmation is intentionally subset-based so no pre-existing
        # active item can be deleted. If a user adds a new item during our initial
        # writes, queue a follow-up pass instead of waiting for the 30-minute safety
        # verification.
        self._queue_followup_for_initial_extras(desired)
        await self._async_save()

    async def _async_reconcile(self) -> None:
        """Perform a three-way reconciliation against the persisted shadow."""

        primary_entity = self._require_todo_entity(self.primary_entity_id)
        secondary_entity = self._require_todo_entity(self.secondary_entity_id)
        self._validate_entity_features(primary_entity, self.primary_entity_id)
        self._validate_entity_features(secondary_entity, self.secondary_entity_id)

        tracked_keys = set(self._shadow)
        primary = self._snapshot_entity(primary_entity, tracked_keys=tracked_keys)
        secondary = self._snapshot_entity(secondary_entity, tracked_keys=tracked_keys)

        result = reconcile_three_way(
            self._shadow,
            primary,
            secondary,
            policy=self.conflict_policy,
        )
        desired = result.desired
        self._conflicts_last_sync = len(result.conflicts)
        self._pending_primary_to_secondary = count_semantic_differences(
            secondary, desired
        )
        self._pending_secondary_to_primary = count_semantic_differences(
            primary, desired
        )
        self._notify_entities()

        tracked_after = set(self._shadow) | set(desired)
        await self._apply_target(
            self.primary_entity_id,
            primary,
            desired,
            allow_delete=True,
            tracked_keys=tracked_after,
        )
        await self._apply_target(
            self.secondary_entity_id,
            secondary,
            desired,
            allow_delete=True,
            tracked_keys=tracked_after,
        )

        if not await self._confirm_target(
            self.primary_entity_id, desired, tracked_keys=tracked_after
        ):
            raise SyncFailure(
                "Primary list did not converge",
                category="confirmation_timeout",
                operation="reconcile_confirm",
                side="primary",
            )
        if not await self._confirm_target(
            self.secondary_entity_id,
            desired,
            tracked_keys=tracked_after,
            refresh_on_timeout=True,
        ):
            raise SyncFailure(
                "Secondary list did not converge",
                category="confirmation_timeout",
                operation="reconcile_confirm",
                side="secondary",
            )

        # Only here, after both sides confirm, may the common shadow advance.
        self._shadow = desired
        self._pending_primary_to_secondary = 0
        self._pending_secondary_to_primary = 0
        self._last_sync = dt_util.utcnow().isoformat()
        await self._async_save()

    async def _apply_target(
        self,
        entity_id: str,
        current: dict[str, SyncItem],
        desired: dict[str, SyncItem],
        *,
        allow_delete: bool,
        tracked_keys: set[str],
    ) -> None:
        """Apply a logical target to one Home Assistant to-do entity."""

        self._suppress_events += 1
        try:
            if allow_delete:
                remove_tokens = [
                    (current[key].uid or current[key].summary)
                    for key in sorted(set(current) - set(desired))
                ]
                if remove_tokens:
                    await self._call_todo_service(
                        "remove_item", entity_id, {"item": remove_tokens}
                    )

            for key in sorted(set(current) & set(desired)):
                before = current[key]
                after = desired[key]
                if before.status == after.status:
                    continue
                await self._call_todo_service(
                    "update_item",
                    entity_id,
                    {"item": before.uid or before.summary, "status": after.status},
                )

            completed_to_update: list[str] = []
            for key in sorted(set(desired) - set(current)):
                item = desired[key]
                await self._call_todo_service(
                    "add_item", entity_id, {"item": item.summary}
                )
                if item.status == STATUS_COMPLETED:
                    completed_to_update.append(key)

            if completed_to_update:
                interim_target = {
                    **desired,
                    **{
                        key: SyncItem(
                            summary=desired[key].summary,
                            status=STATUS_NEEDS_ACTION,
                        )
                        for key in completed_to_update
                    },
                }
                await self._confirm_target(
                    entity_id,
                    interim_target,
                    tracked_keys=tracked_keys,
                    subset_ok=not allow_delete,
                    refresh_on_timeout=(entity_id == self.secondary_entity_id),
                )
                refreshed = self._snapshot_entity(
                    self._require_todo_entity(entity_id), tracked_keys=tracked_keys
                )
                for key in completed_to_update:
                    item = refreshed.get(key)
                    if item is None:
                        raise SyncFailure(
                            "New item was not visible after creation",
                            category="confirmation_timeout",
                            operation="add_then_complete",
                            side=self._side_for_entity(entity_id),
                        )
                    await self._call_todo_service(
                        "update_item",
                        entity_id,
                        {"item": item.uid or item.summary, "status": STATUS_COMPLETED},
                    )
        finally:
            self._suppress_events -= 1

    async def _confirm_target(
        self,
        entity_id: str,
        desired: dict[str, SyncItem],
        *,
        tracked_keys: set[str],
        subset_ok: bool = False,
        refresh_on_timeout: bool = False,
    ) -> bool:
        """Wait for an entity cache to reflect successful provider mutations."""

        if self._target_matches(entity_id, desired, tracked_keys, subset_ok=subset_ok):
            return True

        loop = asyncio.get_running_loop()
        deadline = loop.time() + CONFIRM_TIMEOUT_SECONDS
        while loop.time() < deadline:
            await asyncio.sleep(CONFIRM_POLL_SECONDS)
            if self._target_matches(
                entity_id, desired, tracked_keys, subset_ok=subset_ok
            ):
                return True

        if refresh_on_timeout:
            try:
                mode = await async_refresh_todo_provider(
                    self.hass, entity_id, allow_config_entry_reload=False
                )
                self._last_refresh_mode = mode
                self._bind_todo_item_listeners()
            except Exception:  # noqa: BLE001
                _LOGGER.debug(
                    "Provider refresh after confirmation timeout failed for %s",
                    entity_id,
                )
            return self._target_matches(
                entity_id, desired, tracked_keys, subset_ok=subset_ok
            )

        return False

    def _target_matches(
        self,
        entity_id: str,
        desired: dict[str, SyncItem],
        tracked_keys: set[str],
        *,
        subset_ok: bool,
    ) -> bool:
        """Check whether the current logical list matches a desired state."""

        entity = self._get_todo_entity(entity_id)
        if entity is None:
            return False
        current = self._snapshot_entity(entity, tracked_keys=tracked_keys)

        if subset_ok:
            return all(
                semantic_state(current.get(key)) == semantic_state(desired_item)
                for key, desired_item in desired.items()
            )

        if set(current) != set(desired):
            return False
        return all(
            semantic_state(current.get(key)) == semantic_state(desired.get(key))
            for key in desired
        )

    async def _call_todo_service(
        self, service: str, entity_id: str, data: dict[str, Any]
    ) -> None:
        """Call one standard Home Assistant to-do service."""

        payload = {"entity_id": entity_id, **data}
        try:
            await self.hass.services.async_call(
                TODO_DOMAIN,
                service,
                payload,
                blocking=True,
            )
        except Exception as err:
            raise SyncFailure(
                "Home Assistant to-do service call failed",
                category="service_call_failed",
                operation=service,
                side=self._side_for_entity(entity_id),
            ) from err

    def _snapshot_entity(
        self,
        entity: TodoListEntity,
        *,
        tracked_keys: set[str],
        active_only: bool = False,
    ) -> dict[str, SyncItem]:
        """Build a logical item map from a Home Assistant to-do entity."""

        result: dict[str, SyncItem] = {}
        for item in entity.todo_items or []:
            summary = (item.summary or "").strip()
            if not summary:
                continue

            key = normalize_summary(summary)
            raw_status = getattr(item.status, "value", item.status)
            status = str(raw_status or STATUS_NEEDS_ACTION)
            if status not in {STATUS_NEEDS_ACTION, STATUS_COMPLETED}:
                status = STATUS_NEEDS_ACTION

            if status == STATUS_COMPLETED and (active_only or key not in tracked_keys):
                continue

            candidate = SyncItem(summary=summary, status=status, uid=item.uid)
            existing = result.get(key)
            if existing is not None:
                if existing.status == STATUS_NEEDS_ACTION:
                    continue
                if candidate.status == STATUS_NEEDS_ACTION:
                    result[key] = candidate
                continue
            result[key] = candidate
        return result

    def _get_todo_entity(self, entity_id: str) -> TodoListEntity | None:
        """Return the live TodoListEntity object, if loaded."""

        component = self.hass.data.get(DATA_COMPONENT)
        if component is None:
            return None
        entity = component.get_entity(entity_id)
        return entity if isinstance(entity, TodoListEntity) else None

    def _require_todo_entity(self, entity_id: str) -> TodoListEntity:
        """Return a loaded TodoListEntity or raise a privacy-safe error."""

        entity = self._get_todo_entity(entity_id)
        if entity is None:
            raise SyncFailure(
                "Configured to-do entity is not loaded",
                category="entity_not_loaded",
                operation="read",
                side=self._side_for_entity(entity_id),
            )
        return entity

    def _validate_entity_features(self, entity: TodoListEntity, entity_id: str) -> None:
        """Require CRUD capabilities needed for bidirectional synchronization."""

        supported = TodoListEntityFeature(entity.supported_features or 0)
        if supported & _REQUIRED_FEATURES != _REQUIRED_FEATURES:
            raise SyncFailure(
                "Configured to-do entity lacks required CRUD features",
                category="unsupported_entity",
                operation="validate",
                side=self._side_for_entity(entity_id),
            )

    def _is_entity_available(self, entity_id: str) -> bool:
        """Return whether an entity exists, is available and has a live Todo object."""

        state = self.hass.states.get(entity_id)
        return (
            state is not None
            and state.state not in {STATE_UNAVAILABLE, STATE_UNKNOWN}
            and self._get_todo_entity(entity_id) is not None
        )

    def _update_missing_repairs(self) -> None:
        """Create Repairs only for genuinely absent entities after HA is running."""

        self._update_missing_repair("primary", self.primary_entity_id)
        self._update_missing_repair("secondary", self.secondary_entity_id)

    def _update_missing_repair(self, side: str, entity_id: str) -> None:
        """Synchronize the Repairs issue for one configured side."""

        state = self.hass.states.get(entity_id)
        if state is not None:
            clear_missing_list_issue(self.hass, entry_id=self.entry.entry_id, side=side)
            return

        if self.hass.state is not CoreState.running:
            return

        create_missing_list_issue(
            self.hass,
            entry_id=self.entry.entry_id,
            entry_title=self.entry.title,
            side=side,
            entity_id=entity_id,
        )

    def _update_pending_when_unavailable(self, *, primary_available: bool) -> None:
        """Estimate pending changes while one side cannot be inspected."""

        self._pending_primary_to_secondary = 0
        self._pending_secondary_to_primary = 0

        if primary_available:
            entity = self._get_todo_entity(self.primary_entity_id)
            if entity is not None:
                current = self._snapshot_entity(entity, tracked_keys=set(self._shadow))
                self._pending_primary_to_secondary = count_semantic_differences(
                    current, self._shadow
                )
        else:
            entity = self._get_todo_entity(self.secondary_entity_id)
            if entity is not None and self._is_entity_available(
                self.secondary_entity_id
            ):
                current = self._snapshot_entity(entity, tracked_keys=set(self._shadow))
                self._pending_secondary_to_primary = count_semantic_differences(
                    current, self._shadow
                )
        self._notify_entities()

    def _queue_followup_for_initial_extras(self, desired: dict[str, SyncItem]) -> None:
        """Catch meaningful list changes that occurred during initial writes."""

        expected = semantic_signature(desired)
        tracked_keys = set(desired)
        for entity_id in (self.primary_entity_id, self.secondary_entity_id):
            entity = self._get_todo_entity(entity_id)
            if entity is None:
                continue
            current = self._snapshot_entity(entity, tracked_keys=tracked_keys)
            if semantic_signature(current) != expected:
                self._rerun_requested = True
                return

    def _schedule_retry(self, *, periodic_verification: bool) -> None:
        """Schedule the next bounded retry, if the budget is not exhausted."""

        if not self._enabled:
            return
        delay = next_retry_delay(self._retry_attempt)
        if delay is None:
            self._last_retry_result = "exhausted"
            return

        self._retry_attempt += 1
        self._last_retry_result = "scheduled"
        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
        self._retry_task = self.hass.async_create_task(
            self._async_retry_after_delay(delay, periodic_verification),
            f"todo_list_sync_retry_{self.entry.entry_id}_{self._retry_attempt}",
        )

    async def _async_retry_after_delay(
        self, delay: float, periodic_verification: bool
    ) -> None:
        """Run one automatic retry after the configured backoff delay."""

        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return

        if not self._enabled:
            return

        self._retry_count_total += 1
        self._last_retry = dt_util.utcnow().isoformat()
        self._last_retry_result = "running"
        # After a partial mutation, request a fresh secondary snapshot when a
        # lightweight provider helper exists. Never repeat a heavy config reload
        # automatically during the retry sequence.
        self.async_request_sync(
            "automatic_retry",
            refresh_secondary=True,
            allow_reload=False,
            immediate=True,
            periodic_verification=periodic_verification,
            from_retry=True,
        )

    def _cancel_retry(self, result: str) -> None:
        """Cancel a pending retry and reset the current retry sequence."""

        if self._retry_task and not self._retry_task.done():
            self._retry_task.cancel()
        self._retry_task = None
        if self._retry_attempt:
            self._last_retry_result = result
        self._retry_attempt = 0

    def _record_error(self, err: Exception) -> None:
        """Record structured diagnostics without provider/item message text."""

        if isinstance(err, SyncFailure):
            self._last_error_category = err.category
            self._last_error_operation = err.operation
            self._last_error_side = err.side
        else:
            self._last_error_category = "unexpected_error"
            self._last_error_operation = None
            self._last_error_side = None
        self._last_error_type = type(err).__name__

    def _clear_error(self) -> None:
        """Clear the privacy-safe error metadata after recovery."""

        self._last_error_category = None
        self._last_error_operation = None
        self._last_error_side = None
        self._last_error_type = None

    def _side_for_entity(self, entity_id: str) -> str:
        """Return the configured side for an entity id."""

        return "primary" if entity_id == self.primary_entity_id else "secondary"

    async def _async_save(self) -> None:
        """Persist runtime state."""

        await self._storage.async_save(
            initialized=self._initialized,
            enabled=self._enabled,
            shadow=self._shadow,
            last_sync=self._last_sync,
            last_error_category=self._last_error_category,
            last_error_operation=self._last_error_operation,
            last_error_side=self._last_error_side,
            last_error_type=self._last_error_type,
            last_periodic_verification=self._last_periodic_verification,
            last_periodic_verification_attempt=self._last_periodic_verification_attempt,
            last_periodic_verification_result=self._last_periodic_verification_result,
            last_periodic_refresh_mode=self._last_periodic_refresh_mode,
            periodic_verification_count=self._periodic_verification_count,
            retry_count_total=self._retry_count_total,
            last_retry=self._last_retry,
            last_retry_result=self._last_retry_result,
        )
        self._notify_entities()

    def _set_status(self, status: SyncStatus) -> None:
        """Update status and notify diagnostic entities."""

        self._status = status
        self._notify_entities()

    def _notify_entities(self) -> None:
        """Notify this config entry's diagnostic entities."""

        async_dispatcher_send(self.hass, update_signal(self.entry.entry_id))
