"""
models.py
---------
The typed vocabulary for the verification pipeline. Nothing in here is a
plain dict, and nothing is called "answer" - every value says what kind of
value it is (a model's claim, a piece of evidence, a judgment about whether
evidence supports a claim, a revision, or a value Python computed).

These are intentionally small and frozen (immutable) wherever a step
produces a *new* fact rather than editing an old one. If a quote gets
repaired, that's a new FactClaim, not a mutation of the old one - so you
can always look at a ReaderResult and see the whole chain that led to the
final value, not just the last thing written into a field called "answer".
"""
from dataclasses import dataclass, field
from typing import Literal, Optional

FactType = Literal["boolean", "numeric", "text"]
Verdict = Literal["SUPPORTED", "UNSUPPORTED"]
Operation = Literal["INCREASE", "DECREASE", "MULTIPLIED", "DIVIDED", "NONE"]

# Every terminal state a ReaderResult can end up in.
Status = Literal[
    "VERIFIED_NO_CHANGE",
    "VERIFIED_REPAIRED_QUOTE",
    "VERIFIED_REVISED",
    "VERIFIED_CORRECTED",
    "NEEDS_REVIEW",
]


@dataclass(frozen=True)
class Evidence:
    """One quote, already confirmed to exist verbatim in the source chunk.
    Nothing downstream should ever hold a quote that hasn't passed through
    an Evidence - that's what makes 'exact substring of the chunk' a type
    guarantee instead of something re-checked ad hoc everywhere."""
    quote: str


@dataclass(frozen=True)
class FactClaim:
    """One value someone (a model, or a repair step) asserted, backed by
    one piece of Evidence. A FactClaim is never edited in place - a
    correction produces a brand new FactClaim."""
    value: str
    evidence: Evidence


@dataclass(frozen=True)
class SupportJudgment:
    """The verdict on whether a claim's evidence actually supports its
    value (e.g. 'issued on March 3rd' does NOT support 'due March 3rd')."""
    verdict: Verdict
    checked_claim: FactClaim


@dataclass(frozen=True)
class ComputedValue:
    """A value derived in pure Python arithmetic from a RevisionEvent.
    The model is never trusted to do the math - it only supplies the
    operation and amount; this is always Python's output."""
    value: str


@dataclass(frozen=True)
class RevisionEvent:
    """A later statement in the source that changes an earlier claim
    (e.g. 'made it a thousand dollars less')."""
    evidence: Evidence
    operation: Operation
    amount: str
    computed_value: ComputedValue


@dataclass
class ReaderResult:
    """What process_entry() actually returns for ONE checklist question on
    ONE pass through the pipeline. This is the full, inspectable chain -
    initial claim, any quote repair, any support judgment + correction, any
    revision - not just a final answer. process_entry() is NOT responsible
    for deciding what the long-term fact history looks like; it just reports
    what happened this pass."""
    question: str
    fact_type: FactType
    initial_claim: FactClaim
    status: Status
    evidence_repair: Optional[Evidence] = None
    support_judgment: Optional[SupportJudgment] = None
    corrected_claim: Optional[FactClaim] = None
    revision: Optional[RevisionEvent] = None
    reason: Optional[str] = None

    @property
    def current_value(self) -> str:
        """The best-known value after this pass: revised > corrected > initial."""
        if self.revision is not None:
            return self.revision.computed_value.value
        if self.corrected_claim is not None:
            return self.corrected_claim.value
        return self.initial_claim.value

    @property
    def current_quote(self) -> str:
        if self.evidence_repair is not None:
            return self.evidence_repair.quote
        if self.corrected_claim is not None:
            return self.corrected_claim.evidence.quote
        return self.initial_claim.evidence.quote


@dataclass
class FactHistory:
    """The durable, cross-run record for a single question: every claim
    ever made about it and every revision ever found for it, in order.
    A ReaderResult is one pass; a FactHistory is the accumulated timeline.
    (Merging multiple ReaderResults - e.g. across re-runs or chunks - into
    one FactHistory is the 'FactHistory builder' step; not built out yet.)"""
    question: str
    fact_type: FactType
    claims: list[FactClaim] = field(default_factory=list)
    revisions: list[RevisionEvent] = field(default_factory=list)

    @property
    def current_value(self) -> str:
        if self.revisions:
            return self.revisions[-1].computed_value.value
        if self.claims:
            return self.claims[-1].value
        return "UNKNOWN"

    @property
    def derived_from(self) -> str:
        """Human-readable pointer to whichever claim/revision current_value came from."""
        if self.revisions:
            return f"revision #{len(self.revisions)} ({self.revisions[-1].operation} {self.revisions[-1].amount})"
        if self.claims:
            return f"claim #{len(self.claims)}"
        return "nothing yet"
