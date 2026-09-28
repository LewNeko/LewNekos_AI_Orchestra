"""Retrieval facade: returns context, never designates canonical facts."""
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from runtime.events import RuntimeEvents, RuntimeEventType
from runtime.state import RuntimeState


class FactHistoryRepository(Protocol):
    def query(self, task_id: str, query: str | None = None) -> list[dict[str, Any]] | Awaitable[list[dict[str, Any]]]: ...


class KnowledgeService:
    def __init__(self, state: RuntimeState, fact_history_repository: FactHistoryRepository | None = None,
                 hierarchical_retriever: Callable[..., Any] | None = None, events: RuntimeEvents | None = None) -> None:
        self.state, self.fact_history_repository = state, fact_history_repository
        self.hierarchical_retriever = hierarchical_retriever
        self.events = events or RuntimeEvents()
        self.events.subscribe(state.record_event)

    async def query_fact_history(self, task_id: str, query: str | None = None) -> list[dict[str, Any]]:
        """Query the canonical repository; local state is only a reference cache."""
        if self.fact_history_repository is None:
            return []
        found = self.fact_history_repository.query(task_id, query)
        history = await found if inspect.isawaitable(found) else found
        self.state.add_fact_history(task_id, {"count": len(history), "query": query})
        return history

    async def get_context(self, task_id: str, fact_history: list[dict[str, Any]], *, query: str = "") -> dict[str, Any]:
        sources: list[Any] = []
        if self.hierarchical_retriever is not None:
            retrieved = self.hierarchical_retriever(task_id=task_id, query=query)
            sources = await retrieved if inspect.isawaitable(retrieved) else retrieved
        context = {"task_id": task_id, "task_state": self.state.tasks.get(task_id, {}), "fact_history": fact_history,
                   "reader_result_refs": list(self.state.reader_results.values()), "audit_references": list(self.state.audit_references.values()),
                   "source_documents": sources, "canonical_state": "references only"}
        self.state.add_retrieved_context(task_id, context)
        self.events.emit(RuntimeEventType.CONTEXT_PACK_CREATED, task_id, {"history_count": len(fact_history), "source_count": len(sources)})
        return context

    async def retrieve_knowledge(self, task_id: str, query: str) -> dict[str, Any]:
        history = await self.query_fact_history(task_id, query)
        return await self.get_context(task_id, history, query=query)
