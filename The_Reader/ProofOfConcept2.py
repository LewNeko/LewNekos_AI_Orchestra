"""so i can use the models"""
import os
import sys
from backends import get_backend

"""from verify pipeline"""
from verify_pipeline import (
    check_for_revision,
    compute_corrected_value,
    parse_entries,
    verified_categorizer,
    verify,
)

CHUNK = """
The invoice was issued on March 3rd, 2024, to Acme Corp. Payment terms are net-30. The total amount due is $4,250.00. No late fee schedule is mentioned in this section. 
They felt bad about that total amount due and made it a thousand dollars less.
"""

CHECKLIST = [
    "Does this chunk state a specific due date for payment?",
    "Does this chunk mention a late fee or penalty amount?",
    "Does this chunk name the company being invoiced?",
    "What's the amount due?",
]
CHECK_PROMPT="""
You are verifying facts against a source text chunk. For each checklist item, respond in this exact format:
ITEM: <checklist item>
ANSWER: YES or NO or <number>
QUOTE: <exact sentence from the chunk that supports your answer, copied verbatim or NOT FOUND>

Do not paraphrase the quote. Do not answer YES if you cannot produce an exact quote.

CHUNK: {CHUNK}
CHECKLIST: {CHECKLIST} 
"""
# Pick the backend once, here. Order of precedence: CLI arg -> BACKEND env var -> default.
# Run e.g. `python ProofOfConcept.py claude` or `python ProofOfConcept.py ollama-qwen3-coder`
# See backends.py's BACKENDS dict for the full list of valid names.
BACKEND_NAME = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BACKEND", "ollama-qwen3:8b")
backend = get_backend(BACKEND_NAME)

def run_checklist(chunk, checklist):
    prompt = CHECK_PROMPT.format(
        CHUNK=chunk,
        CHECKLIST="\n".join(f"-{item}" for item in checklist)
    )
    reply = backend.chat([{"role": "user", "content": prompt}])
    return reply["content"]

def chat_fn(prompt):
    reply = backend.chat([{"role": "user", "content": prompt}])
    return reply["content"]

#uses check_for_revision and compute_corrected_value
def show_entry(report, REVISIONS, COMPUTATIONS):
    """prints the"""
    REVISIONS = []
    COMPUTATIONS = []
    for entry in report:
        print(f"""
        status: {entry['status']} 
        question: {entry['item']}
        answer: {entry['answer']}
        quote:  {entry['quote']}
        category: {entry['category']}""")
        if entry['category'] == "DETERMINISTIC":
            print("A different revision will be given for deterministic answers")
            print("----------------")
            continue
        if entry['status'] == "UNVERIFIED_QUOTE":
            print("Either or a warning or correction step will be taken for this")
            print("----------------")
            continue
        revision = check_for_revision(CHUNK, entry, chat_fn)
        REVISIONS.append(revision)
        compute = compute_corrected_value(revision, entry)
        COMPUTATIONS.append(compute)
        #print(f""" revised: {revision['REVISED']} \n revised quote: {revision['REVISION_QUOTE']} """) need to have a parser for revision before use
        print(revision)
        print(compute)
        print("----------------")
#Check the response 
def  main():
    ENTRIES = parse_entries(run_checklist(CHUNK, CHECKLIST)) #pure reponse list
    REPORT = verified_categorizer(verify(ENTRIES, CHUNK)) #reponse list either verify
    REVISIONS = []
    COMPUTATIONS = []
    show_entry(REPORT,REVISIONS,COMPUTATIONS)
            
    for r in REVISIONS:
        continue

if __name__ == "__main__":
    main()
