# Changelog

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
