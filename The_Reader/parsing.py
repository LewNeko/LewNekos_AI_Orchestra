"""
parsing.py
----------
Turns raw model text into plain dicts, and normalizes text for comparison.
Nothing here knows about FactClaim/Evidence/ReaderResult - this module is
purely about reading model output and comparing strings, not about the
domain vocabulary those strings eventually become.
"""
import re


def normalize(text):
    """Collapse whitespace so trivial formatting diffs don't cause false FAILs."""
    return re.sub(r'\s+', ' ', text.strip())


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


#(function) def parse_entries(raw_output: Any) -> list
def parse_entries(raw_output):
    """Split raw model output into ITEM/ANSWER/QUOTE blocks."""
    entries = []
    blocks = re.split(r'(?=ITEM:)', raw_output.strip())
    for block in blocks:
        if not block.strip():
            #i noticed the first loop makes the block variable contain ""
            #and this catches it and runs the next loop which has actual data.
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
