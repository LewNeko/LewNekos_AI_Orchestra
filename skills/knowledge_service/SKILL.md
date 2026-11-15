# Knowledge Service Skill

## Overview 
`knowledge_service` (top-level `knowledge_service.py`, class `knowledgeService`) is the retrieval facade for the entire system. Its core philosophy &ndash; stated in the module docstring and enforced in the code &ndash; is to **provide context and access to information without ever designating "canonical facts" inside the service itself**. Canonicalization is the Auditor's job; this module only assembles context.

## Source of truth
- **File**: `knowledge_service.py` &rightarrow; class `KnowledgeService` and protocol `FactHistoryRepository`.
- **Consumers**: `The_Reader.reader_service.py`, `runtime/planner.py`, `runtime/terminal_observer.py`.

## Public API (verified against code)
| Method | Signature (abridged) | What it does |
| --- | --- | ---|
| `query_fact_history(task_id, query=None)` | `async` &rightarrow; `list[dict[str, Any]]` | Queries the injected `FactHistoryRepository` (sync or async). Records a lightweight reference in `RuntimeState.fact_histories`. Returns `[]`if no repository is confidured. |
| `get_context(task_id, fact_history, *, query="")` | `async` &rightarrow; dict[str, Any]` | Assumbles a context pack: task_state`, `fact_history`, `reader_result_refs`, `audit_references`, optional `source_documents` (via optional `hierarchical_retriever`), and a fixed `canonical_state: "references only"` marker. Emits `CONTEXT_PACK_CREATED`. |
| `retrieve_knowledge(task_id, query)` | `async` &rightarrow; `dict[str, Any]` | Convenience: `query_fact_history` then `get_context`. |

## Design invariants
- `state.add_*` calls are **reference caches**, not copies of canonical data. The canonical record lives in the SQLite store (`The_Reader/store.py`) or the injected repository.
- If the `canonical_decider` or the repository is not configured, the service returns empty structures rather than fabricating data &ndash; the pattern is echoed in `ReaderService.read_and_process`, which refuses to run without a `reader_runner`.
- All methods are awaitable-friendly: sync callables are called inline; `awaitable` results are awaited (see `inspect.isawaitable` checks).

## What it does NOT do
- No canonical fact resolution (that's `The_Auditor`'s job).
- No LLM calls.
- No vector DB management. A vector layer, if built, sits behind `hierarchical_retriever` or the repository and is *derived from* the canonical store.