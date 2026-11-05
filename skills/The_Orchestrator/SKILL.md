# The_Orchestrator Skill

## Overview
`The_Orchestrator` is the central nervous system of the project. It manages the interaction between the user, the models, the tools, and the specialized agents.

## Core Functionality
- **Model-Independent Orchestration**: Uses a `backends.py` abstraction to allow hot-swapping between different LLM providers (OLLAMA, Claude, etc.).
- **The Agent Loop**: Implements the core cycle:
  1. Send request/reasoning step.
  2. Model decides if tool use is required.
  3. Orchestrator executes the requested tool.
  4. Orchestrator returns tool output to the model.
  5. Model reasons again based on new information.
- **Tool management**: Provides access to a unified set of capabilities (`tooling` & `tools.py`).

## Integration
- **Inputs**: User queries or initial tasks.
- **Outputs**: Final judged answers or requested actions.
- **Architecture**: Based on the `LewNekos_AI_Orchestra` architecture, which decouples the reasoning logic from the communication transport.