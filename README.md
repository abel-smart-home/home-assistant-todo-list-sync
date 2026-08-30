# Todo List Sync

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/todo_list_sync/brand/dark_logo%402x.png">
    <img src="custom_components/todo_list_sync/brand/logo%402x.png" alt="Todo List Sync logo" width="520">
  </picture>
</p>

<p align="center">
  <strong>Persistent, offline-tolerant synchronization for Home Assistant to-do lists.</strong>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=abel-smart-home&repository=home-assistant-todo-list-sync&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open this repository in HACS">
  </a>
</p>

Todo List Sync keeps two Home Assistant `todo` entities synchronized using a **persistent three-way reconciliation model**.

The integration is **provider-agnostic by design** and can synchronize any two compatible Home Assistant `todo.*` entities that support create, update and delete operations. Its **primary design target and most thoroughly tested setup** is Home Assistant OS with a local Home Assistant to-do list as Primary and a shopping/to-do list exposed by Home Assistant's official **Alexa Devices** integration as Secondary.

Typical design target:

```text
Home Assistant Local To-do
        PRIMARY
           ↕
    Todo List Sync
           ↕
Alexa Devices Shopping List
       SECONDARY
```

The primary list remains the default winner only for **true conflicts**. Independent changes made on both sides are merged instead of blindly overwriting one list with the other.

---

## Why this exists

Home Assistant can expose Alexa shopping and to-do lists as `todo` entities through the official **Alexa Devices** integration.

Alexa is cloud-backed, while a Local To-do list can continue working locally when Internet access is unavailable.

Todo List Sync combines both behaviors while keeping synchronization logic inside Home Assistant:

- Home Assistant can remain the authoritative list.
- Alexa remains available as a convenient voice interface.
- Changes can flow in both directions.
- Temporary disconnections do not require one side to blindly overwrite the other.
- Todo List Sync does not authenticate directly with Amazon.

---

## Support matrix

| Capability | Support |
|---|---|
| Home Assistant Local To-do | ✅ Primary design target |
| Alexa Devices shopping/to-do lists | ✅ Primary design target |
| Other Home Assistant `todo.*` entities | ✅ Supported when create/update/delete are available; provider-specific behavior can vary |
| Add items in either direction | ✅ |
| Remove items in either direction | ✅ |
| Synchronize active/completed state | ✅ |
| Persistent offline reconciliation | ✅ |
| Primary-wins conflict policy | ✅ Default |
| Secondary-wins conflict policy | ✅ Optional |
| Event-driven normal synchronization | ✅ |
| Periodic safety verification | ✅ |
| Automatic bounded retry after transient failures | ✅ |
| Recovery after provider reconnect | ✅ |
| Home Assistant Repairs notification for a genuinely missing configured list | ✅ |
| Direct Amazon private API access | **No** |
| Amazon credentials stored by Todo List Sync | **No** |
| YAML configuration | No |
| Item ordering | No |
| Due dates / descriptions / provider metadata | No |

---

## Requirements

### Home Assistant

- Home Assistant Core **2026.8.3 or newer**.
- Two loaded Home Assistant `todo` entities.
- Both lists must support:
  - creating items;
  - updating items;
  - deleting items.

### HACS

HACS is required only when using the recommended HACS installation method.

### Recommended Alexa setup

For the principal and most thoroughly tested Home Assistant OS + Alexa use case:

1. Configure **Local To-do** in Home Assistant.
2. Create the local list that should act as the primary list.
3. Configure Home Assistant's official **Alexa Devices** integration.
4. Confirm that the desired Alexa shopping/to-do list appears as a `todo.*` entity.
5. Confirm that Alexa Devices itself is working before configuring Todo List Sync.
6. Create a Todo List Sync pair with:
   - **Primary** = Local To-do;
   - **Secondary** = Alexa Devices list.

Todo List Sync never asks for your Amazon email, password, cookies, TOTP secret or session token.

---

## Installation

### HACS — recommended

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=abel-smart-home&repository=home-assistant-todo-list-sync&category=integration)

1. Click the badge above, or open **HACS → Integrations**.
2. Open the three-dot menu.
3. Select **Custom repositories**.
4. Add:

   ```text
   https://github.com/abel-smart-home/home-assistant-todo-list-sync
   ```

5. Select **Integration** as the repository category.
6. Install **Todo List Sync**.
7. Restart Home Assistant.
8. Go to **Settings → Devices & services → Add integration**.
9. Search for **Todo List Sync**.
10. Select the primary and secondary lists.

### Manual installation

Copy:

```text
custom_components/todo_list_sync/
```

to:

```text
/config/custom_components/todo_list_sync/
```

Restart Home Assistant and add **Todo List Sync** from:

**Settings → Devices & services → Add integration**

---

## Configuration

The setup wizard asks for two lists.

### Primary list

The primary list is normally the local, authoritative Home Assistant list.

It wins only when both sides changed the same logical item incompatibly and the conflict cannot be merged automatically.

### Secondary list

The secondary list is the synchronized companion, for example the Alexa shopping list exposed by Alexa Devices.

Example:

```text
Primary:   todo.lista_de_la_compra
Secondary: todo.alexa_shopping_list
```

Todo List Sync prevents:

- selecting the same entity as both primary and secondary;
- using one `todo` entity in more than one Todo List Sync pair inside the same Home Assistant instance.

---

## Options

Open:

**Settings → Devices & services → Todo List Sync → Configure**

| Option | Default | Purpose |
|---|---|---|
| Winner for true conflicts | Primary | Resolves incompatible changes to the same logical item |
| Safety verification interval | 30 minutes | Recovers from missed provider events |
| Refresh secondary after reconnect | Enabled | Requests a fresh provider snapshot when supported |

The safety verification interval has a hard minimum of **30 minutes** to avoid unnecessary provider/cloud traffic.

Normal synchronization does **not** wait for this interval.

---

## How synchronization works

Todo List Sync stores the **last common synchronized state**, called the **shadow**, in Home Assistant `.storage`.

Every reconciliation compares:

```text
Last common shadow
        +
Current primary list
        +
Current secondary list
        ↓
Three-way reconciliation
        ↓
Desired common state
```

The shadow advances only after both sides have been confirmed to match the desired result.

This is important for offline recovery: a failed or partial provider operation does not silently become the new synchronization truth.

---

## First synchronization

The first synchronization is deliberately conservative.

If Primary contains:

```text
Milk
Eggs
```

and Secondary contains:

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

No active item is deleted during the first merge.

Pre-existing completed history is ignored so that years of historical completed items are not imported into a new synchronization pair.

---

## Offline reconciliation

Suppose the last common shadow was:

```text
Milk
Bread
Eggs
Coffee
```

While connectivity is interrupted:

Primary changes:

```text
+ Tortillas
- Coffee
```

Secondary changes:

```text
+ Cheese
- Eggs
```

After reconnecting, Todo List Sync compares both current lists against the old shadow.

Final result:

```text
Milk
Bread
Tortillas
Cheese
```

Independent changes are merged.

The configured conflict winner is used only when both sides changed the **same logical item** incompatibly.

---

## Failure recovery

### Temporary provider or service failure

Provider writes are confirmed before the common shadow is advanced.

If a synchronization pass fails because of a transient provider/service condition, Todo List Sync performs bounded automatic retries after **5 seconds, 15 seconds and 60 seconds**.

Retries are never infinite. A real list event, reconnect or manual synchronization supersedes a pending retry so stale work is not allowed to fight newer state.

If all automatic attempts fail:

- synchronization enters `error`;
- the persisted common shadow remains unchanged;
- a later provider event, reconnect, manual synchronization or periodic verification can still recover the pair.

### Provider reconnect

When a configured secondary provider becomes available again, Todo List Sync can request a fresh provider-side snapshot before reconciliation.

### Configured list is genuinely missing

Temporary `unavailable` states are handled as connectivity/provider conditions.

If a configured `todo` entity has actually disappeared or was removed after Home Assistant is running, Todo List Sync creates a Home Assistant **Repairs** issue with actionable information.

The repair issue is cleared automatically when the list is restored.

---

## Alexa Devices refresh behavior

Todo List Sync does not implement an Amazon client.

For compatible Alexa Devices versions, it uses feature detection against the already loaded Home Assistant Alexa Devices runtime to request a fresh to-do-list snapshot.

```text
Amazon / Alexa
      ↓
Home Assistant Alexa Devices
      ↓
todo.alexa_...
      ↓
Todo List Sync
      ↓
Local To-do
```

Todo List Sync intentionally avoids importing private Alexa implementation classes directly.

If Home Assistant changes the optional refresh helper in a future release, the integration falls back safely and reports the refresh mode in diagnostics.

---

## Event-driven synchronization

Normal changes are driven by Home Assistant to-do item updates.

Provider/coordinator refreshes can sometimes notify subscribers even when the actual list has not changed. Todo List Sync compares a stable semantic signature and ignores these no-op notifications.

Meaningful changes include:

- item added;
- item removed;
- active/completed status changed.

Changes in ordering or provider-only metadata do not trigger synchronization.

---

## Periodic safety verification

A separate safety verification runs at the configured interval.

Default and minimum:

```text
30 minutes
```

Its purpose is to catch a provider-side change that may have been missed by normal event delivery.

For a compatible Alexa Devices secondary list, the periodic verification requests a fresh list snapshot before reconciliation without reloading the entire Alexa Devices integration.

Periodic verification is tracked independently so a normal item event cannot accidentally cancel a queued safety verification.

---

## Automatic retry diagnostics

The status entity exposes retry metadata without exposing shopping-list contents, for example:

```text
retry_attempt: 0
retry_count_total: 3
last_retry: 2026-08-30T22:10:00+00:00
last_retry_result: recovered
```

A successful normal synchronization clears the current retry attempt counter.

---

## Matching

Todo List Sync compares item names after normalizing:

- upper/lower case;
- accents;
- repeated whitespace.

Therefore:

```text
Limón
limon
 LIMON
```

represent the same logical shopping-list item.

The original display text is not forcibly converted to lowercase.

---

## Completion behavior

Completed items that existed before the synchronization pair was created are ignored during the initial merge.

Once an active item is tracked in the shadow:

- completing it on either side is synchronized;
- deleting that tracked completed item can also be reconciled.

---

## Multi-instance/shared-list warning

One Home Assistant instance prevents the same `todo` entity from being assigned to multiple Todo List Sync pairs.

If **different Home Assistant installations** share the same cloud-backed list, use only one synchronization owner for that shared list whenever possible.

Multiple independent synchronizers writing to the same cloud list can form a feedback topology that no single Home Assistant instance can fully observe.

---

## Entities created

Each synchronization pair creates one Home Assistant device containing:

| Entity | Purpose |
|---|---|
| **Status** sensor | Synchronization state and privacy-safe diagnostics |
| **Synchronize now** button | Request an immediate full verification |
| **Synchronization** switch | Pause/resume synchronization without deleting the shadow |

---

## Status values

- `initializing`
- `syncing`
- `synchronized`
- `waiting_primary`
- `waiting_secondary`
- `disabled`
- `error`

---

## Diagnostics

Typical diagnostic metadata includes:

```text
status: synchronized
primary_available: true
secondary_available: true
verification_interval_minutes: 30
pending_primary_to_secondary: 0
pending_secondary_to_primary: 0
conflicts_last_sync: 0
last_refresh_mode: alexa_full_sync
last_periodic_verification_result: synchronized
last_periodic_refresh_mode: alexa_full_sync
periodic_verification_count: 4
retry_attempt: 0
retry_count_total: 3
last_retry_result: recovered
```

Diagnostics deliberately exclude:

- shopping-list item names;
- shadow contents;
- Amazon credentials;
- cookies;
- provider tokens.

Raw provider exception text is not exposed directly when it could contain list content.

---

## Privacy and security

Todo List Sync:

- has no external server;
- has no direct Amazon authentication flow;
- stores no Amazon password;
- stores no Amazon cookie;
- stores no TOTP secret;
- stores no Amazon session token;
- does not include list contents in exported diagnostics.

The selected cloud provider can naturally continue using its own cloud service through its own Home Assistant integration.

---

## Troubleshooting

### `waiting_secondary`

The secondary provider is currently unavailable.

1. Check the selected secondary entity.
2. If it belongs to Alexa Devices, verify Alexa Devices itself.
3. Restore provider connectivity.
4. Todo List Sync will reconcile after the provider returns.

### `waiting_primary`

The primary list is not currently available.

Check that the selected local/provider integration is loaded.

### `error`

1. Open the Todo List Sync **Status** entity.
2. Review the privacy-safe error category and retry diagnostics.
3. Confirm that both configured lists exist.
4. Press **Synchronize now**.
5. If the secondary integration itself is failing, repair that integration first.

### A configured list was deleted

Home Assistant Repairs will identify the affected synchronization pair.

Restore/recreate the configured list or remove/reconfigure the Todo List Sync entry.

### Changes seem delayed

Normal list changes should be event-driven.

The 30-minute interval is a **safety verification**, not the expected synchronization delay.

### Repeated `syncing → synchronized` activity with no list changes

Todo List Sync ignores unchanged provider refresh notifications using semantic list signatures.

If repeated activity continues, export diagnostics and include relevant provider logs in a bug report.

---

## Updating Home Assistant

The Alexa full-refresh optimization uses runtime feature detection because the Alexa Devices helper is not a stable public API.

Before major Home Assistant upgrades:

1. keep a Home Assistant backup;
2. update Todo List Sync first when a compatibility release exists;
3. verify the integration status after the HA upgrade.

If the optional optimized refresh helper changes, normal event-driven synchronization can continue while diagnostics report the fallback refresh mode.

---

## Development and quality checks

Changes are validated with:

- HACS validation;
- Home Assistant hassfest;
- `pytest`;
- `ruff check`;
- `ruff format --check`.

The automated tests cover synchronization logic and runtime/recovery behavior including:

- safe initial merge;
- three-way offline reconciliation;
- conflict policy;
- Home Assistant restart;
- delayed provider startup;
- provider disappearance and recovery;
- semantic event deduplication;
- periodic verification;
- provider-refresh fallback;
- partial/failed mutations;
- automatic retry/backoff;
- shadow preservation on failed convergence;
- privacy-safe diagnostics.

---

## Development documentation

- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Recovery test plan: [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md)
- Issues: [`GitHub Issues`](https://github.com/abel-smart-home/home-assistant-todo-list-sync/issues)

---

## License

MIT License. See [`LICENSE`](LICENSE).
