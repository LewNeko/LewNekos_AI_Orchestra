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
]
