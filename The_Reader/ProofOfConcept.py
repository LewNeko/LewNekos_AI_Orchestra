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
from .pipeline import build_fact_history, run_entry_loop # noqa: E402
from .parsing import parse_entries # noqa: E402
from .prompts import CHECK_PROMPT # noqa: E402
from .quote_checks import verified_categorizer, verify # noqa: E402
from .reporting import print_final_report # noqa: E402
from .store import ReaderResultStore # noqa: E402
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
    reply = backend.chat([{"role": "user", "content": prompt}], [])
    return reply["content"]

def chat_fn(prompt):
    reply = backend.chat([{"role": "user", "content": prompt}], [])
    return reply["content"]

#Check the response
def main():

    ENTRIES = parse_entries(
        run_checklist(CHUNK, CHECKLIST)
        )  # pure response list
    
    REPORT = verified_categorizer(
        verify(ENTRIES, CHUNK)
        )     # response list, quote-verified + categorized
    
    RESULTS = run_entry_loop(REPORT, CHUNK, chat_fn)# closes the loop: repair -> support check -> revision check
    print_final_report(RESULTS)

    # FactHistory is the durable, cross-run record - built here per-question
    # from this single pass for now (see build_fact_history's docstring).
    HISTORIES = [build_fact_history(r) for r in RESULTS]

    # Persist the complete ReaderResult chain (source of truth) so a vector
    # DB or anything else can be derived from these rows later, rather than
    # becoming another source of truth itself.
    store = ReaderResultStore()
    run_id = store.start_run(
        document_id="proof_of_concept",
        metadata={"backend": BACKEND_NAME},
    )
    store.save_results(RESULTS, run_id=run_id, document_id="proof_of_concept")
    store.close()

    return RESULTS, HISTORIES

if __name__ == "__main__":
    main()
