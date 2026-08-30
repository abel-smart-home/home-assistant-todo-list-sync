"""Unit tests for the pure three-way synchronization engine."""

from custom_components.todo_list_sync.const import ConflictPolicy
from custom_components.todo_list_sync.model import (
    STATUS_COMPLETED,
    STATUS_NEEDS_ACTION,
    SyncItem,
)
from custom_components.todo_list_sync.sync_engine import (
    build_safe_initial_target,
    normalize_summary,
    reconcile_three_way,
)


def _item(name: str, status: str = STATUS_NEEDS_ACTION) -> SyncItem:
    return SyncItem(summary=name, status=status)


def test_normalization_is_case_accent_and_space_insensitive() -> None:
    assert normalize_summary("  LIMÓN  ") == normalize_summary("limon")


def test_safe_initial_target_is_union() -> None:
    primary = {normalize_summary("Milk"): _item("Milk")}
    secondary = {normalize_summary("Bread"): _item("Bread")}
    desired = build_safe_initial_target(primary, secondary)
    assert set(desired) == {normalize_summary("Milk"), normalize_summary("Bread")}


def test_independent_offline_changes_are_merged() -> None:
    shadow = {
        normalize_summary("Milk"): _item("Milk"),
        normalize_summary("Bread"): _item("Bread"),
        normalize_summary("Eggs"): _item("Eggs"),
        normalize_summary("Coffee"): _item("Coffee"),
    }
    primary = {
        normalize_summary("Milk"): _item("Milk"),
        normalize_summary("Bread"): _item("Bread"),
        normalize_summary("Eggs"): _item("Eggs"),
        normalize_summary("Tortillas"): _item("Tortillas"),
    }
    secondary = {
        normalize_summary("Milk"): _item("Milk"),
        normalize_summary("Bread"): _item("Bread"),
        normalize_summary("Coffee"): _item("Coffee"),
        normalize_summary("Cheese"): _item("Cheese"),
    }

    result = reconcile_three_way(shadow, primary, secondary)
    names = {item.summary for item in result.desired.values()}
    assert names == {"Milk", "Bread", "Tortillas", "Cheese"}
    assert not result.conflicts


def test_true_conflict_primary_wins() -> None:
    key = normalize_summary("Milk")
    shadow = {key: _item("Milk")}
    primary = {key: _item("Milk", STATUS_COMPLETED)}
    secondary = {}

    result = reconcile_three_way(
        shadow, primary, secondary, policy=ConflictPolicy.PRIMARY
    )
    assert result.desired[key].status == STATUS_COMPLETED
    assert result.conflicts == (key,)


def test_true_conflict_secondary_wins() -> None:
    key = normalize_summary("Milk")
    shadow = {key: _item("Milk")}
    primary = {key: _item("Milk", STATUS_COMPLETED)}
    secondary = {}

    result = reconcile_three_way(
        shadow, primary, secondary, policy=ConflictPolicy.SECONDARY
    )
    assert key not in result.desired
    assert result.conflicts == (key,)
