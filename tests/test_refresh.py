"""Provider refresh adapter tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.todo_list_sync import refresh


@pytest.mark.asyncio
async def test_unknown_provider_falls_back_to_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = SimpleNamespace(async_get=lambda _entity_id: None)
    monkeypatch.setattr(refresh.er, "async_get", lambda _hass: registry)
    hass = SimpleNamespace()
    assert (
        await refresh.async_refresh_todo_provider(hass, "todo.generic") == "cache_only"
    )


@pytest.mark.asyncio
async def test_alexa_runtime_helper_is_feature_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_sync = AsyncMock()
    notify = Mock()
    runtime = SimpleNamespace(
        sync_todo_list_items=full_sync,
        async_update_listeners=notify,
    )
    config_entry = SimpleNamespace(entry_id="cfg", runtime_data=runtime)
    registry_entry = SimpleNamespace(
        config_entry_id="cfg",
        platform="alexa_devices",
    )
    registry = SimpleNamespace(async_get=lambda _entity_id: registry_entry)
    monkeypatch.setattr(refresh.er, "async_get", lambda _hass: registry)
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_get_entry=lambda _entry_id: config_entry)
    )

    mode = await refresh.async_refresh_todo_provider(hass, "todo.alexa")

    assert mode == "alexa_full_sync"
    full_sync.assert_awaited_once()
    notify.assert_called_once()


@pytest.mark.asyncio
async def test_alexa_without_known_runtime_helper_falls_back_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = SimpleNamespace()
    config_entry = SimpleNamespace(entry_id="cfg", runtime_data=runtime)
    registry_entry = SimpleNamespace(
        config_entry_id="cfg",
        platform="alexa_devices",
    )
    registry = SimpleNamespace(async_get=lambda _entity_id: registry_entry)
    monkeypatch.setattr(refresh.er, "async_get", lambda _hass: registry)
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_get_entry=lambda _entry_id: config_entry)
    )

    mode = await refresh.async_refresh_todo_provider(hass, "todo.alexa")

    assert mode == "cache_only"
