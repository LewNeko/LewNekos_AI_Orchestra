"""
loop.py
-------
The core agent loop for ONE user request ("turn").

run_agent_turn() keeps calling the model, executing the tools it asks for,
and feeding results back, until the model answers without requesting tools
(or MAX_STEPS is hit). Both the interactive chat and the single-task runner
use this one function, so the behaviour cannot drift apart.
"""

from tools import TOOL_SCHEMA

from .config import MAX_REPEATED_TOOL_CALLS, MAX_STEPS, RESULT_PREVIEW_CHARS
from .executor import run_tool_call, tool_call_signature
from .state import AgentState

BLOCKED_MESSAGE = (
    "This exact tool call has already been attempted. "
    "Do not repeat it. Use the information already "
    "available or choose a different approach."
)


def _handle_tool_call(backend, state: AgentState, raw_call) -> None:
    """Normalize, loop-guard, execute, and record one tool call."""
    call = backend.normalize_tool_call(raw_call)
    signature = tool_call_signature(call)
    previous_count = state.repeated_calls.get(signature, 0)

    if previous_count >= MAX_REPEATED_TOOL_CALLS:
        print(f"  -> blocked repeated tool call: {call['name']}")
        state.messages.append(
            backend.make_tool_result_message(call, BLOCKED_MESSAGE)
        )
        return

    state.repeated_calls[signature] = previous_count + 1

    outcome = run_tool_call(call)
    state.tool_history.append(outcome)

    print(f"  -> tool '{outcome['name']}' result: "
          f"{outcome['result'][:RESULT_PREVIEW_CHARS]}")

    state.messages.append(
        backend.make_tool_result_message(call, outcome["result"])
    )


def run_agent_turn(backend, state: AgentState, label: str = "agent") -> str:
    """
    Run the model/tool cycle until it produces a final answer.

    The caller must already have appended the user message to
    state.messages. Returns the final answer text.
    """
    state.new_turn()

    for step in range(MAX_STEPS):
        state.step = step

        reply = backend.chat(state.messages, tools=TOOL_SCHEMA)
        content = reply.get("content") or ""
        tool_calls = reply.get("tool_calls") or []

        # Always keep the assistant's message in history, including the
        # final answer, so later turns can see what the model said.
        state.messages.append(backend.make_assistant_message(reply))

        # No tool calls -> the model considers this turn complete.
        if not tool_calls:
            return content

        # Commentary that accompanies tool calls is intermediate; the
        # final answer is printed by the caller.
        if content:
            print(f"[{label} | step {step}] {content}")

        for raw_call in tool_calls:
            _handle_tool_call(backend, state, raw_call)

        # Fall through: loop back to the model WITH the tool results.

    return (
        f"Stopped after {MAX_STEPS} steps without "
        "receiving a final answer."
    )
