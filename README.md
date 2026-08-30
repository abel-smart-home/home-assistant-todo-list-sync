# Todo List Sync

A Home Assistant custom integration that keeps two `todo` entities synchronized using a persistent three-way merge.

It is designed for setups where one list must remain local and authoritative while another list provides a convenient external interface, such as **Home Assistant Local To-do ↔ Alexa Devices Shopping List**.

> **Version 0.1.5 is still experimental.** Test it with non-critical lists first and keep a backup of your Home Assistant configuration.

This release also adds local brand images so the integration displays a proper icon and logo in Home Assistant.

## Why this exists

Home Assistant can expose Alexa shopping lists as `todo` entities through the official **Alexa Devices** integration. That works well while the cloud connection is healthy, but the Alexa list itself is cloud-backed. A local Home Assistant list can continue working without Internet.

Todo List Sync combines both behaviors:

```text
Local Home Assistant list
        PRIMARY
           ↕
    Todo List Sync
           ↕
Secondary todo entity
   (for example Alexa)
```

The integration remembers the **last common synchronized state** (the *shadow*) in Home Assistant `.storage`. If the two sides diverge while one provider is unavailable, it can reconcile their independent changes later instead of blindly overwriting one list with the other.

## Main features

- Bidirectional synchronization between two Home Assistant `todo` entities.
- Persistent three-way reconciliation: **primary + secondary + last common shadow**.
- Primary-list priority for true conflicts by default.
- Non-destructive first synchronization.
- Active items from both lists are merged on first setup.
- Pre-existing completed history is not imported during first setup.
- Completion state of items tracked after installation is synchronized.
- Case-, accent- and whitespace-insensitive matching to reduce duplicates.
- Event-driven synchronization for normal item changes.
- Availability-state listener reacts only to actual available/unavailable transitions, avoiding redundant reconciliations from provider state churn.
- Safety verification every **30 minutes minimum**.
- Optimized full-list refresh for Home Assistant 2026.8.x **Alexa Devices** when its compatible runtime helper is available.
- Immediate provider refresh after reconnect when possible.
- Persistent enable/disable switch.
- Manual **Synchronize now** button.
- Diagnostic status sensor without exposing shopping-list contents.
- Spanish and English translations.

## Compatibility

Initial target:

- Home Assistant Core **2026.8.3 or newer**.
- Any `todo` entity that supports:
  - create item
  - update item
  - delete item

Primary development use case:

- Home Assistant **Local To-do** as primary.
- Home Assistant **Alexa Devices** shopping list as secondary.

## Installation with HACS as a custom repository

1. Create or publish this repository on GitHub.
2. In HACS, open **Integrations**.
3. Open the menu and choose **Custom repositories**.
4. Add the repository URL and select **Integration**.
5. Install **Todo List Sync**.
6. Restart Home Assistant.
7. Go to **Settings → Devices & services → Add integration**.
8. Search for **Todo List Sync**.

## Manual installation

Copy:

```text
custom_components/todo_list_sync/
```

to:

```text
/config/custom_components/todo_list_sync/
```

Restart Home Assistant and add the integration from **Settings → Devices & services**.

## Configuration

The setup wizard asks for only two entities:

- **Primary to-do list** — the authoritative list in a true conflict.
- **Secondary to-do list** — the synchronized companion, for example an Alexa shopping list.

Example:

```text
Primary:   todo.lista_de_la_compra
Secondary: todo.example_shopping_list
```

### Options

After setup, open **Configure** on the integration.

- **Winner for true conflicts**: Primary or Secondary.
- **Safety verification interval**: minimum 30 minutes, up to 24 hours in 30-minute steps.
- **Refresh secondary provider after reconnect**: enabled by default.

The 30-minute hard minimum is intentional to avoid excessive cloud/API traffic.

## First synchronization

The first synchronization is deliberately conservative.

If the primary contains:

```text
Milk
Eggs
```

and the secondary contains:

```text
Bread
Coffee
```

both lists become:

```text
Milk
Eggs
Bread
Coffee
```

No active item is deleted during this first merge.

Existing completed history is ignored at first setup. This prevents a large historical Alexa completed list from being copied into the local Home Assistant list.

## Three-way reconciliation

Suppose the last synchronized shadow was:

```text
Milk
Bread
Eggs
Coffee
```

While the systems are disconnected:

- Home Assistant adds `Tortillas` and removes `Coffee`.
- Alexa adds `Cheese` and removes `Eggs`.

The integration compares all three states:

| Item | Shadow | Primary | Secondary | Result |
|---|---:|---:|---:|---|
| Milk | yes | yes | yes | keep |
| Bread | yes | yes | yes | keep |
| Eggs | yes | yes | no | remove |
| Coffee | yes | no | yes | remove |
| Tortillas | no | yes | no | add |
| Cheese | no | no | yes | add |

Final state on both sides:

```text
Milk
Bread
Tortillas
Cheese
```

Independent changes are merged. Only a true incompatible change to the same logical item invokes the configured conflict policy.

## Offline behavior

### Both sides connected

Changes are synchronized from item-update events, normally without waiting for the 30-minute verification.

### Home Assistant local list works but the secondary provider is unavailable

The primary list remains usable. The shadow is not advanced while the secondary side cannot be confirmed. When the provider recovers, the integration reconciles the accumulated changes.

### Home Assistant was offline while the remote list changed

When Home Assistant returns, the integration refreshes the secondary provider when supported and reconciles it against the persisted shadow and the current primary list.

For Alexa Devices on Home Assistant 2026.8.x, Todo List Sync uses feature detection for the integration's full to-do-list refresh helper. It does not import Alexa's private classes directly. If Home Assistant changes that internal helper in a future release, the integration falls back gracefully and reports its refresh mode in diagnostics.

## Safety verification

Normal changes are event-driven. Provider/coordinator refreshes that re-notify an unchanged to-do list are ignored by comparing a semantic signature of item identity and active/completed state. Separately, Todo List Sync performs a safety verification at the configured interval.

Default:

```text
30 minutes
```

Minimum allowed:

```text
30 minutes
```

For a compatible Alexa Devices secondary list, the periodic verification asks Alexa Devices for a fresh list snapshot before reconciliation. It does **not** reload the entire Alexa integration every 30 minutes.

A full config-entry reload is reserved as a reconnect fallback for providers where no lighter refresh mechanism is available.

The status sensor records each periodic verification separately. A successful periodic pass updates `last_periodic_verification`, increments `periodic_verification_count`, sets `last_periodic_verification_result` to `synchronized`, and records the provider refresh method in `last_periodic_refresh_mode`. These fields are persisted across Home Assistant restarts.

## Matching and duplicates

Logical comparison normalizes:

- upper/lower case
- accents
- repeated whitespace

Therefore these are treated as one logical item:

```text
Limón
limon
 LIMON
```

The displayed text itself is not forcibly converted to lowercase.

### Duplicate limitation

Version 0.1.5 treats identical normalized names as one logical item. If a provider deliberately stores multiple active entries with the same normalized name, Todo List Sync does not preserve duplicate multiplicity.

## Completion behavior

Completed items that existed before installing the integration are ignored.

Once an active item is tracked in the shadow, marking it completed on either side is synchronized to the other side. If a provider later deletes that tracked completed item, the deletion can also be reconciled.

## What is not synchronized in 0.1.5

- item ordering
- due dates
- descriptions/notes
- provider-specific metadata
- intentional duplicate quantities with the exact same normalized name

The integration focuses on shopping-list semantics: item identity, active/completed status, additions and removals.

## Entities created

Each synchronization pair creates one Home Assistant device containing:

- **Status** sensor
- **Synchronize now** button
- **Synchronization** switch

The status sensor exposes only metadata and counters, for example:

```text
status: synchronized
primary_available: true
secondary_available: true
verification_interval_minutes: 30
pending_primary_to_secondary: 0
pending_secondary_to_primary: 0
conflicts_last_sync: 0
last_refresh_mode: alexa_full_sync
last_periodic_verification: 2026-08-30T20:00:00+00:00
last_periodic_verification_attempt: 2026-08-30T20:00:00+00:00
last_periodic_verification_result: synchronized
last_periodic_refresh_mode: alexa_full_sync
periodic_verification_count: 4
```

Shopping-list item names are intentionally excluded from diagnostics.

## Status values

- `initializing`
- `syncing`
- `synchronized`
- `waiting_primary`
- `waiting_secondary`
- `disabled`
- `error`

## Privacy

Todo List Sync does not send data to its own server and has no external Python dependency.

It only uses the two Home Assistant `todo` entities you select. If the secondary entity belongs to a cloud integration such as Alexa Devices, that provider naturally continues to use its own cloud service.

The diagnostics endpoint does not include item names or shadow contents.

## Recovery and troubleshooting

If the status is `error`:

1. Check that both selected `todo` entities are available.
2. Open the Status sensor attributes and review `last_error`.
3. Press **Synchronize now**.
4. If Alexa Devices itself is unavailable, repair that integration first.
5. Do not delete the local primary list while a sync entry still references it.

To temporarily stop synchronization without deleting its shadow, turn off the **Synchronization** switch.

## Updating Home Assistant

The Alexa full-refresh optimization intentionally uses feature detection against Home Assistant's Alexa Devices runtime data. Because that helper is not a stable public API, a future Home Assistant release can change it.

Before major Home Assistant upgrades, test Todo List Sync in a non-critical environment. If the optimization disappears, normal event synchronization can continue, but missed-event recovery may be weaker until Todo List Sync is updated.

## Development notes

Architecture details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

Offline/recovery test plan: [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md)

## License

MIT License. See [`LICENSE`](LICENSE).
