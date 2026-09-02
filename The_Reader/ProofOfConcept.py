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
    build_fact_history,
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

def print_final_report(results):
    """Print each ReaderResult as the claim/evidence/revision tree, not a
    flat answer field - so the chain that produced current_value is visible."""
    for r in results:
        print(f"""
Fact
|
+-- Question
|     {r.question}  ({r.fact_type})
|
+-- Initial claim
|     Value: {r.initial_claim.value}
|     Evidence: "{r.initial_claim.evidence.quote}\"""")
        if r.evidence_repair is not None:
            print(f"""|
+-- Evidence repair
|     New evidence: "{r.evidence_repair.quote}\"""")
        if r.support_judgment is not None:
            print(f"""|
+-- Support judgment
|     {r.support_judgment.verdict}""")
        if r.corrected_claim is not None:
            print(f"""|
+-- Corrected claim
|     Value: {r.corrected_claim.value}
|     Evidence: "{r.corrected_claim.evidence.quote}\"""")
        if r.revision is not None:
            print(f"""|
+-- Revision
|     {r.revision.operation} {r.revision.amount}
|     Evidence: "{r.revision.evidence.quote}\"""")
        print(f"""|
+-- Status: {r.status}""")
        if r.reason:
            print(f"|     reason: {r.reason}")
        print(f"""|
`-- Current value
      {r.current_value}
""")
        print("----------------")

#Check the response
def main():
    ENTRIES = parse_entries(run_checklist(CHUNK, CHECKLIST))  # pure response list
    REPORT = verified_categorizer(verify(ENTRIES, CHUNK))     # response list, quote-verified + categorized
    RESULTS = run_entry_loop(REPORT, CHUNK, chat_fn)           # closes the loop: repair -> support check -> revision check
    print_final_report(RESULTS)

    # FactHistory is the durable, cross-run record - built here per-question
    # from this single pass for now (see build_fact_history's docstring).
    HISTORIES = [build_fact_history(r) for r in RESULTS]
    return RESULTS, HISTORIES

if __name__ == "__main__":
    main()
