from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class OutputFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    SUMMARY = "summary"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------- Request models ----------

class TaskCommand(BaseModel):
    """Incoming user command (text)."""
    command: str = Field(..., min_length=1, max_length=2000)
    output_format: OutputFormat = OutputFormat.JSON


class VoiceUpload(BaseModel):
    """Metadata for a voice upload; actual audio bytes sent as multipart."""
    sample_rate: int = 16000
    encoding: str = "pcm"
    output_format: OutputFormat = OutputFormat.JSON


# ---------- Internal / response models ----------

class TaskStep(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    action: str
    target: str = ""
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)

    def mark_running(self) -> None:
        self.status = StepStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self, result: Any = None) -> None:
        self.status = StepStatus.COMPLETED
        self.result = result
        self.finished_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = StepStatus.FAILED
        self.error = error
        self.finished_at = datetime.now(timezone.utc)


class TaskPlan(BaseModel):
    """The decomposed plan produced by the planner."""
    task_id: str
    original_command: str
    steps: list[TaskStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TaskResult(BaseModel):
    """Final aggregated result returned to the client."""
    task_id: str
    status: TaskStatus
    command: str
    plan: TaskPlan | None = None
    output: Any = None
    output_format: OutputFormat = OutputFormat.JSON
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    duration_ms: int | None = None


# ---------- WebSocket event ----------

class WSEvent(BaseModel):
    """Lightweight event pushed over WebSocket."""
    task_id: str
    event: str  # plan_ready | step_started | step_completed | step_failed | task_done
    data: dict[str, Any] = Field(default_factory=dict)
