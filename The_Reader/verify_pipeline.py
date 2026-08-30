""" 
verify_pipeline.py
----------------
used for testing the revision-check 
function against a stale amount entry. """
from py_compile import(
    main,
) 
import re

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
FACT_TYPE: {fact_type}

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

REVISION_RELEVANCE_PROMPT = """Decide whether a candidate revision changes
the SAME numeric fact as the original fact. Answer NO when it changes a
different subject, even if both statements contain numbers.

QUESTION: {item}
ORIGINAL ANSWER: {answer}
ORIGINAL QUOTE: {quote}
CANDIDATE REVISION: {revision_quote}

Respond in exactly this format:
RELEVANT: YES or NO
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


def canonical_item(item):
    """Normalize model-copied checklist text before FACT_TYPE lookup."""
    if not item:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", normalize(item).casefold()).strip()

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

def verified_categorizer(entries, fact_types=None):
    """Attach a fact type defined by the checklist, never by model output."""
    normalized_fact_types = {
        canonical_item(item): fact_type
        for item, fact_type in (fact_types or {}).items()
    }
    report = []
    for e in entries:
        fact_type = normalized_fact_types.get(canonical_item(e["item"]), "unknown")
        report.append({**e, "fact_type": fact_type})
    return report

def mock_chat(prompt):
    """Simulates what gemma3:4b *should* say if it reasons over the whole chunk."""
    return "" + prompt 

def check_for_revision(chunk, entry, chat_fn):
    """checks the model's initial output for revision"""
    prompt = REVISION_EXTRACT_PROMPT.format(
        chunk=chunk, fact_type=entry["fact_type"], item=entry["item"], answer=entry["answer"], quote=entry["quote"], status=entry["status"]
    )
    return chat_fn(prompt)


def check_revision_relevance(entry, revision_quote, chat_fn):
    """Ask whether a candidate revision modifies this entry's numeric fact."""
    prompt = REVISION_RELEVANCE_PROMPT.format(
        item=entry["item"],
        answer=entry["answer"],
        quote=entry["quote"],
        revision_quote=revision_quote,
    )
    return parse_fields(chat_fn(prompt)).get("RELEVANT", "").strip().upper()


def original_value_matches_entry(entry, original_value):
    """Require revision arithmetic to start from this entry's own evidence."""
    try:
        expected = float(original_value.replace("$", "").replace(",", ""))
    except (AttributeError, ValueError):
        return False

    values = re.findall(r"\$?\d[\d,]*(?:\.\d+)?", f"{entry['answer']} {entry['quote']}")
    for value in values:
        try:
            if float(value.replace("$", "").replace(",", "")) == expected:
                return True
        except ValueError:
            continue
    return False

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

def process_entry(chunk, entry, chat_fn):
    """Run ONE checklist entry through the full loop until it reaches a
    terminal status. This is the piece that used to just print a warning
    and move on - now every entry ends in exactly one of:
        VERIFIED_NO_CHANGE, VERIFIED_REPAIRED_QUOTE, VERIFIED_CORRECTED,
        VERIFIED_REVISED, NEEDS_REVIEW
    """
    record = {
        "item": entry["item"],
        "initial_answer": entry["answer"],
        "initial_quote": entry["quote"],
        "fact_type": entry.get("fact_type", "unknown"),
    }
    current = dict(entry)  # working copy we're allowed to mutate

    def terminal(status, answer=None, quote=None, **extra):
        record["final_status"] = status
        record["final_answer"] = answer if answer is not None else current["answer"]
        record["quote"] = quote if quote is not None else current["quote"]
        record.update(extra)
        return record

    if current["status"] == "MISSING_FIELDS":
        return terminal("NEEDS_REVIEW",
                         reason="One or more of item/answer/quote were missing from the model output.")

    # Step 1: repair a bad quote BEFORE trusting anything else about this entry.
    quote_was_repaired = False
    if current["status"] == "UNVERIFIED_QUOTE":
        repaired = repair_quote(chunk, current, chat_fn)
        candidate = (repaired.get("quote") or "").strip()
        if candidate and candidate.upper() != "NOT FOUND" and normalize(candidate) in normalize(chunk):
            current["quote"] = candidate
            current["status"] = "VERIFIED"
            quote_was_repaired = True
        else:
            return terminal("NEEDS_REVIEW",
                             reason="Quote could not be verified even after a repair attempt.")

    # OK_NOT_FOUND ("the model correctly said no evidence exists") is already terminal.
    if current["status"] == "OK_NOT_FOUND":
        return terminal("VERIFIED_NO_CHANGE")

    # Step 2: the quote text exists verbatim - but does it actually support
    # THIS question and THIS answer, or just the general topic?
    support = check_answer_support(chunk, current, chat_fn)
    supported_answer = (support.get("answer") or "").strip()
    supported_quote = (support.get("quote") or "").strip()

    if supported_answer and supported_answer.upper() != current["answer"].strip().upper():
        # The model is walking back its own answer.
        if not supported_quote or supported_quote.upper() == "NOT FOUND" \
                or normalize(supported_quote) not in normalize(chunk):
            # Corrected to "no support in the text" - that's a clean, terminal result.
            return terminal("VERIFIED_CORRECTED",
                             answer=supported_answer, quote="NOT FOUND",
                             reason="Original quote did not support the original answer; answer corrected.")
        else:
            # Corrected AND backed by a new exact quote - keep going with the corrected fact.
            current["answer"] = supported_answer
            current["quote"] = supported_quote

    # Only numeric facts currently have a revision handler. Existence, date,
    # and name facts still reach a terminal result after quote/support checks.
    if current.get("fact_type") != "numeric":
        status = "VERIFIED_REPAIRED_QUOTE" if quote_was_repaired else "VERIFIED_NO_CHANGE"
        return terminal(status)

    # Step 3: does some OTHER, later statement revise this numeric fact?
    revision_text = check_for_revision(chunk, current, chat_fn)
    revision_fields = parse_fields(revision_text)

    if revision_fields.get("REVISED") != "YES":
        status = "VERIFIED_REPAIRED_QUOTE" if quote_was_repaired else "VERIFIED_NO_CHANGE"
        return terminal(status)

    revision_quote = revision_fields.get("REVISION_QUOTE", "")
    if normalize(revision_quote) not in normalize(chunk):
        return terminal("NEEDS_REVIEW", reason="Revision quote could not be verified against the source.")

    if not original_value_matches_entry(current, revision_fields.get("ORIGINAL_VALUE")):
        return terminal("NEEDS_REVIEW", reason="Revision original value did not match this entry's evidence.")

    relevance = check_revision_relevance(current, revision_quote, chat_fn)
    if relevance == "NO":
        return terminal("VERIFIED_NO_CHANGE", reason="Candidate revision concerns a different fact.")
    if relevance != "YES":
        return terminal("NEEDS_REVIEW", reason="Could not determine whether the revision applies to this fact.")

    computed = compute_corrected_value(revision_text, current)

    if computed == "PARSE_ERROR":
        return terminal("NEEDS_REVIEW", reason="Could not parse the revision-check response.")

    if computed is not None:
        final_answer = format_amount(computed) if isinstance(computed, float) else computed
        return terminal("VERIFIED_REVISED",
                         answer=final_answer,
                         revision_quote=revision_quote,
                         operation=revision_fields.get("DELTA_DIRECTION"),
                         delta=revision_fields.get("DELTA_VALUE"))

    return terminal("NEEDS_REVIEW", reason="Revision was claimed but no valid arithmetic operation was supplied.")

def run_entry_loop(report, chunk, chat_fn):
    """Run every checklist entry through process_entry so nothing is left
    hanging on a printed warning - each item comes back with a terminal status."""
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

    
