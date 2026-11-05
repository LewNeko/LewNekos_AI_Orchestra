# The_Chunker Skill
(note that this may have relations with the Web_Scraper later on)

## Overview
`The_Chunker` is the document ingestion and chunking boundary for the Orchestra. It bridges the gap between raw, unstructured document files and the structures `Chunk` objects consumed by the rest of the system. It leverages the `docling` library for structural parsing and hybrid chunking.

## Core Functionality
- **Document conversion**: Uses `DocumentConverter` from docling to parse various document formats into a structures `docling.document` object.
- **Hybrid Chunking**: implements a `HybridChunker` which combines content-aware chunking with token-based constraints.
- **Contextualization**: For each chunk, it generates a `contextualizaed_text~ field, ensuring that the model understands the chunk's position and relationship within the larger document structure.
- **Stable Representaation**: Converts the raw data from `docling` into a standardized, frozen `Chunk` dataclass containing: 
  - `id`: A unique, sequential identifier (e.g., `chunk_0001`).
  - `text`: The raw text content of the chunk.
  - `contextualized_text`: The text enhanced with contextual information.
  - `metadata`: A comprehensive dictionary containing structural metadata from the parser.

## Technical Details
- **Dependencies**: Relies on `docling`, `docling-core`, and `transformers`.
- **Tokenizer**: Defaults to `sentence-transformers/all-MiniLM-L6-v2` for consistent token limits
- **Token Limit**: Defaults to `256` tokens per chunk for optimized context management.

## Usage
The `DocumentChunker` provides a high-level `chunk_document` method that accepts a file path and returns a list of processed `Chunk` objects, ready for consumption by `The_Reader`,