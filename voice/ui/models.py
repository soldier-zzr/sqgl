# -*- coding: utf-8 -*-
"""Data models for queue items."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class QueueStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class QueueItem:
    id: str
    index: int
    text: str
    status: QueueStatus = QueueStatus.PENDING
    output_path: Path | None = None
    error: str | None = None

