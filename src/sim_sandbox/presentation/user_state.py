"""Small, failure-tolerant repository-local UI preference store."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class UserState:
    def __init__(self, path: Path | str = Path(".sim_sandbox/user_state.json")) -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                self.data = value
        except (OSError, ValueError, TypeError):
            self.data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def add_recent(self, kind: str, project_id: str, limit: int = 8) -> None:
        raw = self.data.get("recent_projects", [])
        recent = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        recent = [item for item in recent if not (item.get("kind") == kind and item.get("id") == project_id)]
        recent.insert(0, {"kind": kind, "id": project_id})
        self.data["recent_projects"] = recent[:limit]
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".user_state.", suffix=".tmp", dir=self.path.parent, text=True
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


__all__ = ["UserState"]
