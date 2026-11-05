# The_Reader Skill

## Overview
`The_Reader` is the primary engine for local fact verification within the Document Intelligence Orchestra. It transforms a raw document chunk and a checklist question into a verified, traceable chain of evidence and claims.

## Core Principles
- **Immutable Fact Chains**: Instead of mutating values,, `The_Reader` builds an immutable chain. Every "correction" or "revision" produces a new object, allowing the full auditing history (Initial Claim $\rightarrow$ Quote Repair $\rightarrow$ Supprt Judgement $\rightarrow$ Revision) to be preserved.
- **Deterministic Verification**: Minimizes reliance on LLM "judgement" by routing model otputs through strict checks (e.g., verbatim quote checks, regex-based type validation, and pure Python arithmetic).
- **Separation of concerns**: Responsible for a single pass over a single chunk; it does not merge results across different chunks or tuns.

## The pipeline (Process Entry)
Every checklist entry passes through a 3-step loop:

1. **Quote verification & Repair**:
  - Validates if the model's provided quote exists *verbatim* in the chunk.
  - if not, it triggers a `QUOTE_REPAIR_PROMPT` to find a better quote while keeping the original answer.
  - if repair fails, the result is marked `NEEDS_REVIEW`.

2. **Support Judgement & Correction**:
  - Checks if the (repaired) quote actually supports the specific question/answer (e.g., ensuring a "due date" isn't swapped for an "issued dated").
  - If the evidence is insugicient, it generates a `SupportJudgement` and a `corrected_claim`.
  - Any correction that violates the fact's type (e.g., turning a numeric fact into free text) is rejected as a model glitch.

3. **Revision Extraction & Arithmetic**:
  - For numeric facts, it looks for statements in the chunk that revice the previously accepted claim.
  - **Relevance Check**: It confirms the revision quote refers to the same *same* subject as the original.
  - **Verification**: It ensures the "Original Value" stated in the revision matches the current claim.
  - **Computation**: Once validated, it uses `compute_corrected_value` (pure Python math) to appy the delta (Increase, Decrease, Multiplication, Division) to produce a final `ComputedValue`.

## Data Management & Persistence
- **Typed Vocabulary**: Uses strict dataclasses (`Evidence`, `FactClaim`, `SupportJudgement`, `RevisionEvent`) to ensure data integrity across the pipeline.
- **Persistence Store (`store.py`)**: Persistents the complete `ReaderResults` chain into a canonical SQLite database (`fact_history.db`).
- **Schema Architecture**:
  - `facts`: Core records of questions and their final statuses.
  - `claims`: A timeline of every claim ever made about a fact.
  - `evidence`: The verbatim quotes backing those claims.
  - `support_judgements`: Records of the reasoning used to verify claims.
  - `revisions`: Specific arithmetic adjustments to numeric facts.
  - `reader_results`: Stores the full JSON snapshot of the `ReaderResult` object for historical adit.
- **Fact History**: Provides the foundation for `The_Auditor` by creating a durable, cross-run record of every claim and reivision ever encountered.

## Technical Components
- **`reader_service.py`**: The runtime adapter that coordinates fetching context, running the pipeline, and persisting results.
- **`fact_types.py`**: handles fact classification (Boolean, Numeric, Date, Percent, Currency, Text) and regex-based cleaning.
- **`parsing.py`**: Normalizes text and handles the initial "ITEM/ANSWER/QUOTE" extraction from model responses.
- **`prompts.py`**: Houses the exact, narrow instructions for each step of the verification logic.
