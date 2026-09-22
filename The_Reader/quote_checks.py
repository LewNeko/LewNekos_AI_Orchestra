"""
quote_checks.py
----------------
Everything about a single question: "does this quote exist verbatim in the
chunk", and "does this quote actually support this specific claim". This
module never asks whether some OTHER, later statement revises a claim -
that's revisions.py's job. The two are kept separate because a quote can
be perfectly real and perfectly supportive of a claim that later turns out
to be stale.
"""
from .fact_types import classify_fact_type, is_valid_value
from .models import Evidence, FactClaim, SupportJudgment
from .parsing import normalize, parse_fields
from .prompts import ANSWER_SUPPORT_PROMPT, QUOTE_REPAIR_PROMPT


def verify(entries, chunk):
    """Check each entry against the source chunk and assign a status."""
    report = []
    for e in entries:
        status = "MISSING_FIELDS"
        if e["item"] and e["answer"] and e["quote"]:
            if e["quote"].strip().upper() == "NOT FOUND":
                status = "OK_NOT_FOUND"
            elif normalize(e["quote"]) in normalize(chunk):
                status = "VERIFIED"
            else:
                status = "UNVERIFIED_QUOTE"  # <-- fabrication flag
        report.append({**e, "status": status})
    return report


def verified_categorizer(entries):
    #report(first pass) = [{'item': 'Does this chunk state a specific due date for payment?', 'answer': 'YES', 'quote': 'The invoice was issued on March 3rd, 2024', 'status': 'VERIFIED', 'category': 'DETERMINISTIC'}]
    report = []
    for e in entries:
        answer_type = "UNCATEGORIZED"
        if e['status'] == "VERIFIED" and e['answer'] in ("YES", "NO"):
            answer_type = "DETERMINISTIC"
        report.append({**e,"category":answer_type})
    return report


def repair_quote(chunk, entry, chat_fn):
    """Narrow retry for UNVERIFIED_QUOTE: keep the answer, only ask for a
    better (exact) quote. Returns {"answer": ..., "quote": ...}."""
    prompt = QUOTE_REPAIR_PROMPT.format(
        chunk=chunk, item=entry['item'], answer=entry['answer']
    )
    reply = chat_fn(prompt)
    fields = parse_fields(reply)
    return {"answer": fields.get("ANSWER"), "quote": fields.get("QUOTE")}


def check_answer_support(chunk, entry, chat_fn):
    """Narrow check for VERIFIED entries: does the exact quote actually
    support this specific question+answer, or only the general topic?
    May return a corrected answer. Returns {"answer": ..., "quote": ...}."""
    prompt = ANSWER_SUPPORT_PROMPT.format(
        chunk=chunk, item=entry['item'], answer=entry['answer'], quote=entry['quote']
    )
    reply = chat_fn(prompt)
    fields = parse_fields(reply)
    return {"answer": fields.get("ANSWER"), "quote": fields.get("QUOTE")}


def _judge_support(working_claim, raw_support, chunk):
    """Translate check_answer_support()'s raw model-oriented dict into
    domain objects. This is the ONE place the old "answer"/"quote" dict
    vocabulary is allowed to leak in from the helper; process_entry never
    reads raw_support directly.

    Returns (SupportJudgment, corrected_claim_or_None). corrected_claim is
    None when the evidence supported the existing claim - i.e. nothing new
    to report, working_claim stands as-is - OR when the model proposed a
    correction whose value isn't even the right type for this fact.
    """
    proposed_value = (raw_support.get("answer") or "").strip()
    proposed_quote = (raw_support.get("quote") or "").strip()

    if not proposed_value or proposed_value.upper() == working_claim.value.strip().upper():
        return SupportJudgment(verdict="SUPPORTED", checked_claim=working_claim), None

    judgment = SupportJudgment(verdict="UNSUPPORTED", checked_claim=working_claim)

    # A proposed correction that doesn't match the original fact's type
    # (e.g. a numeric fact "corrected" to free text) is a model glitch,
    # not a usable correction - reject it before it becomes a FactClaim.
    fact_type = classify_fact_type(working_claim.value)
    if not is_valid_value(proposed_value, fact_type):
        return judgment, None

    if not proposed_quote or proposed_quote.upper() == "NOT FOUND" \
            or normalize(proposed_quote) not in normalize(chunk):
        corrected = FactClaim(value=proposed_value, evidence=Evidence("NOT FOUND"))
    else:
        corrected = FactClaim(value=proposed_value, evidence=Evidence(proposed_quote))
    return judgment, corrected
