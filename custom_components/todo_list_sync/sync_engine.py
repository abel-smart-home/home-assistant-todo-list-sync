"""Pure three-way reconciliation logic for Todo List Sync."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .const import ConflictPolicy
from .model import STATUS_NEEDS_ACTION, SyncItem

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    """Result of a three-way list reconciliation."""

    desired: dict[str, SyncItem]
    conflicts: tuple[str, ...]
    primary_changed: tuple[str, ...]
    secondary_changed: tuple[str, ...]


def normalize_summary(summary: str) -> str:
    """Normalize an item name for comparison without changing display text.

    Comparison is case-insensitive, accent-insensitive and whitespace-insensitive.
    This intentionally treats values such as "Limón", "limon" and " LIMON " as
    the same logical shopping-list item.
    """

    normalized = unicodedata.normalize("NFKD", summary.strip())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    return normalized.casefold()


def semantic_state(item: SyncItem | None) -> str | None:
    """Return the part of an item that participates in conflict detection."""

    return None if item is None else item.status


def semantic_signature(items: dict[str, SyncItem]) -> tuple[tuple[str, str], ...]:
    """Return a stable signature for the list semantics Todo List Sync tracks.

    Provider refreshes can notify Home Assistant to-do subscribers even when the
    item contents did not change.  The signature intentionally ignores ordering,
    display-only spelling/case differences already normalized into the mapping
    key, UIDs and provider metadata.
    """

    return tuple(sorted((key, item.status) for key, item in items.items()))


def _preferred_item(
    primary: SyncItem | None,
    secondary: SyncItem | None,
    shadow: SyncItem | None,
    policy: ConflictPolicy,
) -> SyncItem | None:
    """Choose an item's display representation after state has been resolved."""

    if policy == ConflictPolicy.SECONDARY:
        return secondary or primary or shadow
    return primary or secondary or shadow


def reconcile_three_way(
    shadow: dict[str, SyncItem],
    primary: dict[str, SyncItem],
    secondary: dict[str, SyncItem],
    policy: ConflictPolicy = ConflictPolicy.PRIMARY,
) -> ReconcileResult:
    """Merge primary and secondary changes against the last common shadow.

    A change on only one side is propagated to the other side. If both sides
    changed the same logical item to different states, the configured conflict
    policy decides the result. Independent changes on different items are merged.
    """

    desired: dict[str, SyncItem] = {}
    conflicts: list[str] = []
    primary_changed: list[str] = []
    secondary_changed: list[str] = []

    all_keys = set(shadow) | set(primary) | set(secondary)
    for key in sorted(all_keys):
        old = shadow.get(key)
        p_item = primary.get(key)
        s_item = secondary.get(key)

        old_state = semantic_state(old)
        p_state = semantic_state(p_item)
        s_state = semantic_state(s_item)

        p_changed = p_state != old_state
        s_changed = s_state != old_state

        if p_changed:
            primary_changed.append(key)
        if s_changed:
            secondary_changed.append(key)

        chosen: SyncItem | None
        if not p_changed and not s_changed:
            chosen = _preferred_item(p_item, s_item, old, policy)
        elif p_changed and not s_changed:
            chosen = p_item
        elif s_changed and not p_changed:
            chosen = s_item
        elif p_state == s_state:
            # Both changed, but to the same semantic result.
            chosen = _preferred_item(p_item, s_item, old, policy)
        else:
            conflicts.append(key)
            chosen = p_item if policy == ConflictPolicy.PRIMARY else s_item

        if chosen is not None:
            desired[key] = SyncItem(summary=chosen.summary, status=chosen.status)

    return ReconcileResult(
        desired=desired,
        conflicts=tuple(conflicts),
        primary_changed=tuple(primary_changed),
        secondary_changed=tuple(secondary_changed),
    )


def build_safe_initial_target(
    primary: dict[str, SyncItem], secondary: dict[str, SyncItem]
) -> dict[str, SyncItem]:
    """Create a non-destructive first-sync target from active items only.

    Existing completed history is intentionally excluded. The primary list wins
    display-name differences when the same normalized item exists on both sides.
    """

    desired: dict[str, SyncItem] = {}
    for key in sorted(set(primary) | set(secondary)):
        item = primary.get(key) or secondary.get(key)
        if item is None:
            continue
        desired[key] = SyncItem(summary=item.summary, status=STATUS_NEEDS_ACTION)
    return desired


def count_semantic_differences(
    current: dict[str, SyncItem], desired: dict[str, SyncItem]
) -> int:
    """Count logical additions, removals or status changes."""

    count = 0
    for key in set(current) | set(desired):
        if semantic_state(current.get(key)) != semantic_state(desired.get(key)):
            count += 1
    return count
