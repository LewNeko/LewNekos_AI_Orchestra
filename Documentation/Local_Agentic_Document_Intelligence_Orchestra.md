# Local Agentic Document Intelligence Orchestra

## Project Vision

Build a model-independent, locally runnable agentic system that can reason over large collections of documents without requiring the entire document corpus to be placed into the model's context window.

The system combines four complementary ideas:

1. **Model-independent agent orchestration** from `LewNekos_AI_Orchestra`
2. **Document retrieval, evidence, and audit tooling** from the Sixfeetup `OrchestrateAgenticAI` project
3. **Dynamic context discovery and relevance selection**, inspired by Aider's repository-map architecture
4. **Dynamic capability composition**, inspired by Cordis (DeepSeek Harness's runtime) — held in reserve as an architectural pattern, not an early build target

The system runs primarily with a local model such as Qwen through Ollama, while retaining the ability to switch to other model backends.

The goal is not to reproduce any one of these systems. The goal is to combine their strongest architectural ideas into a more general, auditable system — and to be explicit, from the start, about where that system's judgment can be trusted and where it can't.

---

## 1. The Problem

Large-document AI systems have a fundamental context-management problem.

A naive system places large amounts of source material directly into the model's context:

```
Large document collection
        ↓
       LLM
        ↓
      Answer
```

This becomes increasingly inefficient as the corpus grows.

Retrieval-augmented generation improves this:

```
Documents
    ↓
Search / Retrieval
    ↓
Relevant chunks
    ↓
   LLM
    ↓
  Answer
```

However, a fixed retrieval pipeline still has a limitation: **the model is largely constrained by what the retrieval system decided to retrieve before the model began reasoning.** If the initial evidence is incomplete, the model may not know that additional relevant information exists elsewhere.

A second, quieter problem sits underneath the first one: even when the model retrieves the right evidence, nothing forces a distinction between *what the evidence literally says* and *what the model concluded from it*. A system that conflates "the text exists" with "the interpretation is correct" will look reliable right up until it isn't.

The proposed system therefore adds two layers on top of retrieval: a **context-navigation layer**, and a **validation layer** that keeps deterministic fact from semantic judgment at every step.

---

## 2. Core Architectural Idea

The system operates as an iterative loop:

```
        ┌──────────────────┐
        │   Local Model     │
        │   Qwen/Ollama     │
        └────────┬──────────┘
                  │
          Reason about
          current evidence
                  │
                  ▼
        "I need more context"
                  │
                  ▼
        ┌──────────────────┐
        │  Context Engine   │
        └────────┬──────────┘
                  │
     ┌────────────┼────────────┐
     ▼             ▼            ▼
  Search       Structure     Retrieve
     │             │            │
     └────────────┼────────────┘
                  ▼
             New evidence
                  │
                  ▼
             Local Model
                  │
                ...repeat...
                  │
                  ▼
            Final judgment
```

This creates a spiral rather than a simple retrieval circle. The model's understanding of the problem determines what information it requests next.

A second spiral — introduced in Section 9a — governs *what the model is allowed to assert* at each turn of this loop.

---

## 3. The Four Foundational Projects

### A. LewNekos_AI_Orchestra — Orchestration Layer

Repository: `LewNeko/LewNekos_AI_Orchestra`

Provides the generic orchestration architecture. Key abstractions:

**`backends.py`** — defines how the orchestrator communicates with a model. The model must be replaceable without rewriting the orchestration system.

```
      Orchestrator
           │
           ▼
      ModelBackend
           │
     ┌─────┴─────┐
     ▼           ▼
  Ollama       Claude
```

**`tools.py`** — defines capabilities available to the model (`list_directory()`, `read_file()`, etc.). The orchestrator does not need to know the internal implementation of every tool.

**`orchestrator.py`** — the fundamental agent loop:

```
send request
     ↓
model decides whether a tool is needed
     ↓
execute tool
     ↓
return tool result
     ↓
model reasons again
     ↓
repeat until final answer
```

This is the foundation for the new system.

### B. Sixfeetup — Document Intelligence Layer

Repository: `github.com/sixfeetup/2026_AllThingsAI_OrchestrateAgenticAI`

Provides specialized document infrastructure: parsing, clause extraction, SQLite storage, Chroma vector storage, semantic search, evidence retrieval, audit logging, evaluation criteria, MCP tooling, and structured document-processing scripts.

Its architecture externalizes most of the actual reasoning to Claude Code:

```
document-eval.py
     ↓
retrieve evidence
     ↓
structured evidence output
     ↓
Claude Code
     ↓
reasoning / judgment
```

We reuse its document capabilities without making the overall system dependent on Claude Code.

### C. Aider — Context Engineering Layer

Repository: `github.com/Aider-AI/aider`

Aider's repository map provides a structural representation of a large codebase and uses relevance/ranking mechanisms to determine which information should enter a limited token budget.

The transferable idea:

```
Large information space
        ↓
Structural representation
        ↓
   Relevance analysis
        ↓
Small amount of high-value context
        ↓
        Model
```

Instead of "put the entire document collection into Qwen," the system enables Qwen to ask: *"What information exists, and which part should I inspect next?"*

### D. Cordis — Runtime Composability Layer (architectural influence, not an early build target)

Cordis (used in DeepSeek Harness) treats models, tools, skills, sessions, and storage as mountable/unmountable plugins with **reversible effects** and **reactive coeffects**: components declare what they provide and require, and the runtime activates or deactivates them as dependencies come and go.

This is genuinely relevant to a system that will eventually run many specialized agents (`Reader+OCR`, `Reader+Legal`, `Reader+Tables`), but Cordis's own API is explicitly unstable, and adopting it wholesale before the base system works would bury the project under infrastructure. We borrow the *pattern* — provides/requires/effects/lifecycle — not the implementation. See Section 15 for how this is staged.

---

## 4. Combined Architecture

```
┌───────────────────────────────────────────────────────┐
│                     LOCAL MODEL                        │
│                    Qwen / Ollama                        │
└──────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                        │
│   Agent loop · Tool selection · Model interaction        │
│   Termination                                            │
└──────────────────────────┬────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌────────────────────────┐   ┌────────────────────────┐
│    CONTEXT ENGINE       │   │      DOMAIN TOOLS        │
│  Structural map          │   │  Document search          │
│  Relevance ranking       │   │  Evidence retrieval       │
│  Context expansion       │   │  Audit                    │
│  Token budgeting         │   │  Document loading         │
└────────────┬───────────┘   └────────────┬───────────┘
             │                             │
             └─────────────┬───────────────┘
                            ▼
┌───────────────────────────────────────────────────────┐
│                     DOMAIN MODEL                        │
│  Documents · Chunks · Claims · Evidence · Findings        │
│  Sources · Verification status                          │
└───────────────────────────────────────────────────────┘
```

---

## 5. The Domain Model

The system uses a proper domain model rather than passing arbitrary strings and dictionaries between agents. This is not cosmetic — Section 6a shows a concrete case (`The_Reader`) where the *original* choice to mutate a generic dict was the actual source of a correctness bug.

```
Document                    Chunk
├── source                  ├── document
├── metadata                ├── location
└── chunks                  ├── text
                             └── metadata

Claim                        Evidence
├── statement                ├── supports claim
├── source                   ├── contradicts claim
└── status                   ├── source
                              └── relevance

Finding                      AuditRecord
├── claim                    ├── action
├── evidence                 ├── actor
├── severity                 ├── timestamp
└── verification status      └── evidence
```

This layer represents what the system knows. The orchestrator represents what the system does. The model represents how the system reasons. Those concerns stay separate.

---

## 6. Agents

### The_Chunker

Transforms raw documents into useful, identifiable chunks.

```
Document → The_Chunker → Chunks
```

### The_Reader — Local Fact Verification

**Current status: implemented as the first substantially complete agent.**

The Reader currently takes a single source chunk plus a checklist of questions, obtains an initial model-produced claim/evidence pair, and runs that result through a deterministic/semantic verification pipeline.

Its job is deliberately bounded:

> **Given one chunk and one requested fact, establish what this chunk supports about that fact, preserve the entire verification chain, and identify any numeric revision found later in the same chunk.**

The Reader does **not** yet resolve the same fact across multiple chunks or processing runs. That remains The_Auditor / FactHistory aggregation problem.

The current pipeline is:

```text
model checklist output
        ↓
parse entries
        ↓
deterministic quote verification
        ↓
quote repair if necessary
        ↓
semantic support judgment
        ↓
optional corrected claim
        ↓
numeric revision detection
        ↓
deterministic revision validation
        ↓
Python arithmetic
        ↓
ReaderResult
        ↓
optional SQLite persistence
```

The important architectural result is that `process_entry()` now returns a typed `ReaderResult` rather than a final mutable answer dictionary. The model-facing parsing boundary still uses simple dictionaries, but once the result enters the domain pipeline it is represented by typed objects such as `FactClaim`, `Evidence`, `SupportJudgment`, `RevisionEvent`, and `ComputedValue`.

### The_Auditor — Cross-Chunk Temporal Reasoning

Resolves state across chunks: *"Does the claim established in Chunk 42 supersede the one established in Chunk 17?"*

```
The_Chunker
    │  produces bounded, identifiable chunks
    ▼
The_Reader
    │  "What does THIS chunk establish about each fact?"
    │  produces claims + evidence + revisions + provenance
    ▼
The_Auditor
    │  "Across chunks, which facts supersede which?"
    │  resolves document-level state
    ▼
Canonical Fact History
```

This means a large document never needs to be dumped into The_Reader at once:

```
Document
├── Chunk 1   → Reader → facts
├── Chunk 2   → Reader → facts
├── ...
├── Chunk 500 → Reader → facts
│
└── Auditor
      ├── Fact A history
      ├── Fact B history
      └── Fact C history
```

The audit trail itself becomes a compressed representation of what matters — closer to the intended architecture than plain RAG over a huge document.

### The_Verifier

Actively attempts to disprove or weaken a finding rather than accepting the first evidence retrieved.

```
Read finding
     ↓
Search for counter-evidence
     ↓
Inspect related material
     ↓
Check audit trail
     ↓
Construct defense
     ↓
Render verdict
```

### The_Drafter

Turns verified findings into a final report or response.

---

## 6a. The_Reader in Detail — Current Implementation

The_Reader is no longer merely a planned architecture. It is the first concrete domain agent in the repository and currently contains the project's most developed validation pipeline.

### What is implemented

The current `The_Reader/` package contains:

```text
The_Reader/
├── models.py
├── verify_pipeline.py
├── reader_result_store.py
├── ProofOfConcept.py
├── Step1Example.py
├── Initial_Test_scripts.py
└── __init__.py
```

The implementation is intentionally more compact than the earlier proposed module split. The verification logic currently lives primarily in `verify_pipeline.py`; it has **not** been broken into the previously proposed `parsing.py`, `validation.py`, `reasoning.py`, and `computation.py` modules.

### The original problem

The original Reader implementation represented a fact as a mutable dictionary:

```python
current = dict(entry)
```

and repeatedly changed `answer`, `quote`, and related fields as the pipeline ran.

That made it possible to lose the distinction between:

- what the model originally claimed,
- what evidence originally supported that claim,
- what the model later corrected,
- and what Python computed from a revision.

### The current fix

The pipeline now has a typed domain vocabulary:

```text
Evidence
    └── exact quote verified against the source

FactClaim
    ├── value
    └── Evidence

SupportJudgment
    ├── verdict
    └── checked_claim

RevisionEvent
    ├── Evidence
    ├── operation
    ├── amount
    └── ComputedValue

ComputedValue
    └── value produced by Python

ReaderResult
    ├── initial_claim
    ├── evidence_repair
    ├── support_judgment
    ├── corrected_claim
    ├── revision
    └── terminal status
```

These objects preserve the chain instead of overwriting it.

For example:

```text
initial claim
    "$4,250"
        │
        ├── evidence: "The total amount due is $4,250.00."
        │
        ▼
support judgment
    SUPPORTED
        │
        ▼
revision event
    DECREASE by $1,000
        │
        ▼
computed value
    "$3,250.00"
```

The model does not directly assert `$3,250`. It proposes the revision operation and raw amount; Python computes the resulting value.

### Current `process_entry()` pipeline

The actual implementation now follows these stages:

1. **Create the initial typed claim**
   - `FactClaim(value=..., evidence=Evidence(...))`

2. **Handle missing fields**
   - Missing item/answer/quote becomes `NEEDS_REVIEW`.

3. **Verify the initial quote**
   - Exact/normalized source matching is performed before the claim is trusted.
   - If the quote is not verified, the Reader gets one narrow quote-repair attempt.
   - Quote repair is deliberately not allowed to change the answer.

4. **Judge semantic support**
   - An exact quote can still be wrong for the question.
   - `_judge_support()` converts the model's raw support response into a typed `SupportJudgment` and, when necessary, a new `FactClaim`.
   - This is the key boundary between deterministic grounding and semantic interpretation.

5. **Stop for non-numeric facts**
   - Boolean and text facts currently finish after quote/support verification.
   - Numeric facts continue to revision checking.

6. **Look for a later numeric revision**
   - The model proposes whether another statement changes the same numeric fact.
   - The candidate revision quote must exist in the source.
   - The revision's original value must match the current claim.
   - Revision relevance is checked before arithmetic is performed.

7. **Compute the revised value in Python**
   - Supported operations currently include:
     `INCREASE`, `DECREASE`, `DIVIDED`, and `MULTIPLIED`.
   - The model does not perform the arithmetic used for the accepted final value.

8. **Return one terminal `ReaderResult`**
   - The current statuses are:
     `VERIFIED_NO_CHANGE`,
     `VERIFIED_REPAIRED_QUOTE`,
     `VERIFIED_CORRECTED`,
     `VERIFIED_REVISED`,
     `NEEDS_REVIEW`.

The result is therefore a complete record of **what happened during one Reader pass**, not merely the final value.

### `FactHistory` is defined, but cross-run aggregation is not finished

`models.py` also defines `FactHistory`:

```text
FactHistory
├── question
├── fact_type
├── claims[]
└── revisions[]
```

The current `build_fact_history()` function can turn **one** `ReaderResult` into a `FactHistory`. It is deliberately thin: it does not yet merge results from multiple chunks or multiple Reader runs for the same question.

That distinction matters:

```text
ReaderResult
    = one pass over one chunk

FactHistory
    = durable timeline across many passes/chunks
```

The second half is still future work and is where The_Auditor will eventually operate.

### SQLite persistence is now present

`reader_result_store.py` establishes SQLite as the canonical structured store for Reader results.

The current schema records:

```text
processing_runs
facts
claims
evidence
support_judgments
revisions
reader_results
```

A `ReaderResult` can be persisted with run/document/chunk provenance. The design explicitly keeps SQLite as the source of truth and treats a future vector database as a derived index rather than the canonical fact store.

The persistence layer does not reinterpret claims, call an LLM, calculate revisions, or decide support. It stores the result produced by the Reader.

### Current implementation boundary

The Reader is therefore **substantially implemented, but not the complete document-intelligence system**.

Implemented:

- typed Reader domain objects
- quote verification
- quote repair
- semantic answer-support checking
- corrected claims
- numeric revision detection
- revision relevance validation
- deterministic arithmetic
- terminal statuses
- `ReaderResult`
- initial `FactHistory` construction
- SQLite persistence
- proof-of-concept execution against the existing model backend

Not yet implemented:

- merging `ReaderResult` objects into a true cross-chunk `FactHistory`
- The_Auditor
- The_Chunker
- the Context Engine
- document-wide adaptive retrieval
- the full orchestrator-driven Reader workflow
- a meaningful labeled evaluation set for measuring semantic support/revision accuracy

### Governing principle: model proposes, Python validates

The Reader now embodies the intended boundary:

```text
                 LLM
                  │
                  ▼
          Proposed interpretation
                  │
                  ▼
        Deterministic validation
                  │
          ┌───────┴────────┐
          │                │
        VALID            INVALID
          │                │
          ▼                ▼
   Accept into         NEEDS_REVIEW
   typed result
```

The deterministic layer can establish things such as:

- whether a quote exists in the source,
- whether a revision quote exists,
- whether the revision's original value matches the claim,
- whether the arithmetic operation is supported,
- and what Python computes from the operation.

It cannot, by itself, prove that a valid quote semantically answers the question. That remains a model judgment and therefore needs evaluation against ground truth.

### Why the Reader is the template for later agents

The Reader establishes the architectural contract that later agents should follow:

> **An agent may use a model to propose structured meaning, but it must not silently turn that proposal into canonical state.**

Later agents such as The_Auditor and The_Verifier should preserve the same separation between:

```text
model proposal
      ↓
typed representation
      ↓
deterministic validation where possible
      ↓
semantic judgment where necessary
      ↓
auditable state transition
```

## 7. Context Engine

Not merely vector search. It answers: *"Given what the model currently knows and what it is trying to accomplish, what information should enter the context next?"*

```
inspect_structure()
search()
retrieve()
expand_context()
find_references()
find_related_claims()
```

```
Semantic relevance
        +
Structural relevance
        +
Explicit references
        +
Current task
        +
Conversation/agent state
        +
Token budget
        ↓
   Optimal context
```

### Context retrieval is more than a vector database

The Context Engine should not be designed around the assumption that a vector database is the architecture. A vector index is a retrieval primitive: it answers which indexed items are semantically close to a query. The Context Engine decides **what to retrieve, how much surrounding structure to expose, what related state matters, and what should actually enter the model's context**.

A useful distinction is:

```text
Flat vector RAG
    query
      ↓
    embedding
      ↓
    nearest chunks
      ↓
    context
```

versus:

```text
Context Engine
    query + task + current state
                ↓
        retrieval strategy
                ↓
      semantic + structural search
                ↓
        rank / expand / filter
                ↓
      related claims / references
                ↓
          token budgeting
                ↓
             context pack
```

A good vector database with metadata filtering, parent/child relationships, reranking, and neighboring-chunk expansion can implement much of this behavior. Therefore, the goal is **not** to replace vector search with something magically superior. The goal is to put vector search inside a larger, explicit retrieval architecture.

### OpenViking as an architectural reference

OpenViking is useful as a reference implementation for this distinction. Its central idea is not that vectors are obsolete; it uses vector retrieval as part of a hierarchical context system. It treats resources, memories, and skills as structured context under a filesystem-like hierarchy and supports retrieval that can move from broad structure toward more specific content.

The most relevant ideas for this project are:

- **Hierarchy-aware retrieval:** search can first locate relevant high-level structure and then descend into more relevant subtrees rather than treating every chunk as an unrelated point.
- **Progressive disclosure:** represent information at multiple levels of detail so retrieval can cheaply decide what matters before loading full content.
- **L0 / L1 / L2 context layers:** a compact representation for retrieval, a richer overview for selection/reranking, and the full source detail loaded only when needed.
- **Retrieval trajectories:** preserve enough information about how retrieval proceeded that retrieval behavior can be inspected rather than becoming a black box.
- **Unified context model:** resources, memories, and skills can participate in the same context-management abstraction.

The project should borrow these **architectural ideas**, not blindly adopt OpenViking as a replacement for SQLite or a vector database.

### How this maps onto this project

The critical distinction is between **canonical fact state** and **derived retrieval context**:

```text
                  SQLite
                    │
                    │ canonical
                    ▼
             ReaderResult
                    │
                    ▼
              FactHistory
                    │
                    ▼
               The_Auditor
                    │
                    ├──────────────┐
                    │              │
                    ▼              ▼
             structured state   source/index data
                                   │
                         vector / hierarchical
                              retrieval
                                   │
                                   ▼
                            Context Engine
                                   │
                                   ▼
                              Context Pack
```

SQLite remains the source of truth for claims, evidence, support judgments, revisions, provenance, and Reader results. A vector or hierarchical retrieval system is a **derived index**, not the authority on what the document says.

This matters because the system has two different questions:

1. **What does the system currently believe the document establishes?** → `FactHistory` / Auditor / canonical store.
2. **What source material should be brought into context to answer or investigate the next question?** → Context Engine / retrieval index.

The Context Engine should eventually be able to use both at once:

```text
User question / agent task
          │
          ├───────────────┐
          ▼               ▼
   FactHistory        source retrieval
   current state      vector + hierarchy
          │               │
          └───────┬───────┘
                  ▼
             context pack
                  │
                  ▼
              local model
```

### L0 / L1 / L2 should be considered for this architecture

The progressive-disclosure idea maps naturally onto the project's fact model, but the layers should not be confused with the canonical records themselves. For example:

```text
L0 — compact retrieval representation
    "Invoice amount currently $3,250."

L1 — useful overview
    "Invoice was originally $4,250; a later statement
     decreased it by $1,000; current value is $3,250."

L2 — full provenance
    claims + exact evidence + revision event +
    computation + chunk/source provenance + audit trail
```

L0/L1 are retrieval aids. L2 remains grounded in the structured canonical state and source material. This lets the Context Engine avoid stuffing full evidence chains into every model request while retaining the ability to expand when the task requires verification.

### Design principle

The Context Engine should therefore be treated as **retrieval policy and context construction**, not as another database that becomes the system of record. Its first implementation can be simple:

```text
query → search → rank → select
```

Then progressively add hierarchy, related claims, explicit references, context expansion, progressive disclosure, retrieval tracing, token budgeting, and agent/task state as the document pipeline demonstrates that those capabilities are actually needed.

---

## 8. Single-Shot vs Tool-Calling

**Single-shot** — for simple evaluation tasks. Simple, fast, easy to debug, one model request, works with models that don't support tools.

```
document-eval.py → evidence → local model → finding
```

**Tool-calling** — for investigation and verification. Adaptive, capable of finding missing evidence, capable of challenging its own conclusions, better suited to large document collections. This is the preferred architecture for advanced verification.

---

## 9. The Information Spiral

```
Question → Initial context → Reason → Identify information gap
    → Retrieve additional context → Reason again
    → Identify new relationship / contradiction → Retrieve again
    → Reason → Verify → Final answer
```

Each reasoning cycle can improve the next context selection. The system becomes increasingly capable of navigating large information spaces without requiring the entire space to fit inside the model's context.

## 9a. The Validation Spiral — Current Reader Boundary

The Reader has made the validation spiral concrete.

The information spiral asks:

> **What information should the system retrieve next?**

The validation spiral asks:

> **Can the proposed fact transition be accepted into structured state?**

The current Reader implements this distinction as:

```text
Model proposes claim
        ↓
Does the evidence quote exist?
        │
        ├── NO → attempt narrow quote repair
        │          └── still invalid → NEEDS_REVIEW
        │
        ▼
Does the evidence actually support this question + value?
        │
        ├── NO → semantic correction / NEEDS_REVIEW
        │
        ▼
Is this a numeric fact?
        │
        ├── NO → terminal ReaderResult
        │
        ▼
Does another statement revise this same numeric fact?
        │
        ├── NO → terminal ReaderResult
        │
        ▼
Does the revision pass deterministic validation?
        │
        ├── NO / IRRELEVANT → terminal status
        │
        ▼
Python computes the new value
        │
        ▼
VERIFIED_REVISED ReaderResult
```

This is more precise than treating all Reader behavior as "validation." There are two different guarantees.

### Deterministic guarantees

The current code can directly verify:

- source grounding of quoted evidence,
- source grounding of revision evidence,
- consistency between the revision's original numeric value and the current claim,
- supported arithmetic operations,
- the resulting arithmetic value.

### Semantic judgments

The model is still responsible for judgments such as:

- whether an exact quote actually answers the requested question,
- whether a candidate revision refers to the same fact,
- whether two statements concern the same subject.

Those judgments are represented explicitly in the Reader result rather than being disguised as deterministic facts.

### Evaluation is now the next validation milestone

The earlier plan treated the labeled evaluation set as something that needed to exist before the Reader could be built. That is no longer the right ordering.

The Reader pipeline exists now. The next step is to **measure it before building downstream agents that depend on it**.

A small hand-labeled evaluation set should therefore be treated as the next major Reader milestone:

```text
known chunk
    ↓
expected ReaderResult
    ↓
run actual Reader
    ↓
compare semantic decisions
    ↓
measure:
  - support judgment accuracy
  - correction accuracy
  - revision relevance accuracy
  - revision validation behavior
  - NEEDS_REVIEW rate
```

The goal is not to prove that the Reader is "correct" in every circumstance. The goal is to establish where its semantic layer is reliable enough to serve as an input to The_Auditor.

## 10. Local-Model Strategy

```
Ollama → Qwen → ModelBackend → Orchestrator
```

The backend abstraction stays model-independent. Potential future backends: Ollama/Qwen, Ollama/other local models, Claude, OpenAI, other APIs. The orchestrator should not care which model is being used — this allows experimentation with local models while retaining the ability to use stronger cloud models for comparison or specialized tasks. Given that most of the system's semantic judgments run on a local model, Phase 1 should include an early, explicit check of whether Qwen can reliably execute a multi-step tool-calling loop at all, rather than assuming it and discovering otherwise mid-Phase-6.

---

## 11. Platform Goal

The system is designed to run naturally on Windows. WSL may remain an optional development environment but is not an architectural requirement.

```
Windows → Python → Ollama → Local model → Orchestrator → Document tools
```

---

## 12. Design Principles

- **Model independence** — the orchestration system does not depend on a particular LLM vendor.
- **Tool independence** — agents interact with capabilities through stable tool interfaces rather than manipulating databases directly.
- **Context efficiency** — never place large amounts of information into context merely because it is available.
- **Progressive disclosure** — give the model the minimum useful information first and let it request more.
- **Model proposes, Python validates** — any claim an agent produces about a fact, a revision, or a computed value passes through deterministic validation before it is accepted into the domain model. This applies to every agent that emits structured claims, not only The_Reader.
- **Grounding vs. interpretation are different guarantees** — the system distinguishes what it can *prove* (the cited text exists, the math is correct) from what it can only *judge* (the text means what the model says it means), and tracks confidence accordingly rather than treating both as equally certain.
- **Separation of concerns** — Model, Orchestration, Tools, Context, Domain Model, and Data remain distinct layers.
- **Auditable reasoning** — important conclusions are traceable back to evidence and source documents, including which claim in a FactHistory produced them.
- **Local-first** — the architecture works with local models and local data without requiring a cloud API.
- **Replaceability** — any individual model, retrieval system, agent, or tool can be replaced without redesigning the entire system.

---

## 13. Final Architecture

```
                              USER
                               │
                               ▼
                         ORCHESTRATOR
                               │
                ┌──────────────┼──────────────┐
                ▼               ▼               ▼
           The_Reader      The_Auditor      The_Drafter
                │               │               │
                └──────────────┼──────────────┘
                               │
                        CONTEXT ENGINE
                               │
                ┌──────────────┼──────────────┐
                ▼               ▼               ▼
             Search        Structure         Expand
                │               │               │
                └──────────────┼──────────────┘
                               │
                         DOMAIN MODEL
                               │
                ┌──────────────┼──────────────┐
                ▼               ▼               ▼
             Claims         Evidence         Findings
                               │
                               ▼
                        DOCUMENT STORE
                        SQLite / Chroma
                               │
                               ▼
                           DOCUMENTS

                               ▲
                               │
                         MODEL BACKEND
                               │
                     ┌─────────┴─────────┐
                     ▼                   ▼
               Ollama/Qwen           Other LLM
```

Each claim flowing through the Domain Model carries its own `FactHistory` — grounded claims, revision events, and the deterministic computations that produced the current value — so any Finding in the final report can be traced back to the evidence and the validation steps that produced it, not just the model's final sentence.

---

## 14. Cordis — Where It Fits, Held in Reserve

Cordis reframes the middle of the architecture from hard-coded modules to mountable/unmountable components with declared `provides` / `requires` and reversible effects:

```
ORCHESTRATOR
     │
     ▼
RUNTIME CONTEXT
     │
┌────┴────┬─────────┐
▼          ▼          ▼
Model    Tools     Context Engine
Provider Provider  Provider
```

Two ideas are worth keeping in mind even before this is built:

**Temporal composability** — a component's effects on the runtime (registered tools, event handlers, state) have a tracked inverse, so unmounting it cleanly undoes what it did, instead of requiring hand-maintained cleanup code.

**Spatial composability** — components declare dependencies and activate/deactivate automatically as those dependencies become available or unavailable (e.g. `The_Auditor` only becomes active once `AuditStore` is mounted).

This becomes genuinely useful once there are multiple variants of an agent (`Reader`, `Reader+OCR`, `Reader+Legal`) and the system needs to compose a profile (`legal_document_analysis` vs. `research_papers`) from a shared pool of components rather than hard-coding one fixed pipeline.

**This is explicitly not a near-term build target.** Cordis's own API is unstable, and the base system — orchestrator, document tools, domain model, context engine — needs to exist and work before a composability layer has anything real to compose. The pattern (provides / requires / effects / lifecycle) is worth designing toward from Phase 5 onward; the full runtime is adopted only if and when plugin-lifecycle pain actually shows up in practice, not on a schedule.

---

## 15. Development Roadmap

The original roadmap was written before The_Reader existed. The project has now crossed that boundary: the Reader's core verification pipeline, typed result model, proof-of-concept path, and SQLite persistence are implemented on `master`.

The roadmap should therefore be read as **current state → next architectural layer**, rather than as a list of work that has not started.

### Completed / substantially completed

**Phase 1 — Preserve the existing Orchestra. — COMPLETE**

The repository retains the model-backend abstraction and generic orchestrator/tool architecture. The Reader proof of concept can select a backend independently of its verification logic.

**Phase 2 — Establish the document/fact verification boundary. — COMPLETE FOR THE READER POC**

The Reader can take a chunk and checklist, obtain model-produced evidence, verify that evidence against the chunk, and continue through additional verification stages.

**Phase 3 — Build the Reader verification pipeline. — COMPLETE / ACTIVE MAINTENANCE**

The Reader now performs:

```text
parse
→ quote verification
→ quote repair
→ support judgment
→ correction
→ numeric revision detection
→ revision validation
→ Python computation
→ ReaderResult
```

**Phase 4 — Establish typed domain objects. — COMPLETE FOR THE READER**

`models.py` now defines the typed vocabulary used by the verification pipeline:

`Evidence`, `FactClaim`, `SupportJudgment`, `ComputedValue`, `RevisionEvent`, `ReaderResult`, and `FactHistory`.

The important architectural change is that `process_entry()` now returns a `ReaderResult` rather than a final mutable dictionary.

**Phase 5 — Establish canonical Reader persistence. — IMPLEMENTED**

`reader_result_store.py` provides SQLite persistence with explicit relationships among processing runs, facts, claims, evidence, support judgments, revisions, and Reader results.

The intended rule is now concrete:

```text
ReaderResult
     ↓
SQLite canonical record
     ↓
future derived indexes (e.g. vectors)
```

### Current next steps

**Phase 6 — Measure The_Reader. — NEXT**

Build the small labeled evaluation set described in Section 9a.

The evaluation should deliberately include:

- correctly supported claims,
- exact quotes that are topically related but do not answer the question,
- fabricated/non-verbatim quotes,
- repairable quotes,
- corrected answers,
- valid numeric revisions,
- revisions to a different fact,
- ambiguous revision candidates,
- malformed model outputs.

*Deliverable: a repeatable Reader evaluation harness with measured semantic accuracy and a clear `NEEDS_REVIEW` baseline.*

**Phase 7 — Finish FactHistory aggregation.**

The current `FactHistory` builder handles one `ReaderResult`. Extend it so multiple results for the same question can be merged across chunks and runs without destroying provenance.

The desired shape is:

```text
Chunk 1 → ReaderResult ─┐
Chunk 2 → ReaderResult ─┼→ FactHistory
Chunk 3 → ReaderResult ─┤
Chunk N → ReaderResult ─┘
```

This is the missing bridge between local Reader reasoning and document-wide state.

*Deliverable: durable cross-chunk fact timelines with explicit provenance and deterministic state transitions.*

**Phase 8 — Build The_Auditor.**

The Auditor operates above individual Reader passes.

Its first responsibility is not to "read documents better." It is to resolve relationships among already-structured Reader results:

```text
ReaderResult / FactHistory
        ↓
compare claims across chunks
        ↓
identify supersession / contradiction
        ↓
construct document-level state
```

Only after this is reliable should The_Verifier become responsible for actively searching for counter-evidence.

*Deliverable: document-level fact resolution built on measured Reader outputs.*

### Later architecture

**Phase 9 — Build The_Chunker and document ingestion.**

Generalize the current single-chunk POC into a document pipeline:

```text
Document
   ↓
The_Chunker
   ↓
identified chunks
   ↓
The_Reader
   ↓
ReaderResults
   ↓
FactHistory
   ↓
The_Auditor
```

Support the intended document formats and preserve stable chunk/source provenance.

**Phase 10 — Build the Context Engine.**

The Context Engine should come after the Reader/Auditor data model is proven. It should be built as a retrieval/context layer over canonical structured state and source indexes, not as a replacement for either.

Start with:

```text
query → search → rank → select
```

Then add capabilities in response to real retrieval requirements:

- structural relationships and document hierarchy,
- parent/child and neighboring-context expansion,
- explicit references,
- related claims from `FactHistory`,
- progressive disclosure / L0-L1-L2 representations,
- reranking where it measurably helps,
- retrieval trajectory/trace recording,
- token budgeting,
- agent/task state.

A vector database may provide the semantic-search primitive. It should remain a derived index. The Context Engine owns the policy for combining semantic retrieval with structure, canonical fact state, references, and context expansion.

OpenViking is an architectural reference here rather than a dependency requirement. Its useful contribution is the combination of vector retrieval, hierarchy, progressive disclosure, and observable retrieval—not the claim that a specialized context database inherently produces better nearest-neighbor search than a good vector database.

The Context Engine should be driven by actual retrieval needs discovered while building the document pipeline, rather than being built as a generic abstraction first.

**Phase 11 — Connect the agents to the Orchestra.**

Once Reader, FactHistory, Auditor, and document ingestion have stable contracts, move them behind the generic orchestration layer.

The desired architecture becomes:

```text
User
 ↓
Orchestrator
 ↓
specialized agent
 ↓
tools / context
 ↓
typed domain result
 ↓
canonical store
```

The current Reader POC is deliberately simpler than this: it selects a model backend directly and runs the Reader pipeline. That is useful for proving the domain logic without simultaneously debugging the entire orchestration stack.

**Phase 12 — Replace demo data with user-controlled corpora.**

The bundled example data becomes a fixture only. Users provide their own documents through the eventual ingestion interface.

### Deferred / conditional work

**Cordis-style composability remains deferred.**

The project should not build a full dynamic plugin runtime simply because the architecture can describe one.

First establish whether multiple agent/tool variants actually create lifecycle and dependency-management pain. If they do, introduce the smallest useful `provides` / `requires` / lifecycle abstraction at that point.

The desired progression is:

```text
stable agents
    ↓
real composition pressure
    ↓
minimal capability declarations
    ↓
mount / unmount if needed
    ↓
full composability only if justified
```

This keeps Cordis as an architectural influence rather than allowing it to become infrastructure that the project does not yet need.

## 16. The Core Thesis

The project is not simply "run Claude's document workflow locally." It is:

> Build a model-independent agentic architecture that combines adaptive context management with specialized document intelligence, allowing a local model to progressively discover, retrieve, verify, and reason over information far larger than its raw context window — while keeping an explicit, auditable line between what the system has proven and what it has judged.

The four source projects contribute different pieces:

```
LewNekos_AI_Orchestra  → HOW THE AGENT OPERATES
Sixfeetup OrchestrateAgenticAI → WHAT THE AGENT CAN DO WITH DOCUMENTS
Aider                   → HOW THE AGENT DECIDES WHAT CONTEXT IT NEEDS
OpenViking              → HOW HIERARCHY + PROGRESSIVE CONTEXT RETRIEVAL CAN BE STRUCTURED (reference)
Cordis                  → HOW THE SYSTEM COMPOSES CAPABILITIES AT RUNTIME (reserve)
```

And The_Reader's fact-history design (Section 6a) contributes a fifth piece that cuts across all of them: **HOW THE SYSTEM KNOWS THE DIFFERENCE BETWEEN WHAT IT FOUND, WHAT THE MODEL CONCLUDED, AND WHAT THE SYSTEM CAN DETERMINISTICALLY ESTABLISH.**

```
              ┌─────────────────────┐
              │     LOCAL MODEL      │
              └──────────┬──────────┘
                         │
                    ORCHESTRATOR
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
      CONTEXT ENGINE          DOMAIN TOOLS
              │                     │
              └──────────┬──────────┘
                         ▼
                   DOMAIN MODEL
              (claims validated before
               they become facts)
                         │
                         ▼
                     DOCUMENTS
```

Whenever the project is tempted to add a new agent or Python file, the discipline is to ask: which architectural layer does it belong to, what capability does it add, and — following Section 9a — what in it is a deterministic guarantee versus a semantic judgment that needs to be measured against ground truth before something else depends on it.
