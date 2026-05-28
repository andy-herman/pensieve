"""Sample-file TaskSource. Reads from data/samples.json. Phase 0 fallback + tests."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from pensieve.sources.base import RawTask, TaskSource


class SampleFileSource(TaskSource):
    name = "sample_file"

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Sample file not found: {self.path}")
        with self.path.open("r", encoding="utf-8") as f:
            self._payload = json.load(f)

    @property
    def strand_catalog(self) -> list[dict]:
        return list(self._payload.get("strand_catalog", []))

    @property
    def recent_context(self) -> dict:
        return dict(self._payload.get("recent_context", {}))

    def list_tasks(self) -> Iterator[RawTask]:
        for raw in self._payload.get("tasks", []):
            yield self._to_raw(raw)

    def get_task(self, task_id: str) -> Optional[RawTask]:
        for raw in self._payload.get("tasks", []):
            if raw.get("id") == task_id:
                return self._to_raw(raw)
        return None

    def _to_raw(self, raw: dict) -> RawTask:
        created = raw.get("created_at")
        created_dt = None
        if created:
            try:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                created_dt = None
        return RawTask(
            id=raw.get("id", ""),
            title=raw.get("title", ""),
            notes=raw.get("notes", "") or "",
            list_name=raw.get("list_name", ""),
            created_at=created_dt,
            last_modification_time=created_dt,
            completed=bool(raw.get("completed", False)),
            categories=list(raw.get("categories", [])),
            source=self.name,
        )
