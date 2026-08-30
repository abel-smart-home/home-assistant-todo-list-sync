"""Home Assistant Repairs helpers for Todo List Sync."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def missing_list_issue_id(entry_id: str, side: str) -> str:
    """Return a stable issue id for one configured side."""

    return f"missing_{side}_{entry_id}"


def create_missing_list_issue(
    hass: HomeAssistant,
    *,
    entry_id: str,
    entry_title: str,
    side: str,
    entity_id: str,
) -> None:
    """Create or update the repair issue for a genuinely missing entity."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        missing_list_issue_id(entry_id, side),
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="configured_list_missing",
        translation_placeholders={
            "entry_title": entry_title,
            "side": side,
            "entity_id": entity_id,
        },
    )


def clear_missing_list_issue(
    hass: HomeAssistant, *, entry_id: str, side: str
) -> None:
    """Clear a stale missing-list repair issue."""

    ir.async_delete_issue(hass, DOMAIN, missing_list_issue_id(entry_id, side))


def clear_all_missing_list_issues(hass: HomeAssistant, *, entry_id: str) -> None:
    """Clear all repair issues belonging to a removed synchronization entry."""

    clear_missing_list_issue(hass, entry_id=entry_id, side="primary")
    clear_missing_list_issue(hass, entry_id=entry_id, side="secondary")
