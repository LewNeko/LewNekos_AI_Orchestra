"""Public compatibility facade for the Orchestrator's local agent tools.

Tool implementations live in ``tooling/``. Keeping this module preserves the
existing ``from tools import TOOL_SCHEMA, TOOL_FUNCTIONS`` imports used by the
Orchestrator and any external callers.

``view_context`` is intentionally not in TOOL_FUNCTIONS/TOOL_SCHEMA: it is a 
user-facing helper (the interactive chat exposes it) that
needs the live AgentState, which the tool executor cannot inject. 
It is re-exported here for convenience and testing.
"""

from tooling.context import edit_context, view_context
from tooling.execution import run_linter_check, run_python
from tooling.filesystem import list_directory, read_file, write_file
from tooling.registry import TOOL_FUNCTIONS
from tooling.schema import TOOL_SCHEMA
from tooling.shell import glob_files, grep_files, run_command
from tooling.skills import skill_index
from tooling.voice import create_optimus_voice_track

__all__ = [
    "TOOL_FUNCTIONS",
    "TOOL_SCHEMA",
    "create_optimus_voice_track",
    "edit_context",
    "view_context",
    "list_directory",
    "read_file",
    "run_linter_check",
    "run_python",
    "skill_index",
    "write_file",
    "glob_files",
    "grep_files",
    "run_command",
]
