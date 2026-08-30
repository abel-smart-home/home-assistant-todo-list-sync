"""Integration lifecycle regression tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import custom_components.todo_list_sync as integration


@pytest.mark.asyncio
async def test_remove_entry_cleans_storage_and_repairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_instance = SimpleNamespace(async_remove=AsyncMock())
    storage_factory = Mock(return_value=storage_instance)
    clear_repairs = Mock()
    monkeypatch.setattr(integration, "SyncStorage", storage_factory)
    monkeypatch.setattr(integration, "clear_all_missing_list_issues", clear_repairs)

    hass = SimpleNamespace()
    entry = SimpleNamespace(entry_id="entry-1")

    await integration.async_remove_entry(hass, entry)

    storage_factory.assert_called_once_with(hass, "entry-1")
    storage_instance.async_remove.assert_awaited_once()
    clear_repairs.assert_called_once_with(hass, entry_id="entry-1")
