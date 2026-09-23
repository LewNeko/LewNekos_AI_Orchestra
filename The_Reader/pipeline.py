"""
pipeline.py
-----------
Orchestrates parsing.py, fact_types.py, quote_checks.py, and revisions.py
into the full per-entry loop: repair a bad quote -> check whether the
quote actually supports the claim -> check whether something later
revises the (now-supported) claim. This is the only module that builds a
RevisionEvent/ComputedValue from raw model text (mirroring how
quote_checks._judge_support was already the one place that builds a
SupportJudgment/corrected FactClaim).
"""
from .fact_types import classify_fact_type, format_amount
from .models import (
    ComputedValue,
    Evidence,
    FactClaim,
    FactHistory,
    ReaderResult,
    RevisionEvent,
)
from .parsing import normalize, parse_fields
from .quote_checks import _judge_support, check_answer_support, repair_quote
from .revisions import _validate_revision, check_for_revision, compute_corrected_value


def build_fact_history(result):
    """Turn ONE ReaderResult into a FactHistory. Deliberately thin for now -
    a real builder would merge ReaderResults across multiple runs/chunks for
    the same question, appending new claims/revisions onto an existing
    FactHistory instead of creating one from scratch each time."""
    claims = [result.initial_claim]
    if result.corrected_claim is not None:
        claims.append(result.corrected_claim)
    revisions = [result.revision] if result.revision is not None else []
    return FactHistory(
        question=result.question,
        fact_type=result.fact_type,
        claims=claims,
        revisions=revisions,
    )


def _terminal_status(corrected_claim, evidence_repair):
    """Pick the right terminal status when nothing further (no numeric
    revision) changes the claim. A corrected value takes priority over a
    same-value quote repair, which takes priority over plain no-change -
    they're not mutually exclusive (a claim can be both quote-repaired AND
    later corrected), and the corrected_claim always wins."""
    if corrected_claim is not None: #if no corrected claim it means the initial one was fine so there's no need for a verified corrected status
        return "VERIFIED_CORRECTED"
    if evidence_repair is not None: #if the evidence (quote) wasn't verbatim before and was corrected, theres a verified repaired quote
        return "VERIFIED_REPAIRED_QUOTE"
    return "VERIFIED_NO_CHANGE" #if claim wasn't corrected and the quote wasn't corrected then there was no change


def process_entry(chunk, entry, chat_fn):
    """Run ONE checklist entry through the full loop and return a
    ReaderResult - the entire chain (initial claim, any quote repair, any
    support judgment/correction, any revision), not just a final value.

    This function does NOT decide what the long-term fact history looks
    like - it just reports what happened on this one pass. Building
    FactHistory out of one or more ReaderResults is a separate step.
    """
    question = entry["item"]
    fact_type = classify_fact_type(entry["answer"]) #boolean, numeric, date*, percent, text, currency or unknown
    initial_claim = FactClaim(value=entry["answer"], evidence=Evidence(entry["quote"]))

    if entry["status"] == "MISSING_FIELDS":
        return ReaderResult(
            question=question, fact_type=fact_type, initial_claim=initial_claim,
            status="NEEDS_REVIEW",
            reason="One or more of item/answer/quote were missing from the model output.",
        )

    working_claim = initial_claim
    quote_status = entry["status"]
    evidence_repair = None

    # Step 1: repair a bad quote BEFORE trusting anything else about this entry.
    if quote_status == "UNVERIFIED_QUOTE":
        repaired = repair_quote(chunk, entry, chat_fn)
        candidate = (repaired.get("quote") or "").strip()
        if candidate and candidate.upper() != "NOT FOUND" and normalize(candidate) in normalize(chunk):
            evidence_repair = Evidence(candidate)
            # the answer is unchanged by design (repair_quote can't touch it) -
            # only the evidence backing it changes.
            working_claim = FactClaim(value=working_claim.value, evidence=evidence_repair)
            quote_status = "VERIFIED"
        else:
            return ReaderResult(
                question=question, fact_type=fact_type, initial_claim=initial_claim,
                status="NEEDS_REVIEW",
                reason="Quote could not be verified even after a repair attempt.",
            )

    # OK_NOT_FOUND ("the model correctly said no evidence exists") is already terminal.
    if quote_status == "OK_NOT_FOUND":
        return ReaderResult(
            question=question, fact_type=fact_type, initial_claim=initial_claim,
            status="VERIFIED_NO_CHANGE",
        )

    # Step 2: the quote exists verbatim - but does it actually support THIS
    # question and THIS value, or just the general topic? check_answer_support
    # still speaks the raw "answer"/"quote" dict vocabulary (that's the model
    # boundary) - _judge_support is the one place that gets translated into
    # domain objects, so nothing past this point touches a dict again.
    raw_support = check_answer_support(
        chunk, {"item": question, "answer": working_claim.value, "quote": working_claim.evidence.quote}, chat_fn
    )
    support_judgment, corrected_claim = _judge_support(working_claim, raw_support, chunk)

    if corrected_claim is not None:
        working_claim = corrected_claim
        if corrected_claim.evidence.quote == "NOT FOUND":
            # The claim changed and has no exact evidence of its own - still
            # terminal, but it's a correction, not "no change".
            return ReaderResult(
                question=question, fact_type=fact_type, initial_claim=initial_claim,
                evidence_repair=evidence_repair, support_judgment=support_judgment,
                corrected_claim=corrected_claim, status="VERIFIED_CORRECTED",
                reason="Original evidence did not support the original claim; claim corrected.",
            )
        # else: corrected AND backed by a new exact quote - keep going below
        # with the corrected claim so a revision can still be checked against it.

        # Step 3: does some OTHER, later statement revise this (now-supported) claim?
    # REVISION_EXTRACT_PROMPT + compute_corrected_value is an arithmetic
    # mechanism (ORIGINAL_VALUE / DELTA_VALUE / DELTA_DIRECTION) - it only
    # makes sense for numeric facts. Running it on a boolean/text fact means
    # asking the model to invent numbers that don't exist, so skip it.
    if fact_type != "numeric":
        return ReaderResult(
            #it's easier to understand if you debug and hover over the variables in returns like these
            question=question, fact_type=fact_type, initial_claim=initial_claim,
            evidence_repair=evidence_repair, support_judgment=support_judgment,
            corrected_claim=corrected_claim,
            status=_terminal_status(corrected_claim, evidence_repair),
        )

    revision_entry = {
        "item": question, "answer": working_claim.value, "quote": working_claim.evidence.quote,
        "status": "VERIFIED", "category": entry.get("category"),
    }
    revision_text = check_for_revision(chunk, revision_entry, chat_fn)
    revision_fields = parse_fields(revision_text)

    # Phase A: validate the candidate revision BEFORE any arithmetic runs.
    validation = _validate_revision(working_claim, revision_fields, chunk)

    if validation["outcome"] == "INVALID":
        return ReaderResult(
            question=question, fact_type=fact_type, initial_claim=initial_claim,
            evidence_repair=evidence_repair, support_judgment=support_judgment,
            corrected_claim=corrected_claim, status="NEEDS_REVIEW",
            reason=validation["reason"],
        )

    if validation["outcome"] == "IRRELEVANT":
        return ReaderResult(
            question=question, fact_type=fact_type, initial_claim=initial_claim,
            evidence_repair=evidence_repair, support_judgment=support_judgment,
            corrected_claim=corrected_claim,
            status=_terminal_status(corrected_claim, evidence_repair),
            reason=validation["reason"],
        )

    if validation["outcome"] == "VALID":
        # Phase B: only now does Python compute anything.
        computed = compute_corrected_value(revision_text, revision_entry)

        if computed == "PARSE_ERROR" or computed is None:
            return ReaderResult(
                question=question, fact_type=fact_type, initial_claim=initial_claim,
                evidence_repair=evidence_repair, support_judgment=support_judgment,
                corrected_claim=corrected_claim, status="NEEDS_REVIEW",
                reason="Revision passed validation but could not be computed.",
            )

        final_value = format_amount(computed) if isinstance(computed, float) else str(computed)
        revision = RevisionEvent(
            evidence=Evidence(validation["revision_quote"]),
            operation=revision_fields.get("DELTA_DIRECTION", "NONE"),
            amount=revision_fields.get("DELTA_VALUE", "0"),
            computed_value=ComputedValue(final_value),
        )
        return ReaderResult(
            question=question, fact_type=fact_type, initial_claim=initial_claim,
            evidence_repair=evidence_repair, support_judgment=support_judgment,
            corrected_claim=corrected_claim, revision=revision, status="VERIFIED_REVISED",
        )

    # outcome == "NONE": nothing revised it - done.
    return ReaderResult(
        question=question, fact_type=fact_type, initial_claim=initial_claim,
        evidence_repair=evidence_repair, support_judgment=support_judgment,
        corrected_claim=corrected_claim,
        status=_terminal_status(corrected_claim, evidence_repair),
    )


def run_entry_loop(report, chunk, chat_fn):
    """Run every checklist entry through process_entry. Returns a list of
    ReaderResult objects - nothing is left hanging on a printed warning."""
    return [process_entry(chunk, entry, chat_fn) for entry in report]
