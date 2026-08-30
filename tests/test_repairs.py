"""Repairs helper regression tests."""

from types import SimpleNamespace

import pytest

from custom_components.todo_list_sync import repairs


def test_missing_list_issue_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        repairs.ir,
        "async_create_issue",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    repairs.create_missing_list_issue(
        SimpleNamespace(),
        entry_id="entry",
        entry_title="Primary ↔ Secondary",
        side="secondary",
        entity_id="todo.remote",
    )
    assert calls
    _, kwargs = calls[0]
    assert kwargs["translation_key"] == "configured_list_missing"
    assert kwargs["translation_placeholders"]["entity_id"] == "todo.remote"
    assert kwargs["is_persistent"] is True


def test_clear_all_repairs_clears_both_sides(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted = []
    monkeypatch.setattr(
        repairs.ir,
        "async_delete_issue",
        lambda _hass, _domain, issue_id: deleted.append(issue_id),
    )
    repairs.clear_all_missing_list_issues(SimpleNamespace(), entry_id="abc")
    assert deleted == ["missing_primary_abc", "missing_secondary_abc"]
