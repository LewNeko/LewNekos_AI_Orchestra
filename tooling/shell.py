"""
shell.py
---
Command-line and search tools exposed to the agent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from .constants import MAX_RUN_CHARS

DEFAULT_TIMEOUT_SECONDS = 120 #I want to make it so the model can adjust these
MAX_COMMAND_CHARS = 4_000
MAX_SEARCH_RESULTS = 400

def run_command(command: str, cwd: str | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """
    Run a shell command and return its bounded stdout + stderr + exit code.
    This is the general-purpose command-line ability: 
    anything you can do in a terminal 
    (git, make, node, ffmpeg, etc.) can be driven through here. 
    Failures are returned as text 
    so the model can read the error and recover.
    """

    command = (command or "").strip()
    if not command:
        return "Error: run_command requires a non-empty command."
    if len(command) > MAX_COMMAND_CHARS:
        return f"Error: command exceeds maximum length of {MAX_COMMAND_CHARS} characters."
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd or None,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        if len(output) > MAX_RUN_CHARS:
            output = output[:MAX_RUN_CHARS] + "\n... (truncated)"
        return (
            f"$ {command}\n"
            f"Exit Code: {result.returncode}\n\n"
            f"Output:\n{output or '(no output)'}\n"
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error: {e}"

_NOISE_DIRS =  {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea",
}

def _walk_files(root: Path) -> list[Path]:
    """
    Collect files under root, skipping heavy/hidden noise directories.
    """
    found: list[Path] = []
    try:
        for entry in root.rglob("*"):
            if not entry.is_file():
                continue
            if _NOISE_DIRS & set(entry.parts):
                continue
            found.append(entry)
    except Exception: # noqa: BLE001 - unreadable dirs are skipped, not fatal
        return []
    return found

def glob_files(pattern: str, path: str = ".") -> str:
    """
    Find files matching a glob pattern (e.g. '**/*.py', '*.md').
    """
    root = Path(path)
    if not root.exists():
        return f"Error: path not found: {path}"

    try:
        files = _walk_files(root)
        match_pattern = pattern[3:] if pattern.startswith("**/") else pattern
        selected = sorted(m for m in files if m.match(match_pattern))
    except Exception as error: #noqa: BLE001 - unreadable dirs are skipped, not fatal
        return f"Error: {error}"

    if not selected:
        return f"No files found matching pattern: {pattern!r} under {path}"
    lines = [str(m) for m in selected[:MAX_SEARCH_RESULTS]]
    footer = (
        f"\n...({len(selected) - MAX_SEARCH_RESULTS} more not shown)"
        if len(selected) > MAX_SEARCH_RESULTS else ""
    )
    return "\n".join(lines) + footer

def grep_files(text: str, path: str = ".", glob: str | None = None, max_results: int = MAX_SEARCH_RESULTS) -> str:
    """
    Search file contents for a substring (case-insensitive).
    ``glob`` optionally restricts which files are searched (e.g. "*.py").
    Returns up to ``max_results`` matching lines as ``path:line_number: line``.
    """
    if not text:
        return "Error: grep_files requires a search string."
    root = Path(path)
    if not root.exists():
        return f"Error: path not found: {path}"

    needle = text.lower()
    limit = max(1, min(max_results, MAX_SEARCH_RESULTS))
    matches: list[str] = []
    files = sorted(_walk_files(root))

    for file in files:
        if glob and not file.match(glob):
            continue
        try:
            content = file.read_text(errors="replace")
        except (OSError, UnicodeDecodeError): 
            continue
        if needle not in content.lower():
            continue
        for number, line in enumerate(content.splitlines(), start=1):
            if needle in line.lower():
                matches.append(f"{file}:{number}: {line.rstrip()}")
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break

    if not matches:
        return f"No matches found for text: {text!r} under {path}"
    footer = (
        f"\n...(showing first {limit} matches out of {len(matches)})"
        if len(matches) >= limit else ""
    )
    return "\n".join(matches) + footer