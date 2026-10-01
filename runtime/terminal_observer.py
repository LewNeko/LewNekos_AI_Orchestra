"""Run a visible, end-to-end Runtime event timeline in a terminal.

Usage (from the repository root):
    python -m runtime.terminal_observer
    python -m runtime.terminal_observer --database runtime-demo.db --no-color
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

from knowledge_service import KnowledgeService
from The_Auditor.auditor_service import AuditorService
from The_Reader.models import (
    ComputedValue,
    Evidence,
    FactClaim,
    FactHistory,
    ReaderResult,
    RevisionEvent,
    SupportJudgment,
)
from The_Reader.reader_service import ReaderService
from The_Reader.store import ReaderResultStore

from .events import RuntimeEvent, RuntimeEvents, RuntimeEventType
from .planner import Planner
from .state import RuntimeState


class TerminalObserver:
    """Formats RuntimeEvent notifications as one chronological terminal stream."""

    _COLORS: ClassVar[dict[str, str]] = {"document_loaded": "36", "claim_proposed": "33", "quote_verified": "32",
               "quote_repaired": "33", "support_judgment_created": "32", "revision_detected": "35",
               "revision_validated": "32", "reader_result_persisted": "34", "fact_history_updated": "34",
               "auditor_conflict_detected": "31", "context_pack_created": "36", "final_answer_generated": "1;32"}

    def __init__(self, color: bool = True) -> None:
        self.color = color

    def __call__(self, event: RuntimeEvent) -> None:
        timestamp = event.occurred_at.strftime("%H:%M:%S.%f")[:-3]
        name = event.event_type.value.upper()
        payload = json.dumps(event.payload, default=str, sort_keys=True)
        label = f"{name:<28}"
        if self.color:
            label = f"\033[{self._COLORS[event.event_type.value]}m{label}\033[0m"
        print(f"{timestamp}  {label} task={event.task_id}  {payload}")


class DemoFactHistoryRepository:
    def query(self, task_id: str, query: str | None = None) -> list[dict[str, Any]]:
        return [{"fact_id": "prior-rate", "task_id": task_id, "query": query, "value": "100"}]


def demo_reader(query: str, context: dict[str, Any]) -> ReaderResult:
    del query, context
    initial = FactClaim("100", Evidence("The rate is 100."))
    corrected = FactClaim("100", Evidence("The rate was 100."))
    revision = RevisionEvent(Evidence("The rate increased by 25."), "INCREASE", "25", ComputedValue("125"))
    return ReaderResult(
        question="What is the current rate?", fact_type="numeric", initial_claim=initial,
        evidence_repair=corrected.evidence,
        support_judgment=SupportJudgment("SUPPORTED", corrected), corrected_claim=corrected,
        revision=revision, status="VERIFIED_REVISED",
    )


def demo_canonical_decider(result: ReaderResult, history: FactHistory) -> dict[str, Any]:
    return {"id": "audit-demo-001", "value": result.current_value, "basis": history.derived_from,
            "decision": "canonical decision delegated to Auditor"}


async def run_demo(database: str, color: bool) -> None:
    task_id = "runtime-demo"
    state, events = RuntimeState(), RuntimeEvents()
    events.subscribe(state.record_event)
    events.subscribe(TerminalObserver(color))
    state.add_task(task_id, {"goal": "Determine the current rate with evidence."})

    knowledge = KnowledgeService(state, DemoFactHistoryRepository(), events=events)
    with ReaderResultStore(database) as store:
        reader = ReaderService(state, knowledge, demo_reader, store, events)
        planner = Planner(state, knowledge, reader, events)
        events.emit(RuntimeEventType.DOCUMENT_LOADED, task_id, {"document_id": "demo-policy-v1"})
        await planner.select_workflow(task_id, "Determine the current rate with evidence.")
        result = await planner.invoke_reader(task_id, "What is the current rate?")
        history = FactHistory("What is the current rate?", "numeric", claims=[FactClaim("100", Evidence("Old rate: 100."))])
        audit = await AuditorService(state, demo_canonical_decider, events).audit_reader_result(task_id, result, history)
        events.emit(RuntimeEventType.FINAL_ANSWER_GENERATED, task_id, {"answer": result.current_value, "audit_id": audit["canonical_decision"]["id"]})

    print(f"\nCompleted {len(state.events)} observable events. Canonical records remain outside RuntimeState.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Display a live Runtime event timeline.")
    parser.add_argument("--database", default=":memory:", help="Reader SQLite database path (default: in-memory).")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI terminal colors.")
    arguments = parser.parse_args()
    database = arguments.database if arguments.database == ":memory:" else str(Path(arguments.database))
    asyncio.run(run_demo(database, color=not arguments.no_color))


if __name__ == "__main__":
    main()
