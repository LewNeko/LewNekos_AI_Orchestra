"""Runtime adapter for the typed Reader pipeline and its durable store."""
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from runtime.events import RuntimeEvents, RuntimeEventType
from runtime.state import RuntimeState

from .models import ReaderResult
from .store import ReaderResultStore

ReaderRunner = Callable[[str, dict[str, Any]], ReaderResult | Awaitable[ReaderResult]]

 
class ReaderService:
    """Exposes Reader without treating a retrieval response as a verified fact."""

    def __init__(
        self, state: RuntimeState, knowledge_service: Any, reader_runner: ReaderRunner | None = None,
        result_store: ReaderResultStore | None = None, events: RuntimeEvents | None = None,
    ) -> None:
        self.state, self.knowledge_service = state, knowledge_service
        self.reader_runner, self.result_store = reader_runner, result_store
        self.events = events or RuntimeEvents()
        self.events.subscribe(state.record_event)

    async def read_and_process(self, task_id: str, query: str) -> ReaderResult:
        """Retrieve context, run the domain pipeline, then persist its typed result."""
        if self.reader_runner is None:
            raise RuntimeError("Reader runner is not configured; no result can be fabricated.")
        history = await self.knowledge_service.query_fact_history(task_id)
        context = await self.knowledge_service.get_context(task_id, history, query=query)
        proposed = self.reader_runner(query, context)
        result = await proposed if inspect.isawaitable(proposed) else proposed
        if not isinstance(result, ReaderResult):
            raise TypeError("Reader runner must return a typed ReaderResult.")
        self.events.emit(RuntimeEventType.CLAIM_PROPOSED, task_id, {"question": result.question})
        self._emit_validation_events(task_id, result)
        return self.persist_result(task_id, result)

    def persist_result(self, task_id: str, result: ReaderResult, *, run_id: str | None = None,
                       document_id: str | None = None, chunk_id: str | None = None) -> ReaderResult:
        """Persist the full result in Reader storage and retain only a Runtime reference."""
        fact_id: str | None = None
        if self.result_store is not None:
            run_id = run_id or self.result_store.start_run(document_id=document_id, metadata={"task_id": task_id})
            fact_id = self.result_store.save_result(result, run_id=run_id, document_id=document_id, chunk_id=chunk_id)
        identifier = fact_id or f"reader:{task_id}:{result.question}"
        self.state.add_reader_result(identifier, {"task_id": task_id, "fact_id": fact_id, "status": result.status, "question": result.question})
        self.state.add_evidence_chain(identifier, {"fact_id": fact_id, "question": result.question})
        self.events.emit(RuntimeEventType.READER_RESULT_PERSISTED, task_id, {"result_ref": identifier, "fact_id": fact_id})
        return result

    def _emit_validation_events(self, task_id: str, result: ReaderResult) -> None:
        self.events.emit(RuntimeEventType.QUOTE_VERIFIED, task_id, {"question": result.question})
        if result.evidence_repair is not None:
            self.events.emit(RuntimeEventType.QUOTE_REPAIRED, task_id, {"question": result.question})
        if result.support_judgment is not None:
            self.events.emit(RuntimeEventType.SUPPORT_JUDGMENT_CREATED, task_id, {"verdict": result.support_judgment.verdict})
        if result.revision is not None:
            self.events.emit(RuntimeEventType.REVISION_DETECTED, task_id, {"operation": result.revision.operation})
            self.events.emit(RuntimeEventType.REVISION_VALIDATED, task_id, {"value": result.current_value})
