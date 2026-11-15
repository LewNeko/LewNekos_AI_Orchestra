# The_Reader Skill

## Overview
`The_Reader` is the primary engine for local fact verification within the Document Intelligence Orchestra. It transforms a raw document chunk and a checklist question into a verified, traceable chain of evidence and claims.

## Current Status
Implemented. `The_Reader` is the most substantially complete agent in the repository. It is invokved through `The_Reader/reader_service.py` (async adapter) and the per-entry pipeline in `The_Reader/reader_pipeline.py::process_entry`.

## Core Principles
- **Immutable Fact Chains**: Instead of mutating values,, `The_Reader` builds an immutable chain. Every "correction" or "revision" produces a new frozen dataclass instance (`FactClaim`,`Evidence`,`SupportJudgement`,`RevisionEvent`,`ComputedValue`), allowing the full auditing history (Initial Claim $\rightarrow$ Quote Repair $\rightarrow$ Supprt Judgement $\rightarrow$ Revision) to be preserved.
- **Deterministic Verification**: Minimizes reliance on LLM "judgement" by routing model outputs through strict checks (e.g., verbatim quote checks, regex-based type validation, and pure Python arithmetic) for numeric revisions. The model supplies claims and quotes; Python does the math and the substring checks.
- **Single-pass, single-chunk scope**: Responsible for one checklit entry over one chunk. It does not merge results across different chunks or turns; that is `The_Auditor / FactHistory` job.

## The pipeline (The_Reader/pipeline.py::Process Entry)
Every checklist entry passes through a 3-step loop:

1. **Quote verification & Repair**:
  - Validates if the model's provided quote exists *verbatim* in the chunk.
  - if not, it triggers a `QUOTE_REPAIR_PROMPT` to find a better quote while keeping the original answer.
  - if repair fails, the result is marked `NEEDS_REVIEW` with a reason.

2. **Support Judgement & Correction(quote_checks.py &rightarrow; pipeline.py::_judge_support)**:
  - Checks if the (repaired) quote actually supports the specific question and this specific value (e.g., an "issued date" does not support a "due date" claim).
  - If the evidence is insufficient, it produces a `SupportJudgement` and (possibly) `corrected_claim`.
  - Any correction that violates the fact's type (e.g., turning a numeric fact into free text) is rejected as a model glitch.

3. **Revision Extraction & Arithmetic (revisions.py)**:
  - Only for numeric facts, running the arithmetic mechanism on a boolean/text fact would invite the model to invent numbers.
  - **Relevance Check**: It confirms the revision quote refers to the same *same* subject as the original.
  - **Verification**: It ensures the "Original Value" stated in the revision matches the current claim.
  - **Computation**: Once validated, it uses `compute_corrected_value` (pure Python math) to appy the delta (Increase, Decrease, Multiplication, Division) to produce a final `ComputedValue`.

## Result status vocabulary (`The_Reader/models.py::Status`)
`VERIFIED_NO_CHANGE` | `VERIFIED_REPAIRED_QUOTE` | `VERIFIED_CORRECTED` | `VERIFIED_REVISED` | `NEEDS_REVIEW`

`current_value` property precedence: revised > corrected > initial.

## Data Management & Persistence
- **Typed Vocabulary** (`models.py`): frozen dataclasses `Evidence`, `FactClaim`, `SupportJudgement`, `ComputedValue`, `RevisionEvent`; non-frozen `ReaderResult` (a pass) and `FactHistory` (a timeline).
- **Persistence store** (`store.py`, class `ReaderResultStore`): Persists the complete  `ReaderResult` chain into a canonical SQLite database (default `fact_history.db`). Design rule: SQLite is the source of truth; a vector DB, if any, is derived *from* these rows, not the other way around.
- **Schema** (`store.py::SCHEMA`):
  - `processing_runs`: One execution of the Reader against a document / chunk set; provenance root.
  - `facts`: Core records of questions and their final statuses for one run.
  - `claims`: A timeline of every claim (INITIAL / CORRECTED roles) about a fact.
  - `evidence`: The verbatim quotes backing those claims (INITIAL / EVIDENCE_REPAIR roles).
  - `support_judgements`: Records of the reasoning used to verify claims.
  - `revisions`: Specific arithmetic adjustments to numeric facts.
  - `reader_results`: JSON snapshot of the full `ReaderResult` per fact, as an escape hatch for schema evolution.
- **Fact History cross-run aggregation**: **Not yet built.** `build_fact_history()` in `pipeline.py` deliberately turns ONE `ReaderResult` into a `FactHistory` and is documented as a placeholder for the cross-run merge that `The_Auditor` needs.

## Technical Components
- **`reader_service.py`**: Async runtime adapter - retrieves context via `knowledge_service`, runs the pipeline, emits runtime events, persists via `ReaderResultStore`, and records a lightweight reference in `RuntimeState` (never the canonical record).
- **`pipeline.py`**: The per-entry loop; the only module that builds `RevisionEvent`/`ComputedValue` from raw model text (mirroring `quote_checks._judge_support` as the sole builder of `SupportJudgement`/corrected `FactClaim`).
- **`fact_types.py`**: Classifies values into `boolean` | `numeric` | `date` | `percent` | `currency` | `text`. Provides `is_valid_value` (type plausibility) and `format_amount` (rendering). No model calls.
- **`parsing.py`**: Normalizes text and handles the initial "ITEM/ANSWER/QUOTE" extraction from model responses.
- **`quote_checks.py`**: Verbatim quote verification, `QUOTE_REPAIR_PROMPT`,`check_answer_support` (model boundary), `_judge_support` (dict &rightarrow; domain).
- **`revisions.py`**: `check_for_revision`, `_validate_revision` (IRRELEVANT / INVALID / VALID / NONE), `compute_corrected_value`.
- **`store.py`**: SQLite persistance, transactions, WAL, foreign keys on.
- **`prompts.py`**: The narrow instructions for each step of the verification logic.
- **`ProofOfConcept.py`**: End-to-end demo driver. 