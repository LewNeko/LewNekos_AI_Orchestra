"""so i can use the models"""
from ollama import chat

"""from verify pipeline"""
from verify_pipeline import (
    check_for_revision,
    compute_corrected_value,
    parse_entries,
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
ANSWER: YES or NO
QUOTE: <exact sentence from the chunk that supports your answer, copied verbatim or NOT FOUND>

Do not paraphrase the quote. Do not answer YES if you cannot produce an exact quote.

CHUNK: {CHUNK}
CHECKLIST: {CHECKLIST} 
"""
MODEL = "gemma3:4b"

def run_checklist(chunk, checklist):
    prompt = CHECK_PROMPT.format(
        CHUNK=chunk,
        CHECKLIST="\n".join(f"-{item}" for item in checklist)
    )
    response = chat(
        MODEL,
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )
    return response.message.content

def chat_fn (prompt):
    response = chat(
        MODEL,
        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ]
    )
    return response.message.content

#Check the response 
ENTRIES = parse_entries(run_checklist(CHUNK, CHECKLIST))
REPORT = verify(ENTRIES, CHUNK)
REVISIONS = []
COMPUTATIONS = []
for entry in REPORT:
    if entry['status'] == "VERIFIED":
        print(f"[{entry['status']}] \n{entry['item']}")
        print(f"    answer: {entry['answer']}")
        print(f"    quote:  {entry['quote']}")
        print("--revisions below--")
        revision = check_for_revision(CHUNK, entry, chat_fn)
        REVISIONS.append(revision)
        compute = compute_corrected_value(revision, entry) # r is an entry in
        COMPUTATIONS.append(compute)
        print(revision)
        print("--computes:--")
        print(compute)
        print("--end of loop--")
for r in REVISIONS:
    continue
    