"""Focused manager recovery tests without real providers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.core import CoreState

from custom_components.todo_list_sync import manager as manager_module
from custom_components.todo_list_sync.const import (
    CONF_PRIMARY_ENTITY,
    CONF_SECONDARY_ENTITY,
    SyncStatus,
)
from custom_components.todo_list_sync.manager import SyncFailure, TodoListSyncManager
from custom_components.todo_list_sync.model import SyncItem


class FakeStorage:
    """Minimal storage double."""

    async def async_load(self):
        return {
            "initialized": True,
            "enabled": True,
            "shadow": {},
            "last_sync": None,
            "last_error_category": None,
            "last_error_operation": None,
            "last_error_side": None,
            "last_error_type": None,
            "last_periodic_verification": None,
            "last_periodic_verification_attempt": None,
            "last_periodic_verification_result": None,
            "last_periodic_refresh_mode": None,
            "periodic_verification_count": 0,
            "retry_count_total": 0,
            "last_retry": None,
            "last_retry_result": None,
        }

    async def async_save(self, **kwargs):
        self.saved = kwargs


def _entry():
    return SimpleNamespace(
        entry_id="entry-1",
        title="Primary ↔ Secondary",
        data={
            CONF_PRIMARY_ENTITY: "todo.primary",
            CONF_SECONDARY_ENTITY: "todo.secondary",
        },
        options={},
    )


def _hass():
    return SimpleNamespace(
        state=CoreState.running,
        data={},
        states=SimpleNamespace(get=lambda _entity_id: None),
        bus=SimpleNamespace(async_listen_once=lambda *_args: (lambda: None)),
    )


@pytest.mark.asyncio
async def test_running_startup_requests_fresh_secondary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    sync_manager = TodoListSyncManager(_hass(), _entry())
    monkeypatch.setattr(sync_manager, "_bind_state_listeners", lambda: None)
    monkeypatch.setattr(sync_manager, "_bind_todo_item_listeners", lambda: None)
    monkeypatch.setattr(sync_manager, "_bind_periodic_verification", lambda: None)
    monkeypatch.setattr(sync_manager, "_bind_post_start_verification", lambda: None)
    request = Mock()
    monkeypatch.setattr(sync_manager, "async_request_sync", request)

    await sync_manager.async_setup()

    request.assert_called_once_with(
        "startup", refresh_secondary=True, allow_reload=False, immediate=True
    )


@pytest.mark.asyncio
async def test_failed_reconcile_preserves_shadow_and_schedules_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    sync_manager = TodoListSyncManager(_hass(), _entry())
    sync_manager._initialized = True
    sync_manager._shadow = {"milk": SyncItem("Milk")}
    original_shadow = dict(sync_manager._shadow)

    monkeypatch.setattr(sync_manager, "_notify_entities", lambda: None)
    monkeypatch.setattr(sync_manager, "_bind_todo_item_listeners", lambda: None)
    monkeypatch.setattr(sync_manager, "_update_missing_repairs", lambda: None)
    monkeypatch.setattr(sync_manager, "_is_entity_available", lambda _id: True)
    monkeypatch.setattr(
        sync_manager,
        "_async_reconcile",
        AsyncMock(
            side_effect=SyncFailure(
                "safe failure",
                category="service_call_failed",
                operation="add_item",
                side="secondary",
            )
        ),
    )
    monkeypatch.setattr(sync_manager, "_async_save", AsyncMock())
    schedule_retry = Mock()
    monkeypatch.setattr(sync_manager, "_schedule_retry", schedule_retry)

    await sync_manager._async_sync(
        "test",
        refresh_secondary=False,
        allow_reload=False,
        periodic_verification=False,
    )

    assert sync_manager._shadow == original_shadow
    assert sync_manager.status is SyncStatus.ERROR
    assert sync_manager.diagnostics["last_error_category"] == "service_call_failed"
    schedule_retry.assert_called_once_with(periodic_verification=False)


def test_error_diagnostics_do_not_expose_exception_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    sync_manager = TodoListSyncManager(_hass(), _entry())
    sync_manager._record_error(RuntimeError("PRIVATE-TEST-ITEM-9371"))
    assert "PRIVATE-TEST-ITEM-9371" not in repr(sync_manager.diagnostics)
    assert sync_manager.diagnostics["last_error_category"] == "unexpected_error"
    assert sync_manager.diagnostics["last_error_type"] == "RuntimeError"


def test_initial_extra_change_queues_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    sync_manager = TodoListSyncManager(_hass(), _entry())
    desired = {"milk": SyncItem("Milk")}
    primary = object()
    secondary = object()
    monkeypatch.setattr(
        sync_manager,
        "_get_todo_entity",
        lambda entity_id: primary if entity_id == "todo.primary" else secondary,
    )
    monkeypatch.setattr(
        sync_manager,
        "_snapshot_entity",
        lambda entity, **_kwargs: (
            {"milk": SyncItem("Milk"), "bread": SyncItem("Bread")}
            if entity is primary
            else desired
        ),
    )

    sync_manager._queue_followup_for_initial_extras(desired)

    assert sync_manager._rerun_requested is True

@pytest.mark.asyncio
async def test_boot_defers_fresh_startup_pass_until_home_assistant_started(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    captured = {}

    def listen_once(_event_type, callback):
        captured["callback"] = callback
        return lambda: None

    hass = _hass()
    hass.state = CoreState.starting
    hass.bus = SimpleNamespace(async_listen_once=listen_once)
    sync_manager = TodoListSyncManager(hass, _entry())
    monkeypatch.setattr(sync_manager, "_bind_state_listeners", lambda: None)
    monkeypatch.setattr(sync_manager, "_bind_todo_item_listeners", lambda: None)
    monkeypatch.setattr(sync_manager, "_bind_periodic_verification", lambda: None)
    request = Mock()
    monkeypatch.setattr(sync_manager, "async_request_sync", request)

    await sync_manager.async_setup()
    request.assert_not_called()

    captured["callback"](SimpleNamespace())
    request.assert_called_once_with(
        "startup", refresh_secondary=True, allow_reload=False, immediate=True
    )


def test_temporary_unavailable_state_does_not_create_missing_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    hass = _hass()
    hass.states = SimpleNamespace(
        get=lambda _entity_id: SimpleNamespace(state="unavailable")
    )
    sync_manager = TodoListSyncManager(hass, _entry())
    create = Mock()
    clear = Mock()
    monkeypatch.setattr(manager_module, "create_missing_list_issue", create)
    monkeypatch.setattr(manager_module, "clear_missing_list_issue", clear)

    sync_manager._update_missing_repair("secondary", "todo.secondary")

    create.assert_not_called()
    clear.assert_called_once()


def test_absent_entity_after_start_creates_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    sync_manager = TodoListSyncManager(_hass(), _entry())
    create = Mock()
    monkeypatch.setattr(manager_module, "create_missing_list_issue", create)
    monkeypatch.setattr(manager_module, "clear_missing_list_issue", Mock())

    sync_manager._update_missing_repair("secondary", "todo.secondary")

    create.assert_called_once_with(
        sync_manager.hass,
        entry_id="entry-1",
        entry_title="Primary ↔ Secondary",
        side="secondary",
        entity_id="todo.secondary",
    )


class FakeTask:
    """Small task double used for scheduling tests."""

    def __init__(self) -> None:
        self.cancelled = False

    def done(self) -> bool:
        return False

    def cancel(self) -> None:
        self.cancelled = True


def test_real_event_supersedes_pending_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    hass = _hass()

    def create_task(coro, _name):
        coro.close()
        return FakeTask()

    hass.async_create_task = create_task
    sync_manager = TodoListSyncManager(hass, _entry())
    retry_task = FakeTask()
    sync_manager._retry_task = retry_task
    sync_manager._retry_attempt = 2

    sync_manager.async_request_sync("todo_items_changed")

    assert retry_task.cancelled is True
    assert sync_manager._retry_attempt == 0
    assert sync_manager._last_retry_result == "superseded"


def test_retry_budget_exhaustion_is_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    sync_manager = TodoListSyncManager(_hass(), _entry())
    sync_manager._retry_attempt = 3

    sync_manager._schedule_retry(periodic_verification=False)

    assert sync_manager._retry_task is None
    assert sync_manager._last_retry_result == "exhausted"


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["add_item", "remove_item", "update_item"])
async def test_todo_service_failures_are_structured_and_private(
    service: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    hass = _hass()
    hass.services = SimpleNamespace(
        async_call=AsyncMock(side_effect=RuntimeError("PRIVATE-TEST-ITEM-9371"))
    )
    sync_manager = TodoListSyncManager(hass, _entry())

    with pytest.raises(SyncFailure) as exc_info:
        await sync_manager._call_todo_service(
            service,
            "todo.secondary",
            {"item": "PRIVATE-TEST-ITEM-9371"},
        )

    sync_manager._record_error(exc_info.value)
    diagnostics = repr(sync_manager.diagnostics)
    assert "PRIVATE-TEST-ITEM-9371" not in diagnostics
    assert sync_manager.diagnostics["last_error_category"] == "service_call_failed"
    assert sync_manager.diagnostics["last_error_operation"] == service
    assert sync_manager.diagnostics["last_error_side"] == "secondary"


def test_state_listener_updates_repairs_on_existence_changes_even_if_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(manager_module, "SyncStorage", lambda *_args: FakeStorage())
    captured = {}

    def track(_hass, _entity_ids, callback):
        captured["callback"] = callback
        return lambda: None

    monkeypatch.setattr(manager_module, "async_track_state_change_event", track)
    sync_manager = TodoListSyncManager(_hass(), _entry())
    repair = Mock()
    request = Mock()
    monkeypatch.setattr(sync_manager, "_update_missing_repair", repair)
    monkeypatch.setattr(sync_manager, "async_request_sync", request)
    sync_manager._bind_state_listeners()

    unavailable = SimpleNamespace(state="unavailable")
    captured["callback"](
        SimpleNamespace(
            data={
                "entity_id": "todo.secondary",
                "old_state": None,
                "new_state": unavailable,
            }
        )
    )
    repair.assert_called_once_with("secondary", "todo.secondary")
    request.assert_not_called()

    repair.reset_mock()
    captured["callback"](
        SimpleNamespace(
            data={
                "entity_id": "todo.secondary",
                "old_state": unavailable,
                "new_state": None,
            }
        )
    )
    repair.assert_called_once_with("secondary", "todo.secondary")
