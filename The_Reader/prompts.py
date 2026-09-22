"""
prompts.py
----------
Every prompt template used anywhere in the verification pipeline, and
nothing else. No imports, no logic - just the strings that get
.format()-ed and sent to a model. Keeping these in one place means the
exact wording a model is asked to follow lives in exactly one spot.
"""

# First-pass prompt: turns a checklist into the model's initial claims
# about a chunk (used by ProofOfConcept.py's run_checklist()).
CHECK_PROMPT = """
You are verifying facts against a source text chunk. For each checklist item, respond in this exact format:
ITEM: <checklist item>
ANSWER: YES or NO or <number>
QUOTE: <exact sentence from the chunk that supports your answer, copied verbatim or NOT FOUND>

Do not paraphrase the quote. Do not answer YES if you cannot produce an exact quote.

CHUNK: {CHUNK}
CHECKLIST: {CHECKLIST} 
"""

# Retry prompt used ONLY when the exact quote failed verification.
# Deliberately narrow: it must NOT be allowed to change the answer,
# only find a better (exact) supporting sentence.
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

# Used ONLY when the quote is an exact match but we haven't checked whether
# it actually answers the specific question asked (e.g. "issued on" vs "due on").
# This prompt IS allowed to change the answer, since that's the whole point.
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

# Extraction prompt for the reviser model to avoid doing math (AI is bad at math)
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
