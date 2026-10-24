"""Filesystem tools exposed to the agent."""

from pathlib import Path

from .constants import MAX_READ_CHARS


def list_directory(path: str) -> str:
    """List the immediate contents of a directory."""
    try:
        entries = [entry.name for entry in Path(path).iterdir()]
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as error:  # noqa: BLE001 - tool errors are returned for model recovery
        return f"Error: {error}"


def read_file(path: str) -> str:
    """Read a text file, returning a bounded preview for the model context."""
    try:
        content = Path(path).read_text(errors="replace")
        if len(content) > MAX_READ_CHARS:
            return content[:MAX_READ_CHARS] + "\n...(truncated)"
        return content
    except Exception as error:  # noqa: BLE001 - tool errors are returned for model recovery
        return f"Error: {error}"


def write_file(path: str, content: str) -> str:
    """Write UTF-8 text, creating missing parent directories when needed."""
    try:
        destination = Path(path).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        return (
            f"Successfully wrote to {path}\n"
            f"Absolute path: {destination}\n"
            f"File size: {destination.stat().st_size} bytes"
        )
    except Exception as error:  # noqa: BLE001 - tool errors are returned for model recovery
        return f"Error writing file: {error}"
