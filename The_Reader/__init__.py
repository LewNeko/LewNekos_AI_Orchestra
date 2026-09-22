"""
The_Reader
----------
Verification pipeline package.

Layout:
    models.py       typed domain vocabulary (FactClaim, Evidence, ReaderResult, ...)
    prompts.py      every prompt template, nothing else
    parsing.py      raw model text -> dicts; text normalization
    fact_types.py   boolean/numeric/text classification + formatting
    quote_checks.py "does this quote exist / support this claim"
    revisions.py    "does something else revise this claim"
    pipeline.py     orchestrates the above per checklist entry
    reporting.py    tree-printer for a list of ReaderResult objects
    store.py        SQLite persistence for ReaderResult objects
"""
