# The_Orchestrator Skill

## Overview
`The_Orchestrator` is the central agent loop of the repository. It manages the interaction between the user, the model backend, the tools, and (indirectly) the speciailized agents in `The_Reader`, `The_Chunker`, and `The_Auditor`, and `knowledge_service`.

It is a python package.

```
The_Orchestrator/
├── __init__.py 
├── __main__.py   # Entrypoint: python -m The_Orchestrator [backend]
├── config.py     # MAX_STEPS, MAX_REPEATED_TOOL_CALLS, RESULT_PREVIEW_CHARS
├── executor.py   # run_tool_call, tool_call_signature (provider-agnostic)
├── loop.py       # run_agent_turn, which is the core loop
├── prompts.py    # SYSTEM_PROMPT (context-menagement + repo rules + audio instructions) - later this will pull from agent.md
├── session.py    # interactive_chat + run_single_task
└── state.py      # AgentState dataclass
```

## Run it
```bash
python -m The_Orchestrator #default backend: ollama (gemma3:4b, which currently breaks the program because there's no support to models without tooling abilities anymore right now)
python -m The_Orchestrator ollama-qwen3:8b # any key from backends from BACKENDS

python -m The_Orchestrator claude #requires ANTHROPIC_API_KEY
```

## Core Functionality (verified against code)
- **Model-Independent Orchestration**: Uses a `backends.py::ModelBacked`. `The_Orchestrator` never touches Ollama or Anthropic directly; it only calls `backend.chat(...)`, `backend.normalize_tool_call(...)`, `backend.make_assistant_message(...)`, and `backend.make_tool_result_message(...)`.
- **The Agent Loop** (`loop.py::run_agent_turn`):
  1. Call `backend.chat(state.messages, tools=TOOL_SCHEMA)`.
  2. If no tool calls &rightarrow; return content as the final answer.
  3. Otherwise, normalize each raw call, loop-guard it, execute it, feed the result back, and repeat.
  4. Stop after `MAX_STEPS` if the model never yields a final answer.
- **Repeat-call guard**: `executor.py::tool_call_signature` computes `name + sorted JSON args`; `state.repeated_calls` count how many times the identical call as been made in this turn; once a call has been made `MAX_REPEATED_TOOL_CALLS` times it is blocked and a `BLOCKED_MESSAGE` tool result is appended so the model can recover.
- **Special case - `edit_context`**: in `loop.py::_handle_tool_call` if the tool name is `edit_context`, the loop reads `input.messages` and calls `state.replace_messages(new_msgs)`, replacing the ENTIRE conversation history. No tool result is appended in that case. (Note: `tooling/context.py::edit_context` is currently a no-op placeholder that returns a "not implemented yet" string; it is also not in `TOOL_SCHEMA` or `TOOL_FUNCTIONS`, so the model cannot invoke it today - the loop code is forward-looking.)
- **Session semantics** (`session.py`):
  - `interactive_chat(backend_name)`: REPL; exits only `exit`/`quit`, EOF, or Ctrl+C. On exception mid-turn, rolls the message history back to the pre-turn checkpoint so history never contains a tool request without its result.
  - `run_single_task(task, backend_name)`: one-shot; creates a fresh `AgentState`, runs one turn, returns the answer text.
- **State** (`state.py::AgentState`): `task`, `messages`, `repeated_calls`, `tool_history`, `step`. `new_turn()` clears `repeated_calls` and `step` per user request, so a new question can legitimately re-read a file seen in a previous turn.
- **System prompt** (`prompts.py::SYSTEM_PROMPT`): instructs the model to manage its own context file via `edit_context` (currently a placeholder), to investigate before claiming, and to use `create_optimus_voice_track` for spoken audio.

## Tool surface (source of truth: `tooling/schema.py` + `tooling/registry.py`)
| Name | Description | Required args |
|---|---|---|
| `list_directory` | List files/folders in a directory. | `path` |
| `read_file` | Read a text file (truncated to `MAX_READ_CHARS=12000`). | `path` |
| `write_file` | Write UTF-8 text, creating arent dirs; overwrites. | `path`, `content` |
| `run_python` | Run a Python script with the same interpreter; 120-second timeout. | `path` |
| `run_linter_check` | Run Ruff + Pylint on a path; bounded stdout/stderr. | `path` |
| `skill_index` | List local `skill/*/SKILL.md` files with a short summary. | `none` |
| `create_optimus_voice_track` | Speak text with kokoro, convert with Optimus RVC; returns WAV paths. | `text` (optional: `voice`, `speed`, `pitch`, `index_rate`) |

`tools.py` at the repo root is a **compatibility facade** - it re-exports the real implementations from `tooling/` so that `from tools import TOOL_SCHEMA, TOOL_FUNCTIONS` works as expected. Also makes pulling functions from `tools` functionally consistent.

## Tunable (`The_Orchestrator/config.py`)
- `MAX_STEPS`: model-call cap per user turn (currently `1000`).
- `MAX_REPEATED_TOOL_CALLS`: how many times the exact same tool call may execute in a turn before being blocked (currently `5`).
- `RESULT_PREVIEW_CHARS`: console echo length for each tool result (currently `200`).

## Integration
- **Inputs**: User queries or initial tasks.
- **Outputs**: Final judged string; the interactive mode also prints per-step tool-call previews.
- **Backends**: any key in `backends.BACKENDS` (see that file for the current list - `ollama`, `ollama-qwen3.8:27b`, claude, openai, etc)
- **Error model**: the executor caches all tool exceptions and returns them as `result` strings so the model can recover from them - a tool failure never crashes the loop.

