import re

def chunk_document(text, max_chunk_chars=500):
    """Split plain text / markdown into bounded, addressable chunks.

    Rules (deliberately simple):
    - Headers (#, ##, ### ...) establish a 'path' that travels with every
      chunk under them, e.g. "Introduction > Background".
    - Paragraphs are separated by blank lines and are NEVER split mid-paragraph.
    - Paragraphs are packed into a chunk until adding the next one would
      exceed max_chunk_chars, then a new chunk starts.
    - Every chunk carries an id, its header path, and its char offsets in
      the ORIGINAL document -- this is the provenance Auditor will need later.
    """
    lines = text.split("\n")
    header_stack = []  # list of (level, title)
    blocks = []  # (header_path, paragraph_text, start_offset, end_offset)

    offset = 0
    current_para_lines = []
    para_start_offset = None

    def flush_paragraph():
        nonlocal current_para_lines, para_start_offset, offset
        if current_para_lines:
            para_text = "\n".join(current_para_lines).strip()
            if para_text:
                path = " > ".join(t for _, t in header_stack)
                blocks.append((path, para_text, para_start_offset, offset))
        current_para_lines = []
        para_start_offset = None

    for line in lines:
        line_len = len(line) + 1  # +1 for the newline we split on
        header_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if header_match:
            flush_paragraph()
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            header_stack = [h for h in header_stack if h[0] < level]
            header_stack.append((level, title))
        elif line.strip() == "":
            flush_paragraph()
        else:
            if para_start_offset is None:
                para_start_offset = offset
            current_para_lines.append(line)
        offset += line_len
    flush_paragraph()

    # Pack paragraphs into size-bounded chunks, never splitting a paragraph.
    chunks = []
    current_paras = []
    current_path = None
    chunk_start = None

    def flush_chunk():
        nonlocal current_paras, current_path, chunk_start
        if current_paras:
            text_joined = "\n\n".join(p[1] for p in current_paras)
            chunks.append({
                "id": f"chunk_{len(chunks):04d}",
                "header_path": current_path,
                "text": text_joined,
                "char_start": chunk_start,
                "char_end": current_paras[-1][3],
            })
        current_paras = []
        chunk_start = None

    for block in blocks:
        path, para_text, start, end = block
        would_be_size = sum(len(p[1]) for p in current_paras) + len(para_text)
        path_changed = current_path is not None and path != current_path
        if current_paras and (would_be_size > max_chunk_chars or path_changed):
            flush_chunk()
        if not current_paras:
            chunk_start = start
            current_path = path
        current_paras.append(block)
    flush_chunk()

    return chunks