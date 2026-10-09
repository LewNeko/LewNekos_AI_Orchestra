"""
executor.py
-----------
Runs normalized tool calls. Knows nothing about any model provider;
backend-specific parsing must already have happened.
"""

import json

from tools import TOOL_FUNCTIONS


def run_tool_call(tool_call: dict) -> dict:
    """
    Execute a normalized tool call: {"id": str, "name": str, "input": dict}.

    Returns {"id": ..., "name": ..., "result": str}. Errors are returned
    as result text (never raised) so the model can treat them as information.
    """
    name = tool_call["name"]
    args = tool_call.get("input", {})
    call_id = tool_call.get("id", name)

    fn = TOOL_FUNCTIONS.get(name)

    if fn is None:
        result = f"Unknown tool: {name}"
    else:
        try:
            result = fn(**args)
        except Exception as exc:
            result = f"Tool error: {type(exc).__name__}: {exc}"

    return {"id": call_id, "name": name, "result": str(result)}


def tool_call_signature(tool_call: dict) -> str:
    """
    Stable string for a normalized tool call, so read_file("a.py") issued
    on two different steps is recognised as the same action.
    """
    name = tool_call["name"]
    args = tool_call.get("input", {})
    return f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
