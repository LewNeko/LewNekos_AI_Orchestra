from py_compile import main
import re

CHUNK = "The invoice was issued on March 3rd, 2024, to Acme Corp. Payment terms are net-30. The total amount due is $4,250.00. No late fee schedule is mentioned in this section. They felt bad about that total amount due and made it a thousand dollars less."

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
Does any OTHER sentence in the chunk revise this specific numeric fact? 
Do not calculate the corrected value yourself. 
Only extract the raw numbers. respond in exactly this format:

REVISED: YES or NO
REVISION_QUOTE: <exact sentence that revises it, or NOT FOUND>
ORIGINAL_VALUE: <the original number in the QUOTE, digits only>
DELTA_DIRECTION: INCREASE, DECREASE, DIVIDED, MULTIPLIED, or NONE
DELTA_VALUE: <the change amount, digits only>
"""
def compute_corrected_value(revision_result_text):
    """Pure Python math so the model isn't involved.
    AI is bad at math, so give it a calculator"""
    fields = {}
    for line in revision_result_text.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()

    if fields.get("REVISED") != "YES":
        return None #its not revised so theres nothing to compute
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

def mock_chat(prompt):
    # Simulates what gemma3:4b *should* say if it reasons over the whole chunk
    return "" + prompt 
#+ "\nREVISED: YES \nREVISION_QUOTE: They felt bad about that total amount due and made it a thousand dollars less. \nCORRECTED_ANSWER: $3,250.00"

#this function is from claudes 
#"Add and test a revision-check function against the stale amount entry""
def check_for_revision(chunk, entry, chat_fn):
    """chat_fn is passed in so this stays testable without a live model call."""
    prompt = REVISION_EXTRACT_PROMPT.format(
        chunk=chunk, item=entry['item'], answer=entry['answer'], quote=entry['quote'], status=entry['status']
    )
    return chat_fn(prompt)

def main():
    entries = parse_entries(RAW_OUTPUT)
    report = verify(entries, CHUNK)
    # report has all questions, there verification status, answer, and quotes.
    for r in report: #runs a check to revise any
        if r['status'] == "VERIFIED":
            print(check_for_revision(CHUNK, r, mock_chat))

if __name__ == "__main__":
    main()

    