# -*- coding: utf-8 -*-
"""Queue management for line-splitted batch tasks."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .models import QueueItem, QueueStatus


class QueueManager:
    def __init__(self) -> None:
        self._items: list[QueueItem] = []
        self._next_index = 1

    def add_from_text(self, text: str, *, dedupe: bool = False) -> list[QueueItem]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return []

        existing = {item.text for item in self._items} if dedupe else set()
        created: list[QueueItem] = []
        for line in lines:
            if dedupe and line in existing:
                continue
            item = QueueItem(
                id=uuid4().hex,
                index=self._next_index,
                text=line,
            )
            self._next_index += 1
            self._items.append(item)
            created.append(item)
            existing.add(line)
        return created

    def items(self) -> list[QueueItem]:
        return list(self._items)

    def get(self, item_id: str) -> QueueItem | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def get_next_pending(self) -> QueueItem | None:
        for item in self._items:
            if item.status == QueueStatus.PENDING:
                return item
        return None

    def has_pending(self) -> bool:
        return self.get_next_pending() is not None

    def mark(
        self,
        item_id: str,
        status: QueueStatus,
        *,
        output_path: str | Path | None = None,
        error: str | None = None,
    ) -> QueueItem | None:
        item = self.get(item_id)
        if item is None:
            return None
        item.status = status
        item.output_path = Path(output_path) if output_path else None
        item.error = error
        return item

    def remove(self, item_ids: set[str]) -> int:
        before = len(self._items)
        self._items = [item for item in self._items if item.id not in item_ids]
        return before - len(self._items)

    def clear_completed(self) -> list[str]:
        completed = {QueueStatus.SUCCESS, QueueStatus.FAILED, QueueStatus.SKIPPED}
        removed = [item.id for item in self._items if item.status in completed]
        self._items = [item for item in self._items if item.status not in completed]
        return removed

    def mark_running_as_skipped(self, *, reason: str = "用户中断") -> list[QueueItem]:
        changed: list[QueueItem] = []
        for item in self._items:
            if item.status == QueueStatus.RUNNING:
                item.status = QueueStatus.SKIPPED
                item.error = reason
                changed.append(item)
        return changed

    def counts(self) -> dict[str, int]:
        data = {
            "total": len(self._items),
            "pending": 0,
            "running": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in self._items:
            data[item.status.value] += 1
        data["done"] = data["success"] + data["failed"] + data["skipped"]
        return data

