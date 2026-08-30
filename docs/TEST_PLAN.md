# Manual test plan

This plan is intentionally focused on recovery and data safety.

## Before testing

Use non-critical test lists first.

Principal validation pair:

- Primary: Home Assistant Local To-do list
- Secondary: Alexa Devices shopping list

Other compatible Home Assistant `todo.*` providers should also work when create/update/delete are supported, but Alexa Devices + Local To-do is the primary design target.

Set conflict policy to **Primary** and verification interval to **30 minutes**.

## Test 1 — first safe merge

Primary: `Milk`, `Eggs`. Secondary: `Bread`, `Coffee`.

Expected on both: `Milk`, `Eggs`, `Bread`, `Coffee`. No active item is deleted.

## Test 2 — Primary → Secondary

Add `Tortillas` to Primary. Expected: it appears on Secondary within seconds and status returns to `synchronized`.

## Test 3 — Alexa/Secondary → Primary

Use Alexa voice to add `Cheese`. Expected: it appears on Primary.

## Test 4 — removal from Alexa

Remove a synchronized item using Alexa. Expected: it disappears from Primary after reconciliation.

## Test 5 — completion state

Add and synchronize `Soap`, then complete it on one side. Expected: the tracked item becomes completed on the other side. Pre-existing completed history is not imported at initial setup.

## Test 6 — HA WAN offline, local changes

Disconnect HA WAN while keeping LAN running. Add two local items and remove one synchronized item from Primary. Restore WAN.

Expected: local changes remain intact and eventually reach Secondary. Shadow advances only after convergence.

## Test 7 — HA offline while Alexa changes remotely

Disconnect HA WAN. Add one item and remove a synchronized item through Alexa/app. Restore WAN.

Expected: reconnect refresh obtains the remote state when supported and merges both remote changes into Primary.

## Test 8 — simultaneous independent offline changes

Start synchronized with `Milk`, `Bread`, `Eggs`, `Coffee`.

Primary while offline: `+ Tortillas`, `- Coffee`.

Secondary while offline: `+ Cheese`, `- Eggs`.

Expected final state on both: `Milk`, `Bread`, `Tortillas`, `Cheese`.

## Test 9 — true conflict

Start with tracked active `Milk`. While disconnected, complete it on Primary and delete it on Secondary.

Expected with Primary policy: completed `Milk` wins and `conflicts_last_sync` increases. Repeat with Secondary policy if desired.

## Test 10 — periodic safety verification

Leave both lists untouched for at least 30 minutes.

Expected diagnostic fields:

```text
last_periodic_verification_result: synchronized
periodic_verification_count: 1 or higher
```

For compatible Alexa Devices versions:

```text
last_periodic_refresh_mode: alexa_full_sync
```

## Test 11 — minimum interval enforcement

Try to configure less than 30 minutes. Expected: UI prevents it and runtime clamps defensively to 30.

## Test 12 — Home Assistant restart

Synchronize lists, restart HA and then change one side.

Expected: persisted shadow is reused and no destructive first merge occurs.

## Test 13 — disable switch

Disable **Synchronization**, change both lists independently, then enable it again.

Expected: no sync while disabled; shadow is retained; reconciliation resumes from the persisted common state.

## Test 14 — normalization

Use `Limón` on one side and `limon` on the other.

Expected: one logical item. v0.1.6 intentionally does not model intentionally duplicated identical names as separate quantities.

## Test 15 — idle provider refresh noise

Leave lists unchanged for 10–15 minutes before the periodic interval.

Expected: provider/coordinator refreshes with identical semantics do not repeatedly produce `syncing → synchronized`. A real add/remove/complete event remains immediate.

## Test 16 — bounded automatic retry

Cause a temporary service/provider failure during a synchronization pass, then restore the provider before the sequence is exhausted.

Expected approximate retry schedule:

```text
5 s → 15 s → 60 s
```

Expected diagnostics after recovery:

```text
retry_attempt: 0
retry_count_total: 1 or higher
last_retry_result: recovered
```

## Test 17 — retry exhaustion

Keep the failing condition present through all three automatic retries.

Expected:

```text
status: error
last_retry_result: exhausted
```

No fourth automatic retry is scheduled.

## Test 18 — real event supersedes sleeping retry

Create a transient failure so a retry is scheduled, then restore the provider and make a real list change before the delay expires.

Expected: the pending retry is cancelled/superseded and the newer event drives reconciliation.

## Test 19 — partial mutation never advances shadow

Force one side to accept an operation while the other side/confirmation fails.

Expected: status becomes `error`/retrying, but the stored common shadow remains the last fully confirmed state. After recovery, reconciliation uses that old shadow to resolve the partial write safely.

## Test 20 — fresh startup refresh

While Home Assistant is off, change the Secondary cloud list remotely. Start Home Assistant.

Expected for Alexa Devices: startup diagnostics eventually show `last_refresh_mode: alexa_full_sync` and the remote change is merged without requiring a 30-minute wait.

For a generic provider with no refresh helper, expected mode is `cache_only`; synchronization still remains generic.

## Test 21 — delayed provider startup

Restart Home Assistant with the Secondary provider loading later than Todo List Sync.

Expected: Todo List Sync does not permanently fail setup. It waits and automatically reconciles once the selected entity becomes available. No false missing-list Repair should remain after normal startup.

## Test 22 — temporary unavailable vs genuinely missing

A. Temporarily make the provider entity `unavailable`.

Expected: `waiting_primary` or `waiting_secondary`; **no missing-list Repair**.

B. Actually delete/remove a configured `todo` entity after Home Assistant is running.

Expected: a Home Assistant Repairs issue appears for that Primary/Secondary entity.

Restore the entity. Expected: the Repair clears automatically and synchronization resumes.

## Test 23 — privacy-safe diagnostics

Cause an operation failure involving a deliberately distinctive item name such as `PRIVATE-TEST-ITEM-9371`.

Export diagnostics and inspect the Status attributes.

Expected: the item name is absent. Error fields contain only structured values such as:

```text
last_error_category: service_call_failed
last_error_operation: add_item
last_error_side: secondary
last_error_type: <exception class>
```

## Test 24 — change during initial synchronization

Create the synchronization pair with active items on both sides. While the initial merge is actively writing, add another item to either list.

Expected: the first merge remains non-destructive and a follow-up reconciliation is queued automatically; the new item should not wait until the 30-minute safety verification.

## Test 25 — config entry removal cleanup

After a successful synchronization, remove the Todo List Sync integration entry.

Expected:

- both user lists remain untouched;
- `.storage/todo_list_sync.<entry_id>` is removed;
- any missing-list Repairs for that pair are removed.

## Test 26 — version consistency and repository hygiene

Before release, verify:

```text
manifest.json version == const.py VERSION == 0.1.6
```

Also verify the repository contains no tracked `__pycache__/` directories or `*.pyc` files.
