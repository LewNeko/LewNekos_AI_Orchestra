from pathlib import Path

from The_Chunker import DocumentChunker


def main() -> None:
    source = Path(__file__).parent / "invoice.md"

    chunker = DocumentChunker(
        max_tokens=128,
    )

    chunks = chunker.chunk_document(source)

    print(f"Document: {source}")
    print(f"Chunks: {len(chunks)}")
    print()

    for chunk in chunks:
        print("=" * 80)
        print(chunk.id)
        print("-" * 80)

        print("TEXT:")
        print(chunk.text)

        print()
        print("CONTEXTUALIZED:")
        print(chunk.contextualized_text)

        print()
        print("METADATA:")
        print(chunk.metadata)

        print()


if __name__ == "__main__":
    main()