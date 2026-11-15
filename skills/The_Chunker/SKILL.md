# The_Chunker Skill
> Note: expected to have relations with `Web_Scraper` later on. It'll be the ingestion source for HTML/web documents, and the chunker will own the bounded-structure boundary the rest of the pipeline consumes. 

## Overview
`The_Chunker` is the document ingestion and chunking boundary for the Orchestra. It bridges the gap between raw, unstructured document files and the structures `Chunk` objects consumed by the rest of the system. It leverages the `docling` library for structural parsing and hybrid chunking for bounded segments.

## Source of truth
- **File**: `The_Chunker/chunker.py` &rightarrow; `DocumentChunker` and the frozen `Chunk` dataclass.
- **Demo**: `The_Chunker/example.py`.

## Core Functionality (verified against code)
- **Document conversion**: `docling.document_converter.DocumentConverter` parses a local file into a `docling` document.
- **Hybrid Chunking**: `docling.chunking.HybridChunker` with `merge_peers=True`, wrapped by a `HuggingFaceTokenizer`.
- **Contextualization**: `HybridChunker.contextualize(chunk=docling_chunk)` produces a `contextualized_text` string for each chunk.
- **Stable Representaation**: `The_Chunker.Chunk` (frozen dataclass) - fields:
 
  - `id: str`: sequential, zero-padded, **starting at `chunk_0000`**(`f"chunk_{index:04d}"`).
  - `text: str`: The raw text content of the chunk.
  - `contextualized_text: str`: The text enhanced with contextual information.
  - `metadata: dict[str, Any]`: JSON-safe dump of the docling chunk's `.meta`.
- **Static helper**: `DocumentChunker.chunk_to_dict(chunk)` &rightarrow; `dataclasses.asdict`.
- **Validation**: raises `FileNotFoundError` for a missing path and `ValueError` if the path is not a file, before doing any work.

## Technical Details
- **Dependencies**: (in `requirements.txt`) Relies on `docling`, `docling-core`, `huggingface_hub`, `tokenizers` and `transformers`.
- **Tokenizer**: Defaults to `sentence-transformers/all-MiniLM-L6-v2` for consistent token limits
- **Token Limit**: Defaults to `256` tokens per chunk for optimized context management.

## Usage
```python
from The_Chunker.chunker import DocumentChunker

chunker = DocumentChunker()                               # defaults
chunks = chunker.chunk_document("path/to/your/file.txt")  #list[Chunk]
# chunks[0].id      -> "chunk_0000"
# chunks[0].text    -> raw text
# chunks[0].contextualized_text -> contextualized text
```

## What this does NOT do
- No LLM call in the chunking path. Splitting is deterministic and structural.
- No cross-document merge. One call = one input file.
- No deduplication or normalization across chunks; that is the Reader/Auditor's territory.