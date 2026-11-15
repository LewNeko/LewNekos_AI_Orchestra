# Code Review Skill

> **Status: prototype.** The single-file orchestrator `codeReader.py` exists and runs against a local Ollama model, but the `agents/` folder doesn't exist yet. There's also no `sample.diff` committed. To use it today you must create both before invoking the script.

## Overview
This skill provides a structured framework fr review a code diff using a multi-agent pattern: one specialist agent per concern (security, performance, readability, logic, ...), each in its own isolated context, followed by a validator pass that only sees the specialists' outputs (not the diff) and flags gaps.

## Components
- `codeReader.py`: The core engine that reads the diff, invokes specialist agents, and aggregates their findings.
  - `load_agent` &ndash; parses a Markdown agent file with optional YAML-style frontmatter (simple `key: value` lines) and returns `(meta, body)`.
  - `run_agent(system_prompt, user_input)` &ndash; one Ollama chat call per agent; **fresh context per call**, no shared history. Hard-coded to `OLLAMA_URL = http://localhost:11434/api/chat` and `MODEL = qwen2.5-coder:14b`.
  - `review_diff`(diff_text)` &ndash; iterates `agents/*.md`, runs each specialist, then runs a validator prompt over the concatenated outputs.
  - `__main__` &ndash; reads `sample.diff` from the current directory.

- `agents/`: **does not exist yet**. This is the intended home of the specialist prompts (one .md per agent: e.g. security.md, performance.md, readability.md).
- sample.diff: not committed. The user must supply one before running.

## Requirements
1. Ollama running locally with a coding-capable model (the code currently assumes `qwen2.5-coder:14b`; change the `MODEL` constant to use another). 
2. An `agents/` folder next to `codeReader.py` with at least one `.md` file.
3. A `sample.diff` file next to `codeReader.py`.

## Usage
```
cd skills/code_review
# create agents/security.md
agents/performance.md, ...
# create sample.diff
python codeReader.py
```


## Workflow
1. **Input**: a unified diff file.
2. **Specialist revieww**: each `.md` in `agents/` is loaded and sent, in its own isolated context, the prompt `Review this diff:\n\n{diff}`.
3. **Validation**: a separate agent &ndash; given only the concatenated specialist outputs, not the diff &ndash; lists gaps and vague answers.
4. **Output**: per-agent findings and the validation summary printed to stdout.

## Known limitations
- Model, URL, and agent prompt layout are hard-coded constants
- no CLI flags yet.
- No persistance of findings (no SQLite, no JSON output).
- No concurrency; specialists run sequentially. (although this is because this is meant to be run locally, and hardware may not support parallelism in all cases, espicially for multiple AI agents)
- The frontmatter parser nly handles simple `key: value` pairs; nested YAML is not supported.
