"""Storage safety and migration tests."""

from types import SimpleNamespace

import pytest

from custom_components.todo_list_sync import storage


class FakeStore:
    """Capture Store construction and data calls."""

    created_kwargs = None

    def __init__(self, *args, **kwargs):
        type(self).created_kwargs = kwargs
        self.data = None
        self.removed = False

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data

    async def async_remove(self):
        self.removed = True


def test_storage_uses_atomic_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "Store", FakeStore)
    storage.SyncStorage(SimpleNamespace(), "entry-id")
    assert FakeStore.created_kwargs["private"] is True
    assert FakeStore.created_kwargs["atomic_writes"] is True


@pytest.mark.asyncio
async def test_legacy_raw_error_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "Store", FakeStore)
    sync_storage = storage.SyncStorage(SimpleNamespace(), "entry-id")
    sync_storage._store.data = {"last_error": "PRIVATE-TEST-ITEM-9371 failed"}
    loaded = await sync_storage.async_load()
    assert loaded["last_error_category"] == "legacy_error_redacted"
    assert "PRIVATE-TEST-ITEM-9371" not in repr(loaded)

@pytest.mark.asyncio
async def test_storage_can_be_removed_with_config_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(storage, "Store", FakeStore)
    sync_storage = storage.SyncStorage(SimpleNamespace(), "entry-id")
    await sync_storage.async_remove()
    assert sync_storage._store.removed is True
