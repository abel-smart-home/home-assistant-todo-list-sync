# Architecture

## Goal

Synchronize two existing Home Assistant `todo` entities while preserving a local authoritative list and surviving temporary provider outages without blindly overwriting either side.

## Core model

Todo List Sync stores a persistent **shadow**: the last state that was confirmed on both sides.

```text
Primary current ─┐
                 ├─ three-way reconcile ─ desired common state
Shadow ──────────┤
                 │
Secondary current┘
```

A logical item is keyed by a normalized summary. The shadow stores only:

- display summary
- `needs_action` / `completed` status

Provider UIDs are never stored in the shadow because they are provider-specific and can change when an item is recreated.

## Normalization

`normalize_summary()` applies:

1. trim
2. Unicode NFKD decomposition
3. removal of combining marks
4. whitespace collapsing
5. case folding

This is optimized for spoken shopping-list input where capitalization and accents can vary.

## Change classification

For each logical key:

- compare Primary to Shadow
- compare Secondary to Shadow

Cases:

1. Neither side changed → keep state.
2. Only Primary changed → propagate Primary.
3. Only Secondary changed → propagate Secondary.
4. Both changed to the same semantic state → accept it.
5. Both changed differently → true conflict; configured policy decides.

## Initial sync

The first sync uses only active items and performs a union. It does not delete items.

Historical completed items are intentionally excluded.

## Completed items after initialization

A completed item is read only if its normalized key is already present in the shadow. This lets the integration detect completion of a previously active tracked item without importing unrelated old completion history.

If both an active and completed item with the same normalized key exist on one provider, the active item wins the logical snapshot.

## Event model

The manager subscribes directly to each live `TodoListEntity.async_subscribe_updates()` callback and also tracks normal Home Assistant state changes for availability transitions.

Changes are debounced before reconciliation to avoid event storms and feedback loops.

## Provider verification

Periodic verification is limited to a minimum of 30 minutes.

### Alexa Devices 2026.8.x

The Alexa Devices coordinator currently exposes `sync_todo_list_items()` on its config-entry runtime data. Todo List Sync detects this method dynamically and uses it for a fresh list snapshot.

After that call, it asks the coordinator to notify its listeners so the `todo` entity exposes the refreshed cache.

No direct import from `homeassistant.components.alexa_devices` is used. This isolates the compatibility risk.

### Generic providers

If no safe lightweight refresh method is known, periodic verification compares the provider's current Home Assistant cache.

A full config-entry reload is allowed only as a reconnect fallback when configured. It is not used every 30 minutes.

## Write confirmation

Cloud-backed list writes can be eventually consistent. After changing a list, Todo List Sync waits for the Home Assistant entity cache to confirm the desired logical state.

If the secondary confirmation times out, the provider refresh adapter gets one chance to retrieve a fresh snapshot before the pass is marked as failed.

The shadow advances only after both sides confirm convergence.

## Storage

Each config entry uses a private Home Assistant `Store` key:

```text
todo_list_sync.<config_entry_id>
```

Stored data:

- initialized flag
- enabled flag
- shadow
- last successful sync timestamp
- last error

## Diagnostics privacy

The diagnostics endpoint deliberately returns counts and status only. It does not return shopping-list summaries or the raw shadow.
