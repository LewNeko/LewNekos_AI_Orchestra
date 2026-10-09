from __future__ import annotations

import io
import re

from ..errors import ExtractionError
from ..models import ContentBlock


def parse_pdf(body: bytes, url: str) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ExtractionError("PDF support needs: pip install pypdf") from e
    reader = PdfReader(io.BytesIO(body))
    info = reader.metadata
    title = (info.title if info and info.title else None)
    blocks, md_parts, pos = [], [], 0
    for n, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        md_parts.append(f"## Page {n}\n\n{text}")
        for para in re.split(r"\n\s*\n", text):
            para = " ".join(para.split())
            if para:
                blocks.append(ContentBlock(text=para, tag="p", selector=f"page={n}", source_url=url,
                                           position=pos, heading_path=[f"Page {n}"]))
                pos += 1
    title = title or (blocks[0].text[:120] if blocks else None)
    return {"title": title, "description": None, "language": None, "markdown": "\n\n".join(md_parts),
            "html": None, "links": [], "images": [], "blocks": blocks, "tables": [],
            "metadata": {"title": title, "pages": len(reader.pages)}}
