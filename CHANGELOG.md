# Changelog

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
