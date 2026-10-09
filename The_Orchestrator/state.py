"""
state.py
--------
Runtime state for an agent session.

LANGGRAPH NOTE:
    If this grows into a state machine with persistence, branching,
    checkpointing, and resumability, this dataclass maps naturally onto
    LangGraph state.

CREWAI NOTE:
    A CrewAI Flow could provide a similar state/execution abstraction if
    this becomes a multi-agent system.
"""

from dataclasses import dataclass, field

from .prompts import SYSTEM_PROMPT


@dataclass
class AgentState:
    task: str
    messages: list = field(default_factory=list)
    tool_history: list = field(default_factory=list)
    repeated_calls: dict = field(default_factory=dict)
    step: int = 0

    @classmethod
    def with_system_prompt(cls, task: str) -> "AgentState":
        """Create a state whose history starts with the system prompt."""
        return cls(
            task=task,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}],
        )

    def new_turn(self) -> None:
        """
        Reset per-turn bookkeeping. Called at the start of every user request.

        Repeat detection is scoped to a single turn so that a new question
        can legitimately re-read a file the model looked at earlier.
        tool_history and messages are kept for the whole session.
        """
        self.repeated_calls.clear()
        self.step = 0
