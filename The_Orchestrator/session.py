"""
session.py
----------
User-facing entry points: the interactive chat and the one-shot task runner.
"""

from backends import get_backend
from tools import view_context

from .loop import run_agent_turn
from .state import AgentState

EXIT_WORDS = {"exit", "quit"}
# Commands the user can type to inspect state, without sending a prompt.
VIEW_CONTEXT_WORDS = {"context", "/context", "show context", "/context show"}

def _show_context(state: AgentState) -> None:
    """Print the current conversation context for the human, without a model call."""
    print("\n" + view_context(agent_state=state) + "\n")

def run_single_task(task: str, backend_name: str = "ollama") -> str:
    """Run one non-interactive task to completion and return the answer."""
    backend = get_backend(backend_name)
    state = AgentState.with_system_prompt(task)
    state.messages.append({"role": "user", "content": task})
    return run_agent_turn(backend, state, label=backend_name)


def interactive_chat(backend_name: str = "ollama") -> None:
    """
    Conversational loop. Each user message starts one agent turn; the agent
    may call as many tools as it needs within that turn before replying.
    The session only ends when the user exits.

    User-only commands (no model call):
        context | /context | show context -> print the live conversation context
    """
    # later i should make a handle just for user commands.
    backend = get_backend(backend_name)

    print("--- Interactive Chat Session ---")
    print(f"Model Backend: {backend_name}")
    print("Type 'exit' to end the conversation.")
    print("Type '/context' to inspect the current conversation context.")
    print("---------------------------------")

    state = AgentState.with_system_prompt("Interactive session")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue

        # User-only inspection commands run before we touch the model.
        if user_input.lower() in VIEW_CONTEXT_WORDS:
            _show_context(state)
            continue

        if user_input.lower() in EXIT_WORDS:
            break

        checkpoint = len(state.messages)
        state.messages.append({"role": "user", "content": user_input})

        try:
            answer = run_agent_turn(backend, state, label=backend_name)
        except Exception as exc:
            # Roll back the half-finished turn so history never contains a
            # tool request without its result, then keep the session alive.
            del state.messages[checkpoint:]
            print(f"\nAn error occurred: {type(exc).__name__}: {exc}\n")
            continue

        print(f"\n{backend_name}: {answer}\n")

    print("\n--- Conversation Ended ---")
