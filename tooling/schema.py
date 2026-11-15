"""Backend-neutral definitions of the tools available to the model."""


def _function(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    parameters = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


TOOL_SCHEMA = [
    _function(
        "list_directory",
        "List files and folders in a given directory.",
        {"path": {"type": "string", "description": "Directory path to list."}},
        ["path"],
    ),
    _function(
        "read_file",
        "Read the text contents of a file.",
        {"path": {"type": "string", "description": "File path to read."}},
        ["path"],
    ),
    _function(
        "run_python",
        "Run a Python script and return its stdout and stderr.",
        {"path": {"type": "string", "description": "File path to a Python script."}},
        ["path"],
    ),
    _function(
        "create_optimus_voice_track",
        (
            "Create a local WAV track from text using Kokoro, then convert it with "
            "the installed Optimus RVC voice model. Returns source and converted paths."
        ),
        {
            "text": {"type": "string", "description": "Text to speak (maximum 4,000 characters)."},
            "voice": {"type": "string", "description": "Optional Kokoro voice ID; default is af_nicole."},
            "speed": {"type": "number", "description": "Optional Kokoro speed from 0.25 to 2.0; default is 0.92."},
            "pitch": {"type": "integer", "description": "Optional RVC pitch shift; default is 0."},
            "index_rate": {"type": "number", "description": "Optional RVC index blend from 0 to 1; default is 0.75."},
        },
        ["text"],
    ),
    _function(
        "skill_index",
        (
            "List local skills and their descriptions. Call this before selecting a skill, "
            "then use read_file on the selected SKILL.md."
        ),
        {},
    ),
    _function(
        "write_file",
        "Write text to a file, creating parent directories when required. Existing files are overwritten.",
        {
            "path": {"type": "string", "description": "File path to write."},
            "content": {"type": "string", "description": "Text content to write."},
        },
        ["path", "content"],
    ),
    _function(
        "run_linter_check",
        "Run Ruff and Pylint checks on a directory or file and return their findings.",
        {"path": {"type": "string", "description": "Path to lint."}},
        ["path"],
    ),
    _function(
        "run_command",
        (
            """Run a shell command in the terminal and return its bounded 
            stdout + stderr + exit code. Use for git, make, node, ffmpeg, package managers,
            and any other command-line task. Commands run with a 120 second timeout.
                """
        ),
        {"command": {"type": "string", "description": "Shell command to run."},
         "cwd": {"type": "string", "description": "Optional working directory for the command."},
         "timeout": {"type": "integer", "description": "Optional timeout in seconds; default is 120."},
        },
        ["command"],
    ),
    _function(
        "glob_files",
        "Find files whose names match a glob pattern, searching recursively.",
        {
            "pattern": {"type": "string", "description": "Glob pattern to match file names (e.g., '**/*.py')."},
            "path": {"type": "string", "description": "Root directory to search; (default is '.') ."},
        },
        ["pattern"],
    ),
    _function(
        "grep_files",
        "Search file contents for a substring (case-insensitive) and return matching lines.",
        {
            "text": {"type": "string", "description": "Substring to search for."},
            "path": {"type": "string", "description": "Root directory to search; default is '.'."},
            "glob": {"type": "string", "description": "Optional file filter, e.g. '*.py'."},
            "max_results": {"type": "integer", "description": "Optional max matching lines (default 400)."},
        },
        ["text"],
    ),
    _function(
        "edit_context",
        ("""
            Replace the entire active conversation history with a new, cleamed-up
            list of messages. Use this to compact, summarise, or restructure your
            own context (Context Language Model capability). Pass the complete new
            message list you want to keep, in order. Keep the system prompt first, then drop
            redundant or already-resolved exchanges, and preserve every
            fact, decision, and unfinished step you still need to address.
            This is a full replacement of the conversation history, Not an append or partial edit.
        """
        ),
        {
            "messages": {
                "type": "array",
                "description": "The complete new message history, in order.",
                "items": {
                    "type": "object",
                    "properties":{
                        "role": {
                            "type": "string",
                            "enum": ["system", "user", "assistant", "tool"],
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
        },
        ["messages"],
    ),
]
