"""Auditor adapter: analyzes Reader output and delegates canonical decisions."""
from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from runtime.events import RuntimeEvents, RuntimeEventType
from runtime.state import RuntimeState
from The_Reader.models import FactHistory, ReaderResult

CanonicalDecider = Callable[[ReaderResult, FactHistory], dict[str, Any] | Awaitable[dict[str, Any]]]


class AuditorService:
    def __init__(self, state: RuntimeState, canonical_decider: CanonicalDecider, events: RuntimeEvents | None = None) -> None:
        self.state, self.canonical_decider = state, canonical_decider
        self.events = events or RuntimeEvents()
        self.events.subscribe(state.record_event)

    async def audit_reader_result(self, task_id: str, result: ReaderResult, history: FactHistory) -> dict[str, Any]:
        """Perform conflict/timeline analysis; only the supplied Auditor decider can canonize."""
        conflicts = [claim.value for claim in history.claims if claim.value != result.current_value]
        timeline = {"prior_claims": len(history.claims), "prior_revisions": len(history.revisions), "candidate": result.current_value}
        if conflicts:
            self.events.emit(RuntimeEventType.AUDITOR_CONFLICT_DETECTED, task_id, {"conflicting_values": conflicts})
        decision = self.canonical_decider(result, history)
        canonical = await decision if inspect.isawaitable(decision) else decision
        audit = {"status": "conflict" if conflicts else "audited", "timeline": timeline, "canonical_decision": canonical}
        self.state.add_audit_reference(task_id, {"status": audit["status"], "canonical_ref": canonical.get("id")})
        self.events.emit(RuntimeEventType.FACT_HISTORY_UPDATED, task_id, {"audit_ref": task_id})
        return audit
