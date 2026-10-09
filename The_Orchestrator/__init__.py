"""
orchestrator
------------

The agent loop, split by responsibility:

    config.py    limits (MAX_STEPS, repeat guard, preview length)
    prompts.py   SYSTEM_PROMPT
    state.py     AgentState dataclass
    executor.py  run_tool_call, tool_call_signature
    loop.py      run_agent_turn  (the model <-> tool cycle)
    session.py   interactive_chat, run_single_task
    __main__.py  `python -m orchestrator [backend]`

The orchestrator deliberately does NOT know how Ollama, Claude, or another
provider represents tool calls. That translation belongs in backends.py.

Architecture notes
------------------
Aider:     borrow its repository-map idea later; it need not be part of
           this loop.
LangGraph: could replace the explicit loop if we need persistent graph
           state, checkpointing, branching, resumability, or
           human-in-the-loop. Until then, plain Python keeps behaviour
           explicit.
CrewAI:    useful only if this becomes genuinely separate agents
           (researcher -> coder -> tester -> reviewer). Not the current
           problem.
No framework: intentional. Strengthen our own orchestration layer first.
"""

from .loop import run_agent_turn
from .session import interactive_chat, run_single_task
from .state import AgentState

__all__ = [
    "AgentState",
    "interactive_chat",
    "run_agent_turn",
    "run_single_task",
]
