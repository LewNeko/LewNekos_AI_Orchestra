"""Typed, append-only observations emitted by the Runtime layer."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class RuntimeEventType(StrEnum):
    DOCUMENT_LOADED = "document_loaded"
    CLAIM_PROPOSED = "claim_proposed"
    QUOTE_VERIFIED = "quote_verified"
    QUOTE_REPAIRED = "quote_repaired"
    SUPPORT_JUDGMENT_CREATED = "support_judgment_created"
    REVISION_DETECTED = "revision_detected"
    REVISION_VALIDATED = "revision_validated"
    READER_RESULT_PERSISTED = "reader_result_persisted"
    FACT_HISTORY_UPDATED = "fact_history_updated"
    AUDITOR_CONFLICT_DETECTED = "auditor_conflict_detected"
    CONTEXT_PACK_CREATED = "context_pack_created"
    FINAL_ANSWER_GENERATED = "final_answer_generated"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """An immutable observation with references, not copies of canonical data."""

    event_type: RuntimeEventType
    task_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: f"evt_{uuid4().hex}")
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


EventHandler = Callable[[RuntimeEvent], None]


class RuntimeEvents:
    """In-process publisher for the Runtime's observable event timeline."""

    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """Register a handler once, so shared Runtime services do not duplicate events."""
        if handler not in self._handlers:
            self._handlers.append(handler)

    def emit(self, event_type: RuntimeEventType, task_id: str, payload: dict[str, Any] | None = None) -> RuntimeEvent:
        event = RuntimeEvent(event_type, task_id, dict(payload or {}))
        for handler in tuple(self._handlers):
            handler(event)
        return event
