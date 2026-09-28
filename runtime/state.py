"""Transient Runtime execution state; never a canonical knowledge store."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .events import RuntimeEvent


@dataclass
class RuntimeState:
    conversations: dict[str, dict[str, Any]] = field(default_factory=dict)
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    tool_calls: dict[str, dict[str, Any]] = field(default_factory=dict)
    mcp_interactions: dict[str, dict[str, Any]] = field(default_factory=dict)
    retrieved_context: dict[str, dict[str, Any]] = field(default_factory=dict)
    reader_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    fact_histories: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence_chains: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_references: dict[str, dict[str, Any]] = field(default_factory=dict)
    planner_decisions: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[RuntimeEvent] = field(default_factory=list)

    def _add(self, collection: dict[str, dict[str, Any]], identifier: str, details: dict[str, Any]) -> None:
        collection[identifier] = dict(details)

    def add_conversation(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.conversations, identifier, details)
    def add_task(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.tasks, identifier, details)
    def add_tool_call(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.tool_calls, identifier, details)
    def add_mcp_interaction(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.mcp_interactions, identifier, details)
    def add_retrieved_context(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.retrieved_context, identifier, details)
    def add_reader_result(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.reader_results, identifier, details)
    def add_fact_history(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.fact_histories, identifier, details)
    def add_evidence_chain(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.evidence_chains, identifier, details)
    def add_audit_reference(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.audit_references, identifier, details)
    def add_planner_decision(self, identifier: str, details: dict[str, Any]) -> None: self._add(self.planner_decisions, identifier, details)

    def record_event(self, event: RuntimeEvent) -> None:
        self.events.append(event)

    def get_all_state(self) -> dict[str, Any]:
        return vars(self).copy()
