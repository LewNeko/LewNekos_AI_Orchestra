"""Capability planner. It selects work; it never establishes facts."""
from __future__ import annotations

from typing import Any

from .events import RuntimeEvents, RuntimeEventType
from .state import RuntimeState


class Planner:
    def __init__(self, state: RuntimeState, knowledge_service: Any, reader_service: Any | None = None) -> None:
        self.state = state
        self.knowledge_service = knowledge_service
        self.reader_service = reader_service
        self.events = RuntimeEvents()
        self.events.subscribe(state.record_event)

    async def select_workflow(self, task_id: str, goal: str) -> dict[str, Any]:
        history = await self.knowledge_service.query_fact_history(task_id)
        context = await self.knowledge_service.get_context(task_id, history, query=goal)
        workflow = self._select_workflow_from_context(context)
        decision = {"workflow": workflow, "goal": goal, "reason": "selected from retrieval context"}
        self.state.add_planner_decision(task_id, decision)
        self.events.emit(RuntimeEventType.CLAIM_PROPOSED, task_id, {"proposal": decision})
        return {"workflow": workflow, "context": context}

    @staticmethod
    def _select_workflow_from_context(context: dict[str, Any]) -> str:
        if "conflict" in str(context.get("audit_summary", "")).lower():
            return "conflict_resolution_workflow"
        if context.get("fact_history"):
            return "fact_retrieval_workflow"
        return "general_planning_workflow"

    async def invoke_reader(self, task_id: str, query: str) -> Any:
        if self.reader_service is None:
            raise RuntimeError("Reader capability was not configured for this planner.")
        return await self.reader_service.read_and_process(task_id, query)
