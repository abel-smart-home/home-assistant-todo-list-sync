"""Release metadata consistency checks."""

import json
from pathlib import Path

from custom_components.todo_list_sync.const import VERSION


def test_manifest_and_runtime_versions_match() -> None:
    manifest = json.loads(
        Path("custom_components/todo_list_sync/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["version"] == VERSION == "0.1.10"
