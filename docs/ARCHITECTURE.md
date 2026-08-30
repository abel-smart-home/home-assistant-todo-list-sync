# Architecture

## Goal

Synchronize two existing Home Assistant `todo` entities while preserving an authoritative Primary list and surviving temporary provider outages without blindly overwriting either side.

Todo List Sync is provider-agnostic at the synchronization layer. Its principal design and validation target is **Home Assistant Local To-do ↔ Alexa Devices**, but any pair of Home Assistant `todo.*` entities can be used when both support create, update and delete operations.

## Core model

Todo List Sync stores a persistent **shadow**: the last logical state that was confirmed on both sides.

```text
Primary current ─┐
                 ├─ three-way reconcile ─ desired common state
Shadow ──────────┤
                 │
Secondary current┘
```

The shadow advances only after both sides confirm convergence.

A logical item is keyed by a normalized summary. The shadow stores only:

- display summary;
- `needs_action` / `completed` status.

Provider UIDs are not persisted because they are provider-specific and can change when an item is recreated.

## Normalization

`normalize_summary()` applies trim, Unicode NFKD decomposition, combining-mark removal, whitespace collapsing and case folding.

This is especially useful for spoken shopping-list input where capitalization and accents can vary.

## Change classification

For each logical key:

1. Neither side changed → keep state.
2. Only Primary changed → propagate Primary.
3. Only Secondary changed → propagate Secondary.
4. Both changed to the same semantic state → accept it.
5. Both changed differently → true conflict; configured policy decides.

## Initial synchronization

The first synchronization uses active items only and performs a union. It never deletes active items.

Historical completed items are intentionally excluded.

The initial confirmation is subset-based for safety. v0.1.6 performs a final semantic check after the writes; if a user added an active item during that window, a follow-up reconciliation is queued immediately instead of waiting for the periodic verification.

## Completed items after initialization

A completed item is read only when its normalized key is already present in the shadow. This synchronizes completion of tracked active items without importing unrelated historical completed entries.

If a provider contains both a completed and an active item with the same normalized name, the active item wins the logical snapshot.

## Event model

The manager subscribes directly to each loaded `TodoListEntity.async_subscribe_updates()` callback and tracks normal Home Assistant state changes only for availability transitions.

Semantic signatures suppress provider/coordinator notifications when membership and active/completed state did not change.

Events are debounced. A synchronization already in progress is never cancelled; new changes are coalesced into one follow-up pass.

## Startup and provider verification

If Home Assistant is still booting, the manager registers a one-shot post-start verification. Once Home Assistant reaches the running state, the startup pass asks the Secondary provider for a fresh lightweight snapshot when a compatible helper is available.

### Alexa Devices

Alexa Devices exposes a runtime `sync_todo_list_items()` helper in the Home Assistant versions targeted by this integration. Todo List Sync detects the method dynamically instead of importing private Alexa implementation classes.

When available, this returns diagnostic refresh mode:

```text
alexa_full_sync
```

### Generic providers

If no safe lightweight refresh is known, the adapter returns:

```text
cache_only
```

The synchronization engine remains fully generic. A full config-entry reload is reserved for configured reconnect recovery and is never repeated automatically by the retry sequence or periodic verification.

## Periodic safety verification

Periodic verification has a hard minimum of 30 minutes. It is independent from normal event-driven synchronization and has its own persistent diagnostics.

Its purpose is recovery from a provider-side change whose event was missed.

## Write confirmation and partial failures

Cloud-backed list writes can be eventually consistent. After mutations, Todo List Sync waits for the Home Assistant entity cache to confirm the desired semantic state.

For Secondary confirmation timeouts, the provider refresh adapter receives one lightweight refresh opportunity.

A partial mutation is **not** enough to advance the shadow. The shadow remains at the previous common state until both sides converge.

## Bounded retry model

Transient synchronization exceptions use this retry schedule:

```text
initial failure
  └─ 5 s  → retry 1
      └─ 15 s → retry 2
          └─ 60 s → retry 3
              └─ ERROR / exhausted
```

Retries are bounded and never loop indefinitely.

A real item event, reconnect, enable action or manual synchronization supersedes a sleeping retry. Automatic retries request a fresh Secondary snapshot when a lightweight helper exists but never repeat a heavy generic config-entry reload.

## Missing-list Repairs

`unavailable` and `unknown` states represent temporary provider conditions and keep the manager in `waiting_primary` / `waiting_secondary` without a Repair.

After Home Assistant is running, a configured entity that is genuinely absent (`hass.states.get(entity_id) is None`) creates a Home Assistant Repairs issue. The issue is automatically cleared when the entity returns.

## Storage

Each config entry uses a private Home Assistant `Store` key:

```text
todo_list_sync.<config_entry_id>
```

The store uses `atomic_writes=True`.

Stored data includes the shadow, enabled/initialized flags, successful synchronization timestamp, periodic-verification diagnostics, privacy-safe error metadata and aggregate retry diagnostics.

Deleting the config entry removes this private storage key and stale missing-list Repairs.

## Diagnostics privacy

Exported/status diagnostics deliberately omit list summaries and raw shadow contents.

v0.1.6 no longer persists raw exception messages. Only structured fields are retained:

- error category;
- operation;
- side;
- exception type.

Legacy v0.1.5 raw `last_error` values are replaced with `legacy_error_redacted` on load rather than being exposed again.
