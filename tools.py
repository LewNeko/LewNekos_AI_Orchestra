"""
tools.py
--------
Define what the agent is allowed to DO. Start small -- one or two
safe, read-only tools -- and expand once the loop is solid.
"""

import os

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
]


def list_directory(path: str) -> str:
    try:
        entries = os.listdir(path)
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:
        return f"Error: {e}"


def read_file(path: str) -> str:
    try:
        with open(path, "r", errors="replace") as f:
            content = f.read()
        # Keep tool output bounded so it doesn't blow up context.
        return content[:3000] + ("\n...(truncated)" if len(content) > 3000 else "")
    except Exception as e:
        return f"Error: {e}"


TOOL_FUNCTIONS = {
    "list_directory": list_directory,
    "read_file": read_file,
}
