"""
tools.py
--------
Define what the agent is allowed to DO. Start small -- one or two
safe, read-only tools -- and expand once the loop is solid.
"""

import os
import pathlib
import subprocess
import sys

# Anchor the skills folder to this file, not the current working directory.
SKILLS_DIR = pathlib.Path(__file__).resolve().parent / "skills"

# Keep tool output bounded so it doesn't blow up context.
MAX_READ_CHARS = 12000
MAX_RUN_CHARS = 6000

# OpenAI-style tool schema. Both backends understand this shape
# (ClaudeBackend converts it internally).
TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a given directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Run a Python script and return its stdout and stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to python script."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "skill_index",
            "description": (
                "List the available skills: the path, name and description of every "
                "SKILL.md in the skills/ folder. Call this first to find the skill that "
                "matches the task, then use read_file on its path before writing code."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def list_directory(path: str) -> str:
    try:
        entries = os.listdir(path)
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:  # return errors as text so the model can recover
        return f"Error: {e}"


def read_file(path: str) -> str:
    try:
        with open(path, "r", errors="replace") as f:
            content = f.read()
        if len(content) > MAX_READ_CHARS:
            return content[:MAX_READ_CHARS] + "\n...(truncated)"
        return content
    except Exception as e:
        return f"Error: {e}"


def skill_index() -> str:
    if not SKILLS_DIR.is_dir():
        return f"Error: skills folder not found at {SKILLS_DIR}"
    lines = []
    for f in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        text = f.read_text(errors="replace")
        # Simple frontmatter parse: text between the first two '---' lines.
        parts = text.split("---", 2)
        head = parts[1].strip() if text.startswith("---") and len(parts) == 3 else text[:200].strip()
        lines.append(f"- {f}: {head}")
    return "\n".join(lines) if lines else "(no skills found)"


def run_python(path: str) -> str:
    """Run a Python script and return its stdout and stderr."""
    try:
        r = subprocess.run(
            [sys.executable, path], capture_output=True, text=True, timeout=120
        )
        return (r.stdout + r.stderr)[-MAX_RUN_CHARS:] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: script timed out after 120 seconds."
    except Exception as e:
        return f"Error: {e}"


TOOL_FUNCTIONS = {
    "list_directory": list_directory,
    "read_file": read_file,
    "skill_index": skill_index,
    "run_python": run_python,
}