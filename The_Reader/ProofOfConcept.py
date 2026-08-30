"""
Proof of Concept for using the verification pipeline
"""
#usage: python -m The_Reader.ProofOfConcept ollama
#command should be run from the root of the repo, not from The_Reader folder.
from pathlib import Path
import sys
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# noqa: E402 is a ruff directive to ignore that the import 
# is not at the top of the file. 
# This is necessary because we need to modify 
# sys.path before importing. other backends.py import breaks stuff
from .verify_pipeline import ( # noqa: E402
    parse_entries,
    run_entry_loop,
    verified_categorizer,
    verify,
)
from backends import get_backend # noqa: E402


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

# This routing belongs to the checklist definition, not to the model's answer.
# A wrong YES/NO from the model must not decide which verifier handles it.
FACT_TYPES = {
    "Does this chunk state a specific due date for payment?": "existence",
    "Does this chunk mention a late fee or penalty amount?": "existence",
    "Does this chunk name the company being invoiced?": "name",
    "What's the amount due?": "numeric",
}
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
BACKEND_NAME = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BACKEND", "ollama-qwen3:4b")
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

def print_final_report(records):
    """Every record here is terminal - nothing gets silently dropped anymore."""
    for r in records:
        print(f"""
        item: {r['item']}
        final_status: {r['final_status']}
        final_answer: {r['final_answer']}
        quote: {r.get('quote')}
        (initial_answer was: {r['initial_answer']})""")
        if r.get("revision_quote"):
            print(f"        revision_quote: {r['revision_quote']}")
            print(f"        operation: {r.get('operation')}  delta: {r.get('delta')}")
        if r.get("reason"):
            print(f"        reason: {r['reason']}")
        print("----------------")

#Check the response
def main():
    ENTRIES = parse_entries(run_checklist(CHUNK, CHECKLIST))  # pure response list
    REPORT = verified_categorizer(verify(ENTRIES, CHUNK), FACT_TYPES)
    FINAL = run_entry_loop(REPORT, CHUNK, chat_fn)             # closes the loop: repair -> support check -> revision check
    print_final_report(FINAL)

if __name__ == "__main__":
    main()
