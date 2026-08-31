# Changelog

## 0.1.9 — 2026-08-31

Home Assistant startup-listener lifecycle hotfix.

### Fixed

- Track the one-time `homeassistant_started` listener separately from persistent listeners.
- Clear the local listener reference as soon as Home Assistant consumes the one-time startup listener.
- Prevent options-triggered integration reloads from trying to remove an already-consumed listener.
- Preserve correct listener cleanup when Todo List Sync unloads before Home Assistant finishes starting.
- Prevent the `Unable to remove unknown job listener ... homeassistant_started` log error observed after saving integration options.

### Tests

- Added regression coverage for unloading after the startup event has already fired.
- Added regression coverage for unloading while the startup listener is still pending.

### Unchanged

- No synchronization or reconciliation behavior changes compared with v0.1.8.
- Periodic verification, Alexa Devices refresh, retries, Repairs, storage and privacy-safe diagnostics remain unchanged.

## 0.1.8 — 2026-08-30

Release metadata consistency correction.

### Fixed

- Align `manifest.json` with release version `0.1.8`.
- Align the runtime `VERSION` constant with release version `0.1.8`.
- Align the automated version-consistency test with release version `0.1.8`.
- Restore the missing `0.1.7` release-history entry in this changelog.

### Unchanged

- No synchronization behavior changes compared with v0.1.7.
- Reliability, recovery, Repairs, privacy-safe diagnostics, retry handling, Alexa Devices refresh support, semantic event deduplication and periodic verification remain unchanged.

## 0.1.7 — 2026-08-30

CI and repository-quality finalization.

### Changed

- Finalized Ruff 0.16.5 lint and formatting compliance.
- Updated `actions/checkout` to v7.0.1.
- Updated `actions/setup-python` to v7.0.0.
- Confirmed Python 3.14.2 CI compatibility for Home Assistant Core 2026.8.3.
- Finalized test formatting and repository quality checks.

### Unchanged

- No intentional synchronization behavior changes compared with v0.1.6.
- The reliability and recovery improvements introduced in v0.1.6 remain unchanged.

## 0.1.6 — 2026-08-30

Reliability, recovery, privacy and project-quality release.

### Added

- Bounded automatic retry sequence after transient synchronization failures: 5 s, 15 s and 60 s.
- Retry diagnostics: `retry_attempt`, `retry_count_total`, `last_retry` and `last_retry_result`.
- Structured privacy-safe error diagnostics: category, operation, side and exception type without raw provider/item messages.
- Fresh secondary-provider verification on startup when a lightweight provider refresh is available.
- Home Assistant Repairs issue when a configured list genuinely disappears after Home Assistant is running.
- Automatic Repair cleanup when the entity returns.
- Unit/regression coverage for retry policy, startup refresh, shadow preservation, Repairs, provider refresh fallback, storage and version consistency.
- GitHub Actions tests and Ruff lint/format checks.
- Dependabot configuration for GitHub Actions.
- Bug-report issue form and contributor/branch policy.
- `.gitignore` preventing Python bytecode and local tooling artifacts from being committed.

### Changed

- Private shadow storage now uses Home Assistant atomic writes.
- Private storage is removed when a Todo List Sync config entry is deleted.
- Startup waits for Home Assistant's normal boot lifecycle before raising missing-list Repairs.
- `unavailable`/`unknown` provider states remain temporary waiting conditions and do not create missing-list Repairs.
- A real list event, reconnect or manual request supersedes a pending automatic retry.
- Automatic retries never repeat a heavy generic config-entry reload.
- Initial synchronization detects active changes that occur during its non-destructive writes and queues a follow-up reconciliation.
- README now presents Todo List Sync as a generic `todo.*` synchronizer while explicitly documenting Home Assistant Local To-do ↔ Alexa Devices as the primary design and test target.
- CI actions are pinned to immutable commit SHAs.

### Privacy

- Legacy raw `last_error` text from v0.1.5 and earlier is redacted on load.
- New diagnostics never store raw provider exception messages that could contain shopping-list text.
- Default integration error logs contain structured categories instead of raw provider exception payloads.

### Repository cleanup

- Generated `custom_components/todo_list_sync/__pycache__/` content must be deleted from source control before publishing this release.

## 0.1.5 — 2026-08-30

Semantic deduplication for to-do update notifications.

### Fixed

- Ignore Home Assistant to-do subscriber notifications when the list semantics have not changed.
- Prevent Alexa/coordinator refreshes from producing unnecessary `syncing → synchronized` activity when item identity and active/completed state are unchanged.
- Preserve immediate event-driven synchronization for real additions, removals and completion-state changes.

### Added

- Stable semantic list signatures based on normalized item identity plus active/completed status.
- Unit coverage confirming the signature ignores ordering/display-only differences and detects membership/status changes.
- Manual idle-refresh regression test in `docs/TEST_PLAN.md`.

### Unchanged

- The independent 30-minute safety verification and its diagnostics remain unchanged.
- Three-way reconciliation, offline recovery and Alexa full-list refresh behavior remain unchanged.

## 0.1.4 — 2026-08-30

Synchronization-noise reduction and periodic-verification diagnostics.

### Changed

- Provider state changes now trigger reconciliation only when a selected to-do entity actually transitions between available and unavailable.
- Normal provider state/attribute refreshes no longer cause redundant `syncing → synchronized` passes.
- To-do item updates remain event-driven through the dedicated item-update subscription.
- Periodic verification is tracked independently while queued, so concurrent item events cannot erase a pending 30-minute safety verification.

### Added

- Persistent periodic-verification diagnostics:
  - `last_periodic_verification`
  - `last_periodic_verification_attempt`
  - `last_periodic_verification_result`
  - `last_periodic_refresh_mode`
  - `periodic_verification_count`
- A successful Alexa periodic verification can now be confirmed directly with `last_periodic_verification_result: synchronized` and `last_periodic_refresh_mode: alexa_full_sync`.

## 0.1.3 — 2026-08-30

Home Assistant event-loop thread-safety hotfix.

### Fixed

- Marked the dispatcher entity-update listener with Home Assistant's `@callback` decorator.
- Diagnostic entity state writes now execute on Home Assistant's event loop instead of an executor thread.
- Fixes repeated `async_write_ha_state from a thread other than the event loop` warnings and runtime errors.
- No list reconciliation, offline recovery, Alexa refresh, or 30-minute verification logic was changed.

## 0.1.2 — 2026-08-30

Version display consistency fix.

### Fixed

- Corrected the internal `VERSION` constant from `0.1.0` to `0.1.2`.
- The Home Assistant device information now reports firmware/software version `0.1.2`, matching HACS and `manifest.json`.
- No synchronization behavior or logic was changed.

## 0.1.1 — 2026-08-30

Experimental maintenance and branding update.

### Added

- Local Home Assistant brand assets under `custom_components/todo_list_sync/brand/`.
- `icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png`.
- `dark_icon.png`, `dark_icon@2x.png`, `dark_logo.png`, `dark_logo@2x.png` for dark mode support.

### Changed

- Updated GitHub Actions checkout step from `actions/checkout@v4` to `actions/checkout@v7` to avoid Node.js 20 deprecation warnings.
- Bumped integration version to `0.1.1`.

## 0.1.0 — 2026-08-30

Initial experimental release.

### Added

- Bidirectional synchronization between two Home Assistant `todo` entities.
- Persistent three-way shadow reconciliation.
- Non-destructive initial union of active items.
- Primary/secondary conflict policy.
- Completion tracking for items active after installation.
- Case/accent/whitespace normalization.
- Direct to-do item subscriptions with debounced synchronization.
- 30-minute minimum periodic safety verification.
- Alexa Devices 2026.8.x optimized full list refresh by runtime feature detection.
- Reconnect refresh support with conservative config-entry reload fallback.
- Status sensor, manual sync button and enable/disable switch.
- Privacy-preserving diagnostics.
- Spanish and English translations.
- HACS and Hassfest validation workflow.
- Architecture and offline recovery test documentation.
