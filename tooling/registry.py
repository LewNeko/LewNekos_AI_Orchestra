"""Single registry mapping tool-call names to their implementations."""

from .context import edit_context
from .execution import run_linter_check, run_python
from .filesystem import list_directory, read_file, write_file
from .shell import glob_files, grep_files, run_command
from .skills import skill_index
from .voice import create_optimus_voice_track

TOOL_FUNCTIONS = {
    "list_directory": list_directory,
    "read_file": read_file,
    "skill_index": skill_index,
    "run_python": run_python,
    "create_optimus_voice_track": create_optimus_voice_track,
    "run_linter_check": run_linter_check,
    "write_file": write_file,
    # edit context replaces the live history, so the Orchestrator loop applies
    # it directly (The_Orchestrator/loop.py). It's registered here so
    # the tool name is a known tool and the public tools.py facade stays consistent.
    "edit_context": edit_context,
    "glob_files": glob_files,
    "grep_files": grep_files,
    "run_command": run_command,
}
