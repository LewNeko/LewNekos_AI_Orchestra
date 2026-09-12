from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker

from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)

from transformers import AutoTokenizer


@dataclass(frozen=True)
class Chunk:
    """
    Stable Reader-facing representation of a document chunk.
    """

    id: str
    text: str
    contextualized_text: str
    metadata: dict[str, Any]


class DocumentChunker:
    """
    Document ingestion and chunking boundary for the Orchestra.

    Docling handles document parsing and structural understanding.

    This class converts Docling's output into the stable chunk
    representation consumed by the rest of the Orchestra.
    """

    def __init__(
        self,
        max_tokens: int = 256,
        tokenizer_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.converter = DocumentConverter()

        tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained(
                tokenizer_model
            ),
            max_tokens=max_tokens,
        )

        self.chunker = HybridChunker(
            tokenizer=tokenizer,
            merge_peers=True,
        )

    def chunk_document(
        self,
        source: str | Path,
    ) -> list[Chunk]:
        """
        Parse and chunk a single local document.
        """

        source = Path(source)

        if not source.exists():
            raise FileNotFoundError(
                f"Document does not exist: {source}"
            )

        if not source.is_file():
            raise ValueError(
                f"Source is not a file: {source}"
            )

        result = self.converter.convert(source)
        document = result.document

        chunks: list[Chunk] = []

        for index, docling_chunk in enumerate(
            self.chunker.chunk(dl_doc=document)
        ):
            contextualized_text = self.chunker.contextualize(
                chunk=docling_chunk
            )

            metadata = docling_chunk.meta.model_dump(
                mode="json"
            )

            chunks.append(
                Chunk(
                    id=f"chunk_{index:04d}",
                    text=docling_chunk.text,
                    contextualized_text=contextualized_text,
                    metadata=metadata,
                )
            )

        return chunks

    @staticmethod
    def chunk_to_dict(
        chunk: Chunk,
    ) -> dict[str, Any]:
        return asdict(chunk)