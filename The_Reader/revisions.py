"""
revisions.py
------------
Everything about whether some OTHER, later statement in the chunk revises
an already-supported claim (e.g. "made it a thousand dollars less").
This module only validates and extracts the raw pieces of a candidate
revision - it never builds a RevisionEvent/ComputedValue itself. That
translation into domain objects, and the arithmetic in
compute_corrected_value(), only becomes "real" once pipeline.py decides
the candidate is VALID; this module just says whether it's safe to trust.
"""
from .parsing import normalize, parse_fields
from .prompts import REVISION_EXTRACT_PROMPT


def is_self_referential(entry, fields):
    """Catches if the models sites the original quote as its own 'revision'.
    prevents the reviser from not revising a little"""
    revision_quote = fields.get("REVISION_QUOTE","")
    return normalize(revision_quote) == normalize(entry.get("quote",""))


def check_for_revision(chunk, entry, chat_fn):
    """checks the model's initial output for revision"""
    prompt = REVISION_EXTRACT_PROMPT.format(
        chunk=chunk, category=entry['category'], item=entry['item'], answer=entry['answer'], quote=entry['quote'], status=entry['status']
    )
    return chat_fn(prompt)


def compute_corrected_value(revision_result_text, entry = None):
    """Pure Python math so the model isn't involved.
    AI is bad at math, so give it a calculator"""
    fields = parse_fields(revision_result_text)

    if fields.get("REVISED") != "YES":
        return None #its not revised so theres nothing to compute

    if entry and is_self_referential(entry, fields):
        print("it is self referentially revising here, so ignore this revision")
        return None # catches false positive when the revision cites itself.

    direction = fields.get("DELTA_DIRECTION", "NONE")
    if direction == "NONE":
        return None

    try:
        original = float(fields["ORIGINAL_VALUE"].replace("$", "").replace(",", ""))
        delta = float(fields["DELTA_VALUE"].replace("$", "").replace(",", ""))
    except (KeyError, ValueError):
        return "PARSE_ERROR" #if the parser messed up

    #covers the four basic arithmetic operations
    if direction == "DECREASE":
        return original - delta
    elif direction == "INCREASE":
        return original + delta
    elif direction == "DIVIDED":
        return original / delta
    elif direction == "MULTIPLIED":
        return original * delta
    return None


def _validate_revision(working_claim, revision_fields, chunk):
    """Phase A of Step 3: decide whether a candidate revision is real,
    evidenced, relevant to working_claim, and internally consistent -
    WITHOUT computing anything. compute_corrected_value() (Phase B) only
    runs if this returns "VALID".

    Note: there's no check_revision_relevance() in this codebase (checked
    before writing this). The closest existing mechanism is
    is_self_referential(), which catches the model citing the original
    quote back at itself. There was previously no check that the revision's
    stated ORIGINAL_VALUE actually matches working_claim's value, so that's
    added here as the other half of "relevant to this fact."

    Returns one of:
        {"outcome": "NONE"}                          - model found no revision
        {"outcome": "VALID", "revision_quote": ...}   - safe to compute
        {"outcome": "IRRELEVANT", "reason": ...}      - real revision, wrong fact
        {"outcome": "INVALID", "reason": ...}         - unverifiable/unusable
    """
    if revision_fields.get("REVISED") != "YES":
        return {"outcome": "NONE"}

    revision_quote = revision_fields.get("REVISION_QUOTE", "")
    if not revision_quote or normalize(revision_quote) not in normalize(chunk):
        return {"outcome": "INVALID", "reason": "Revision quote could not be verified against the source."}

    # Relevance check #1 (the mechanism that already exists in this codebase):
    # catches the model citing the original quote back at itself as its own "revision".
    if is_self_referential({"quote": working_claim.evidence.quote}, revision_fields):
        return {"outcome": "IRRELEVANT", "reason": "Candidate revision concerns a different fact (self-referential match)."}

    # Relevance check #2 (new): does the revision's stated original value
    # even match the value currently on working_claim? If not, the model
    # found a real revision - just not to this fact.
    try:
        claim_value = float(working_claim.value.replace("$", "").replace(",", ""))
        revision_original = float(revision_fields.get("ORIGINAL_VALUE", "").replace("$", "").replace(",", ""))
    except (ValueError, AttributeError):
        return {"outcome": "INVALID", "reason": "Could not parse the revision's original value for comparison."}

    if abs(claim_value - revision_original) > 0.01:
        return {"outcome": "IRRELEVANT", "reason": "Candidate revision concerns a different fact (original value doesn't match this claim)."}

    return {"outcome": "VALID", "revision_quote": revision_quote}
