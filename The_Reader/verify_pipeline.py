""" 
verify_pipeline.py
----------------
used for testing the revision-check 
function against a stale amount entry. """
from py_compile import(
    main,
) 
import re

try:
    from .models import (
        ComputedValue,
        Evidence,
        FactClaim,
        ReaderResult,
        RevisionEvent,
        SupportJudgment,
    )
except ImportError:
    # Falls back to a plain import so this file still runs standalone
    # (e.g. `python verify_pipeline.py`) as well as inside the package.
    from models import (
        ComputedValue,
        Evidence,
        FactClaim,
        ReaderResult,
        RevisionEvent,
        SupportJudgment,
    )

CHUNK = """The invoice was issued on March 3rd, 2024, to Acme
"Corp. Payment terms are net-30. The total amount due is 
"$4,250.00. No late fee schedule is mentioned in this section. 
" They felt bad about that total amount due and made it a 
"thousand dollars less."""
# Simulating Gemma's actual raw output from your test
RAW_OUTPUT = """ITEM: Does this chunk state a specific due date for payment?
ANSWER: YES
QUOTE: The invoice was issued on March 3rd, 2024

ITEM: Does this chunk mention a late fee or penalty amount?
ANSWER: NO
QUOTE: No late fee schedule is mentioned in this section.

ITEM: Does this chunk name the company being invoiced?
ANSWER: YES
QUOTE: The invoice was issued to Acme Corp.

ITEM: What's the amount due?
ANSWER: $4,250.00
QUOTE: The total amount due is $4,250.00"""
#Small prompt for the reviser model
REVISION_CHECK_PROMPT = """You are checking whether a previously 
extracted answer is still accurate given the FULL source chunk below.

CHUNK:
{chunk}

An earlier step extracted this answer:
ITEM: {item}
ANSWER: {answer}
QUOTE: {quote}
Status: {status}
Does any OTHER sentence in the chunk revise, correct, override, or update this specific fact?
Respond in exactly this format:

REVISED: YES or NO
REVISION_QUOTE: <exact sentence that revises it, or NOT FOUND>
CORRECTED_ANSWER: <the new value if revised, or SAME>
"""
#Retry prompt used ONLY when the exact quote failed verification.
#Deliberately narrow: it must NOT be allowed to change the answer,
#only find a better (exact) supporting sentence.
QUOTE_REPAIR_PROMPT = """Your previous answer to the question below is being KEPT AS-IS: {answer}

The quote you gave earlier was not an exact, verbatim sentence from the source text.
Find ONE exact sentence, copied verbatim from the CHUNK below, that supports this answer.
If no exact supporting sentence exists in the CHUNK, respond with NOT FOUND.
Do not change the ANSWER. Do not paraphrase the QUOTE.

CHUNK:
{chunk}

QUESTION: {item}
ANSWER: {answer}

Respond in exactly this format:
ANSWER: {answer}
QUOTE: <exact sentence copied verbatim from the chunk, or NOT FOUND>
"""
#Used ONLY when the quote is an exact match but we haven't checked whether
#it actually answers the specific question asked (e.g. "issued on" vs "due on").
#This prompt IS allowed to change the answer, since that's the whole point.
ANSWER_SUPPORT_PROMPT = """You are checking whether a quote actually supports a specific answer
to a specific question. Be strict: the quote must state the answer directly.
Being topically related is not enough (e.g. an "issued" date does not support a "due" date).

QUESTION: {item}
ANSWER: {answer}
QUOTE: {quote}

Does the QUOTE directly support this exact ANSWER to this exact QUESTION?
- If yes, return the same ANSWER and the same QUOTE.
- If no, return the corrected ANSWER (e.g. NO, or NOT FOUND, or the correct value) and
  an exact supporting QUOTE copied verbatim from the CHUNK below, or NOT FOUND if none exists.

CHUNK:
{chunk}

Respond in exactly this format:
ANSWER: <YES, NO, NOT FOUND, or the corrected value>
QUOTE: <exact sentence copied verbatim from the chunk, or NOT FOUND>
"""
#Extraction prompt for the reviser model to avoid doing math (AI is bad at math)
REVISION_EXTRACT_PROMPT = """You are checking whether a previously 
extracted answer is still accurate given the FULL source chunk below.

CHUNK:
{chunk}

An earlier step extracted this answer:
ITEM: {item}
ANSWER: {answer}
QUOTE: {quote}
Status: {status}
category: {category}

Does any OTHER sentence in the chunk revise this SPECIFIC fact (not some other fact in the chunk)?
Does the revision quote refer to the same entity/subject as the original quote?
A sentence is only a revision if it refers to the same subject.
Only answer YES if the revising sentence is clearly talking about the same thing as the ANSWER above.
If the only candidate sentence you can find is about a different fact, answer NO.
Do NOT calculate the corrected value yourself. Only extract the raw numbers. 
Respond in exactly this format:

REVISED: YES or NO
REVISION_QUOTE: <exact sentence that revises it, or NOT FOUND>
ORIGINAL_VALUE: <the original number in the QUOTE, digits only>
DELTA_DIRECTION: INCREASE, DECREASE, DIVIDED, MULTIPLIED, or NONE
DELTA_VALUE: <the change amount, digits only>
"""

def is_self_referential(entry, fields):
    """Catches if the models sites the original quote as its own 'revision'.
    prevents the reviser from not revising a little"""
    revision_quote = fields.get("REVISION_QUOTE","")
    return normalize(revision_quote) == normalize(entry.get("quote",""))

def parse_fields(text):
    """Split any 'KEY: value' formatted model response into a dict.
    Shared by every prompt in this module that uses that format, so
    there's exactly one place that knows how to read model output."""
    fields = {}
    for line in text.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields

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

def parse_entries(raw_output):
    """Split raw model output into ITEM/ANSWER/QUOTE blocks."""
    entries = []
    blocks = re.split(r'(?=ITEM:)', raw_output.strip())
    for block in blocks:
        if not block.strip():
            continue
        item_match = re.search(r'ITEM:\s*(.+)', block)
        answer_match = re.search(r'ANSWER:\s*(.+)', block)
        quote_match = re.search(r'QUOTE:\s*(.+)', block)
        entries.append({
            "item": item_match.group(1).strip() if item_match else None,
            "answer": answer_match.group(1).strip() if answer_match else None,
            "quote": quote_match.group(1).strip() if quote_match else None,
        })
    return entries

def normalize(text):
    """Collapse whitespace so trivial formatting diffs don't cause false FAILs."""
    return re.sub(r'\s+', ' ', text.strip())

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

def build_fact_history(result):
    """Turn ONE ReaderResult into a FactHistory. Deliberately thin for now -
    a real builder would merge ReaderResults across multiple runs/chunks for
    the same question, appending new claims/revisions onto an existing
    FactHistory instead of creating one from scratch each time."""
    try:
        from .models import FactHistory
    except ImportError:
        from models import FactHistory

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

def mock_chat(prompt):
    """Simulates what gemma3:4b *should* say if it reasons over the whole chunk."""
    return "" + prompt 

def check_for_revision(chunk, entry, chat_fn):
    """checks the model's initial output for revision"""
    prompt = REVISION_EXTRACT_PROMPT.format(
        chunk=chunk, category=entry['category'], item=entry['item'], answer=entry['answer'], quote=entry['quote'], status=entry['status']
    )
    return chat_fn(prompt)

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

def format_amount(value):
    """Render a computed float back as a display string, e.g. 3250.0 -> '$3,250.00'."""
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return str(value)

def classify_fact_type(value):
    """Guess whether a claimed value is boolean, numeric, or free text.
    Used only to label the ReaderResult - it never affects verification."""
    v = (value or "").strip().upper()
    if v in ("YES", "NO"):
        return "boolean"
    cleaned = v.replace("$", "").replace(",", "").strip()
    try:
        float(cleaned)
        return "numeric"
    except ValueError:
        return "text"

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

def _terminal_status(corrected_claim, evidence_repair):
    """Pick the right terminal status when nothing further (no numeric
    revision) changes the claim. A corrected value takes priority over a
    same-value quote repair, which takes priority over plain no-change -
    they're not mutually exclusive (a claim can be both quote-repaired AND
    later corrected), and the corrected_claim always wins."""
    if corrected_claim is not None:
        return "VERIFIED_CORRECTED"
    if evidence_repair is not None:
        return "VERIFIED_REPAIRED_QUOTE"
    return "VERIFIED_NO_CHANGE"

def process_entry(chunk, entry, chat_fn):
    """Run ONE checklist entry through the full loop and return a
    ReaderResult - the entire chain (initial claim, any quote repair, any
    support judgment/correction, any revision), not just a final value.

    This function does NOT decide what the long-term fact history looks
    like - it just reports what happened on this one pass. Building
    FactHistory out of one or more ReaderResults is a separate step.
    """
    question = entry["item"]
    fact_type = classify_fact_type(entry["answer"])
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

def is_valid_value(value, fact_type):
    """Check whether `value` is even the right *kind* of thing for
    `fact_type` ("boolean", "numeric", or "text"). Used to catch a model
    proposing a correction that doesn't match the fact's type at all -
    e.g. "corrected" a numeric fact to free text, or a YES/NO fact to a
    dollar amount. This never judges whether the value is factually
    correct, only whether it's a plausible value of that type."""
    v = (value or "").strip().upper()
    if not v:
        return False
    if fact_type == "boolean":
        return v in ("YES", "NO")
    if fact_type == "numeric":
        cleaned = v.replace("$", "").replace(",", "").strip()
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    return True  # "text" facts accept any non-empty value

def run_entry_loop(report, chunk, chat_fn):
    """Run every checklist entry through process_entry. Returns a list of
    ReaderResult objects - nothing is left hanging on a printed warning."""
    return [process_entry(chunk, entry, chat_fn) for entry in report]

def main():
    entries = parse_entries(RAW_OUTPUT)
    report = verify(entries, CHUNK)
    # report has all questions, there verification status, answer, and quotes.
    for r in report: #runs a check to revise any
        if r['status'] == "VERIFIED":
            print(check_for_revision(CHUNK, r, mock_chat))

if __name__ == "__main__":
    main()