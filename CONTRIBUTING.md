# Contributing

Todo List Sync is intentionally conservative because synchronization errors can delete or resurrect user data.

## Branch policy

Do not develop directly on `main`.

1. Create a focused feature/fix branch.
2. Make the smallest coherent change.
3. Add or update tests for the affected behavior.
4. Open a pull request into `main`.
5. Merge only after validation checks pass.

## Required checks

Before merging:

```bash
python -m compileall custom_components/todo_list_sync tests
ruff check .
ruff format --check .
pytest --tb=short
```

GitHub also runs HACS and Hassfest validation.

## Synchronization safety rules

Changes must preserve these invariants:

- Never advance the persistent shadow until both sides confirm convergence.
- Initial synchronization must remain non-destructive for active items.
- Temporary provider failures must not become synchronization truth.
- Provider-specific optimizations must fail safely for generic `todo.*` entities.
- Diagnostics must not expose item summaries, raw provider payloads, credentials or tokens.
- Automatic retries must remain bounded.

## Versioning

When publishing a release, keep these values synchronized:

- `custom_components/todo_list_sync/manifest.json` → `version`
- `custom_components/todo_list_sync/const.py` → `VERSION`

CI contains a regression test that fails when the two values differ.
