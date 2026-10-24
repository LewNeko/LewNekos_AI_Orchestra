"""Single registry mapping tool-call names to their implementations."""

from .execution import run_linter_check, run_python
from .filesystem import list_directory, read_file, write_file
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
}
