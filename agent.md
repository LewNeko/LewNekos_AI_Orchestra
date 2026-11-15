# LewNekos AI Orchestrator Skills

## Overview
The LewNekos AI Orchestrator is a multi-model-capable agent that performs tasks by interacting with the local environment. It supports swappable backends (Ollama for local execution, or Anthropic's Claude for advanced reasoning) while keeping a single, backend-agnostic orchestration loop.

The agent loop lives in the `The_Orchestrator.` package (run with `python -m The_Orchestrator [backend]`).
The model backend is abstracted behind `backends.py::ModelBackend`. The tools are defined in `tooling/schema.py` + `tooling/registry.py` and re-exported through the `tools.py` facade.

## Available tools (source of truth: `tooling/schema.py`)

### 1. list_directory
- **Description**: Lists files and folders in a given directory.
- **Parameters**: `path` (string) - the directory path to list.


### 2. read_file
- **Description**: Reads the contents fo a file.
- **Parameters**: `path` (string) - the file path to read.
- **Note**: Content is truncated to `MAX_READ_CHARS` (12,000 characters, set in `tooling/constants.py`) to keep the model's context bounded.

### 3. write_file
- **Description**: Writes UTF-8 test to a file, creating parent directories as needed. Existing files are overwritten.
- **Parameters**: `path` (string), `content` (string).

### 4. run_python
- **Description**: Runs a python script using the same interpreter as the orchestrator and returns stdout + stderr.
- **Parameters**: `path` (string) - file path to a python script. (has a 120-second timeout)

### 5. run_linter_check
- **Description**: Runs Ruff and Pylint on a path and returns their bounded stdout/stderr.
- **Parameters**: `path` (string).

### 6. skill_index
- **Description**: Lists local skills (`skills/*/SKILL.md`) with a short summary. Call this before selecting a skill, then use `read_file` on the chosen `SKILL.md`.
- **Parameters**: none.

### 7. create_optimus_voice_track
- **Description**: Speaks text with Kokoro and converts it with the installed Optimus RVC voice model; returns source and converted WAV paths.
- **Parameters**: `text` (string, required; max 4,000 chars); optional `voice`, `speed`, `pitch`, `index_rate`.

### Operational logic
- **Multi-step reasoning**: within one user turn the model may call tools and receive results up to `MAX_STEPS`. model calls (current `1000`, set in `The_Orchestrator/config.py`).
- **Repeat-call guard**: the exact same tool call (name + args) may be executed at most `MAX_REPEATED_TOOL_CALLS` times (currently `5`) per turn before it is blocked.
- **Context management**: the system promt instructs the model to keep its own context clean via `edit_context`. Note: `edit_context` is currently a placeholder, it is not in the tool schema/registry and `tooling/context.py` returns a "not implemented yet" string. The loop in `The_Orchestrator/loop.py` already contains the forward looking handling for it though.
- **Backend-agnostic**: the loop logic is identical whether the backend is a local model (Ollama) or a remote API (Claude); backend-specific formats stay inside `backends.py`.
- **Error model**: tool exceptions are caught in `The_Orchestrator/executor.py` and returned as result strings, so a failing tool feeds information back to the model instead of crasing the loop.

## System instructions (source of truth: `The_Orchestrator/prompts.py::SYSTEM_PROMPT`)
The model is instructed to:
- Treat itself as a local software-engineering agent inside a repository.
- Manage its own context file (`edit_context`) to stay concise and dop irrelevant information.
- Investigate before making claims: discover structure before assuming a file exists, read files rather than guessing, treat tool errors as information, never blindly repeat a failed tool call. 
- Verify important conclusions when possible, and stop using tools once it has enough evidence.
- Use `create_optimus_voice_track` when asked for spoken audio, and report the WAV path without claiming playback happened unless the user confirms it.
