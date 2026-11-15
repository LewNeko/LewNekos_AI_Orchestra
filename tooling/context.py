"""Context-management tool (Context Language Model capability).
CLM philosophy  is that the model itself treats its active message history as 
an editable "file" and rewrites it in place. Rather than a fixed external summarizer
deciding what to keep, the agent decides when and how to compact, summarize, 
or restructure its own context.

Two tools live here:
edit_context: the model replaces the whole live history.

view_context: a read-only render of the live history, used both by the model 
(to inspect its context before deciding to compact) and by the human user 
(the interactive chat exposes it as the 'context' command).

edit_context receives the new full message list the model wants and validates it. 
The actual application onto AgentState is coordinated in The_Orchestrator/loop.py
so the same function works under both the Ollama and Claude backends.
"""

from __future__ import annotations

VALID_ROLES = {"system", "user", "assistant", "tool"}

# Per-message preview budget for view_context, so a long context stays readable.
_VIEW_MESSAGE_CHARS = 600

def _valid_role(role: object) -> bool:
    return role in VALID_ROLES

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

    When agent_state is provided (the Orchestrator loop does this), 
    the new history is applied immediately. when
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

def _message_content_text(content) -> str:
    """
    Flatten a message's content (str or a list of blocks) to plain text.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", block.get("content", block))))
            else:
                parts.append(str(block))
        return " ".join(p for p in parts if p)
    return str(content)

def view_context(agent_state=None, messages: list | None = None) -> str:
    """
    Render the current context (messagee history) as readable text.

    Data source:
    agent_state: an AgentState (the interactive chat passes this).
    messages: a raw list of message dicts (standalone/tests).
    either may be None; at least one must carry messages.

    Output is bounded: each message is truncated to _VIEW_MESSAGE_CHARS and 
    a rough total (message + characters) is reported at the top, so the user
    or model can see how large the context is before deciding to compact it.
    """
    if agent_state is not None:
        messages = agent_state.messages
    if not messages:
        return "(context is empty)"
    if not isinstance(messages, list):
        return "Error: view_context needs an AgentState or a message list."
    total_chars = 0
    lines = []
    for index, message in enumerate(messages, start=1):
        if not isinstance(message, dict):
            continue
        role = message.get("role", "unknown")
        text = _message_content_text(message.get("content", ""))
        total_chars += len(text)

        preview = text if len(text) <= _VIEW_MESSAGE_CHARS else text[:_VIEW_MESSAGE_CHARS] + "...(truncated)"
        # Collapse newlines so the transcript stays on a compact, scannable block.
        preview = " ".join(preview.split())
        lines.append(f"[{index}] {role.upper()}: {preview or '(no content)'}")

    header = (
        f"== CONVERSATION CONTEXT ==\n"
        f"{len(lines)} message(s), ~{total_chars} characters total.\n"
        f"(rough token estimate: ~{total_chars // 4} tokens)\n"
        + "-" * 40
    )
    return header + "\n" + "\n".join(lines)
