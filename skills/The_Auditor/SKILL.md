# The_Auditor Skill

>**Status: adapter is in place, deep temporal reasoning is still under development.** The code that ships today (`The_Auditor/auditor_service.py`) is an async adapter that (a) computes a shallow conflict list, (b) emits a `AUDITOR_CONFLICT_DETECTED` event when one exists, (c) delegates the actual canonical decision to a caller-supplied `CanonicalDecider` callable, and (d) records a lightweight audit reference in `RuntimeState`. The rich cross-chunk supersession model (same / supersedes / contradicts / unrelated / needs_review) is still on the readmap and is not yet encoded as data structures in this package.

## Overview
`The_Auditor` is the reconciliation and validation layer for the Document Intelligence Orchestra. Its intended role is to aggregate evidence across chunks and processing runs into a durable **canonical FactHistory**, resolving state over time: *"Does the claim established in Chunk 42 supersede the one in Chunk 17?"*

## What exists today (source of truth)
- **File**: `The_Auditor/auditor_service.py` &rightarrow; class `AuditorService`.
- **Constructor**: takes `RuntimeState`, a required `canonical_decider` callable, and otional `RuntimeEvents`.
- **Public API**: `audit_reader_result(task_id, result: ReaderResult, histoory: FactHistory)` &rightarrow; `dict`
  - Computes `conflicts = [claim.value for claim in history.claims if claim.value != result.current_value]'.
  - Emits `AUDITOR_CONFLICT_DETECTED` when `conflicts` is non-empty.
  - Emits `FACT_HISTORY_UPDATED` after the decider returns.
  - Returns `{"status": "conflict" | "audited", "timeline": {...}, "canonical_decision": <decider output>}`.
  ** Demo wiring**: see `runtime/terminal_observer.py::demo_canonical_decider` for a working example of the decider contract.

  ## What is still on the roadmap
  - Rich temporal relationship vocabulary (same / supersedes / contradicts / unrelated / needs_review) &ndash; currently there is no `TemporalRelation` type in the codebase.
  - Cross-run `FactHistory` aggregation. `The_Reader/pipeline.py::build_fact_history` is explicity a placeholder for this; it only turns ONE `ReaderResult` into a `FactHistory` instance.
  - Persistence of audit decisions (currently the decider's dict is returned and recorded in `RuntimeState.audit_references`, but there is no SQLite `audit_records` table yet).
  - Document-level resolution (the "Cannical Fact History" the plan describes).

  ## Integration
  - **Inputs**: `ReaderResult` (from `The_Reader`) and a `FactHistory`.
  - **Outputs**: an audit dict plus an event on the runtime timeline.
  - **Role in Orchestra**: the boundary between "what the model concludes on one pass" and "what the system commits to as canonical across passes." Until the decider and the cross-run builder are real, treat every `canonical_decision` as *delegated*, not *resolved*.