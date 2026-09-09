from chunker import chunk_document

doc = '''# Invoice Record

## Billing Details

The invoice was issued on March 3rd, 2024, to Acme Corp. Payment terms are net-30.

The total amount due is $4,250.00. No late fee schedule is mentioned in this section.

## Adjustments

They felt bad about that total amount due and made it a thousand dollars less.

This adjustment was approved by the billing supervisor on March 10th.
'''

chunks = chunk_document(doc, max_chunk_chars=500)
for c in chunks:
    print(f"[{c['id']}] path={c['header_path']!r} offset=({c['char_start']},{c['char_end']})")
    print(f"    text: {c['text']!r}")
    print("")
