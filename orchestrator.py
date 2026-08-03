"""
orchestrator.py
----------------
The agent loop. This is the "local orchestration logic" -- it never
cares which backend is answering. It just: send messages -> get a
reply -> if the reply wants a tool, run the tool -> feed result back
-> repeat until the model gives a final answer.
"""

import json
from backends import get_backend
from tools import TOOL_SCHEMA, TOOL_FUNCTIONS

MAX_STEPS = 6  # safety cap so a confused model can't loop forever

SYSTEM_PROMPT = (
    "You are a helpful local assistant with access to tools for reading "
    "files and listing directories. Use tools when you need information "
    "you don't already have. Once you have enough information, give a "
    "clear final answer without calling more tools."
)


def run_tool_call(tool_call: dict, backend_name: str) -> dict:
    """Execute a tool call and package the result for the model."""
    if backend_name == "claude":
        name = tool_call["name"]
        args = tool_call.get("input", {})
        call_id = tool_call["id"]
    else:  # ollama / OpenAI-style
        name = tool_call["function"]["name"]
        args = json.loads(tool_call["function"]["arguments"])
        call_id = tool_call.get("id", name)

    fn = TOOL_FUNCTIONS.get(name)
    result = fn(**args) if fn else f"Unknown tool: {name}"

    return {"id": call_id, "name": name, "result": result}


def run(task: str, backend_name: str = "ollama") -> str:
    backend = get_backend(backend_name)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    for step in range(MAX_STEPS):
        reply = backend.chat(messages, tools=TOOL_SCHEMA)

        if reply["content"]:
            print(f"[{backend_name} | step {step}] {reply['content']}")

        if not reply["tool_calls"]:
            return reply["content"]  # done -- final answer

        # Model wants to use a tool. Run it, report the result back.
        messages.append({"role": "assistant", "content": reply["content"] or ""})
        for tc in reply["tool_calls"]:
            outcome = run_tool_call(tc, backend_name)
            print(f"  -> tool '{outcome['name']}' result: {outcome['result'][:200]}")
            messages.append({
                "role": "tool",
                "content": f"Tool '{outcome['name']}' returned:\n{outcome['result']}",
            })

    return "Stopped: reached max steps without a final answer."


if __name__ == "__main__":
    import sys

    backend_choice = sys.argv[1] if len(sys.argv) > 1 else "ollama"
    task_input = " ".join(sys.argv[2:]) or "List the files in the current directory."

    print(f"Running with backend: {backend_choice}\nTask: {task_input}\n")
    final = run(task_input, backend_name=backend_choice)
    print(f"\nFinal answer:\n{final}")
