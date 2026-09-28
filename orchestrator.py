"""
orchestrator.py
----------------

The agent loop.

The orchestrator is responsible for:
    - maintaining agent state
    - asking the selected backend for the next response
    - executing requested tools
    - detecting repeated tool calls
    - feeding tool results back to the model
    - stopping when the model produces a final answer

The orchestrator deliberately does NOT know how Ollama, Claude,
or another provider represents tool calls internally.

That translation belongs in backends.py.

Architecture notes
------------------

Aider:
    We can borrow Aider's repository-awareness ideas later,
    particularly a repository map that gives the model structural
    knowledge of the project before it starts reading individual files.

    Aider itself does not need to become part of this loop.

LangGraph:
    LangGraph could eventually replace this explicit loop if we
    need persistent graph state, checkpointing, branching,
    resumability, or human-in-the-loop workflows.

    For now, keeping the loop as ordinary Python makes the
    orchestration behavior explicit and easier to understand.

CrewAI:
    CrewAI could become useful if this grows into genuinely
    separate agents such as:
        researcher -> coder -> tester -> reviewer

    That is not the current problem. Right now we are fixing
    the single-agent tool loop.

No framework:
    This is intentional. The current goal is to understand and
    strengthen our own orchestration layer before introducing
    another orchestration abstraction.
"""

import json
from dataclasses import dataclass, field

from backends import get_backend
from tools import TOOL_SCHEMA, TOOL_FUNCTIONS


MAX_STEPS = 20
MAX_REPEATED_TOOL_CALLS = 1


SYSTEM_PROMPT = """
You are a local software-engineering agent operating inside a repository.

Investigate before making claims about the code.

When inspecting a repository:

1. Discover the repository structure before assuming a file exists.
2. Read relevant files rather than guessing their contents.
3. Follow imports and references when they matter to the task.
4. Treat tool errors as information.
5. Never blindly repeat the same failed tool call.
6. Keep track of files and actions you have already inspected.
7. Verify important conclusions when possible.
8. Once you have enough evidence, stop using tools and answer.

If a requested file cannot be found:
- do not repeatedly request the same path
- inspect the surrounding directory
- search for the likely filename
- continue from the information you discover

When recommending code improvements:
- identify the observed problem
- explain why it matters
- distinguish observed facts from recommendations
- do not claim that something works unless you verified it
"""


@dataclass
class AgentState:
    """
    Runtime state for one agent task.

    This is intentionally a normal Python dataclass.

    LANGGRAPH NOTE:
        If this eventually becomes a large state machine with
        persistence, branching, checkpointing, and resumability,
        this state could map naturally onto LangGraph state.

    CREWAI NOTE:
        A CrewAI Flow could eventually provide a similar state/
        execution abstraction if this becomes a multi-agent system.
    """

    task: str
    messages: list = field(default_factory=list)
    tool_history: list = field(default_factory=list)
    repeated_calls: dict = field(default_factory=dict)
    step: int = 0


def tool_call_signature(tool_call: dict) -> str:
    """
    Produce a stable representation of a normalized tool call.

    This lets the orchestrator detect:
        read_file("backend.py")
        read_file("backend.py")

    as the same action even if they occur on different steps.
    """

    name = tool_call["name"]
    args = tool_call.get("input", {})

    return (
        f"{name}:"
        f"{json.dumps(args, sort_keys=True, default=str)}"
    )


def run_tool_call(tool_call: dict) -> dict:
    """
    Execute a normalized tool call.

    Backend-specific parsing should already have happened before
    this function receives the call.
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
            result = (
                f"Tool error: {type(exc).__name__}: {exc}"
            )

    return {
        "id": call_id,
        "name": name,
        "result": str(result),
    }


def run(task: str, backend_name: str = "ollama") -> str:
    backend = get_backend(backend_name)

    state = AgentState(task=task)

    state.messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": task,
        },
    ]

    for step in range(MAX_STEPS):

        state.step = step

        reply = backend.chat(
            state.messages,
            tools=TOOL_SCHEMA,
        )

        content = reply.get("content") or ""
        tool_calls = reply.get("tool_calls") or []

        if content:
            print(
                f"[{backend_name} | step {step}] "
                f"{content}"
            )

        # ---------------------------------------------------------
        # No tool calls means the model considers the task complete.
        # ---------------------------------------------------------

        if not tool_calls:
            return content

        # ---------------------------------------------------------
        # IMPORTANT:
        #
        # Preserve the assistant's actual tool-call message.
        #
        # The old implementation only appended:
        #
        #   {"role": "assistant", "content": content}
        #
        # which discarded reply["tool_calls"].
        #
        # That meant the next model request contained tool results
        # without the assistant's corresponding tool requests.
        #
        # The backend knows how to preserve its native format.
        # ---------------------------------------------------------

        state.messages.append(
            backend.make_assistant_message(reply)
        )

        # ---------------------------------------------------------
        # Execute every tool call requested by the model.
        # ---------------------------------------------------------

        for raw_call in tool_calls:

            # Convert Claude/Ollama/etc. into our one internal shape:
            #
            # {
            #     "id": "...",
            #     "name": "read_file",
            #     "input": {"path": "..."}
            # }
            #
            normalized_call = backend.normalize_tool_call(raw_call)

            signature = tool_call_signature(normalized_call)

            previous_count = state.repeated_calls.get(
                signature,
                0,
            )

            # -----------------------------------------------------
            # Loop protection.
            #
            # The model already tried this exact call.
            # Do not execute it again indefinitely.
            # -----------------------------------------------------

            if previous_count >= MAX_REPEATED_TOOL_CALLS:

                result = (
                    "This exact tool call has already been attempted. "
                    "Do not repeat it. Use the information already "
                    "available or choose a different approach."
                )

                print(
                    f"  -> blocked repeated tool call: "
                    f"{normalized_call['name']}"
                )

                state.messages.append(
                    backend.make_tool_result_message(
                        normalized_call,
                        result,
                    )
                )

                continue

            state.repeated_calls[signature] = (
                previous_count + 1
            )

            # -----------------------------------------------------
            # Actually execute the tool.
            # -----------------------------------------------------

            outcome = run_tool_call(normalized_call)

            state.tool_history.append(outcome)

            print(
                f"  -> tool '{outcome['name']}' result: "
                f"{outcome['result'][:200]}"
            )

            # -----------------------------------------------------
            # Give the result back in the format expected by the
            # selected backend.
            # -----------------------------------------------------

            state.messages.append(
                backend.make_tool_result_message(
                    normalized_call,
                    outcome["result"],
                )
            )

    return (
        f"Stopped after {MAX_STEPS} steps without "
        "receiving a final answer."
    )


if __name__ == "__main__":
    import sys

    backend_choice = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "ollama"
    )

    task_input = (
        " ".join(sys.argv[2:])
        or "List the files in the current directory."
    )

    print(
        f"Running with backend: {backend_choice}\n"
        f"Task: {task_input}\n"
    )

    final = run(
        task_input,
        backend_name=backend_choice,
    )

    print(f"\nFinal answer:\n{final}")