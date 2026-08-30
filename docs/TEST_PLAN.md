# Manual test plan

This plan is intentionally focused on recovery and data safety.

## Before testing

Use non-critical test lists first.

Recommended pair:

- Primary: Local To-do list
- Secondary: Alexa Devices shopping list

Set conflict policy to **Primary** and verification interval to **30 minutes**.

## Test 1 — first safe merge

Primary:

```text
Milk
Eggs
```

Secondary:

```text
Bread
Coffee
```

Add Todo List Sync.

Expected result on both lists:

```text
Milk
Eggs
Bread
Coffee
```

No active item should be deleted.

## Test 2 — normal primary → secondary

With both providers connected:

1. Add `Tortillas` to the primary list.
2. Wait a few seconds.

Expected:

- `Tortillas` appears on the secondary list.
- status returns to `synchronized`.

## Test 3 — normal Alexa/secondary → primary

1. Use Alexa voice to add `Cheese`.
2. Wait for Alexa Devices to receive the event.

Expected:

- `Cheese` appears in the local primary list.

## Test 4 — removal from Alexa

1. Add `Milk` if needed.
2. Ask Alexa to remove `Milk`.

Expected:

- `Milk` disappears from the primary list after reconciliation.

## Test 5 — completion state

1. Add a new tracked item, `Soap`.
2. Let both sides synchronize.
3. Mark `Soap` completed on one side.

Expected:

- the corresponding tracked item becomes completed on the other side.

Pre-existing completed history should not be imported during initial setup.

## Test 6 — Home Assistant WAN offline, local changes

1. Confirm both lists are synchronized.
2. Disconnect Home Assistant's WAN while keeping the local network running.
3. Add `Local A` and `Local B` to the primary list.
4. Remove one previously synchronized item from the primary list.
5. Restore WAN.

Expected:

- primary local changes remain intact while offline.
- secondary provider eventually receives the additions/removal.
- shadow advances only after convergence.

## Test 7 — Home Assistant offline while Alexa changes remotely

1. Synchronize both lists.
2. Disconnect Home Assistant WAN.
3. From an Internet-connected Alexa/app, add `Remote A` and remove a synchronized item.
4. Restore Home Assistant WAN.

Expected:

- reconnect refresh obtains the remote state when supported.
- `Remote A` is merged into the primary list.
- the remote removal is propagated to primary.

## Test 8 — simultaneous independent offline changes

Start synchronized with:

```text
Milk
Bread
Eggs
Coffee
```

During Home Assistant WAN outage:

Primary changes:

```text
+ Tortillas
- Coffee
```

Remote changes:

```text
+ Cheese
- Eggs
```

Restore WAN.

Expected final state on both sides:

```text
Milk
Bread
Tortillas
Cheese
```

## Test 9 — true conflict

Start with tracked item `Milk` active.

While disconnected:

- mark `Milk` completed on Primary.
- delete `Milk` on Secondary.

With conflict policy **Primary**, restore connectivity.

Expected:

- Primary's semantic choice wins.
- `conflicts_last_sync` increases.

Repeat with Secondary conflict policy if desired.

## Test 10 — safety verification

1. Set interval to 30 minutes.
2. Confirm the status sensor reports `verification_interval_minutes: 30`.
3. Leave both lists untouched for at least one full interval.
4. Inspect the Status sensor attributes after the periodic verification.

Expected:

```text
last_periodic_verification_result: synchronized
last_periodic_refresh_mode: alexa_full_sync
periodic_verification_count: 1 or higher
last_periodic_verification: <recent timestamp>
```

For Alexa Devices 2026.8.x, `alexa_full_sync` confirms that the periodic pass requested a fresh provider-side list snapshot rather than relying only on cached state.

## Test 11 — minimum interval enforcement

Try to configure less than 30 minutes.

Expected:

- UI selector does not allow less than 30.
- runtime also clamps the value to 30 as a defensive measure.

## Test 12 — integration restart

1. Synchronize lists.
2. Restart Home Assistant.
3. Modify one side.

Expected:

- persisted shadow is reused.
- no new destructive first merge occurs.

## Test 13 — disable switch

1. Turn off **Synchronization**.
2. Change both lists independently.
3. Confirm no synchronization occurs.
4. Turn the switch on.

Expected:

- the persisted shadow is retained.
- reconciliation resumes using changes made while disabled.

## Test 14 — duplicates/normalization

Add variants on different sides:

```text
Limón
limon
```

Expected:

- they are treated as one logical item.

Version 0.1.5 intentionally does not preserve multiple quantities represented by duplicate identical names.

## Test 15 — idle provider state churn does not trigger reconciliation

1. Confirm both lists are synchronized.
2. Do not add, remove, or complete any items.
3. Observe the Status entity activity for 10–15 minutes before the periodic interval expires.

Expected:

- ordinary Alexa/provider state or attribute refreshes do not repeatedly produce `syncing → synchronized`.
- an actual to-do item change still synchronizes within a few seconds.
- the 30-minute periodic verification still runs independently and increments `periodic_verification_count`.


## Test 15 — unchanged provider refresh notifications

1. Leave both lists unchanged and available.
2. Do not add, remove or complete any items.
3. Observe the Todo List Sync Status activity before the next 30-minute safety verification.

Expected:

- ordinary provider/coordinator refreshes with identical list semantics do not trigger repeated `syncing → synchronized` passes.
- a real add/remove/complete operation still triggers event-driven synchronization promptly.
- the independent 30-minute periodic verification still runs and increments `periodic_verification_count`.
