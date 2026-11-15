"""Context-management tool (Context Language Model capability).
CLM philosophy  is that the model itself treats its active message history as an editable "file" and rewrites it in place. Rather than a fixed external summarizer
deciding what to keep, the agent decides when and how to compact, summarize, or restructure its own context.
edit_context receives the new full message list the model wants and validates it.
the actual application only AgentState is coordinated in The_Orchestrator/loop.py so
the same function works under both the Ollama and Claude backends.
"""

from __future__ import annotations

def _valid_role(role: object) -> bool:
    return role in {"system", "user", "assistant", "tool"}

def _normalise_message(message: object) -> dict | None:
    """
    Validate one message dict; return None when it is not usable.
    """
    if not isinstance(message, dict):
        return None
    role = message.get("role")
    if not _valid_role(role):
        return None
    content = message.get("content")
    if content is None:
        content = ""
    return {"role": role, "content": content}
    

def edit_context(messages: list | dict, agent_state=None) -> str:
    """
    Replace the agent's active message history with the provided list.
    The 'messages' parameter may be either a list of message dicts, or
    an object with a 'messages' key (the loop may pass the tool input object).

    When agent_state is provided (the Orchestrator loop does this), the new history is applied immediately. when
    it is None (unit tests / standalone), the function skill validates and
    reports when would be applied so the contract stays stable.
    """
    if isinstance(messages, dict):
        messages = messages.get("messages", [])

    if not isinstance(messages, list):
        return "Error: edit_context expects a list of messages."

    cleaned = [_normalise_message(m) for m in messages]
    cleaned = [m for m in cleaned if m is not None]

    if not cleaned:
        return "Error: edit context produced an empty context. Refusing to replace it."

    if agent_state is not None:
        agent_state.replace_messages(cleaned)

    total_chars = sum(len(m["content"]) for m in cleaned)
    return (
        f"Context replaced: now {len(cleaned)} message(s), "
        f"~{total_chars} characters total."
    )