# LewNekos AI Orchestrator Skills

## Overview
The LewNekos AI Orchestrator is a multi-model capable agent designed to perform tasks by interacting with the local environment. It supports swappable backends (e.g., Ollama for local execution or Anthropic's Claude for advanced reasoning) while maintaining a consistent orchestration logic.

## Capabilities
The agent is equipped with the following tools to interact with the file system:

### 1. list_directory
- **Description**: Lists files and folders in a given directory.
- **Parameters**: `path` (string) - The directory path to list.
- **Usage**: Use this to explore the file system and identify relevant files.

### 2. read_file
- **Description**: Reads the text content of a specified file.
- **Parameters**: `path` (string) - The file path to read.
- **Note**: Content is truncated to 3000 characters to maintain context window efficiency.

## Operational Logic
- **Multi-Step Reasoning**: The orchestrator supports a loop (up to 6 steps) where the model can call tools, receive results, and refine its plan.
- **Context Management**: The agent is instructed to use tools only when necessary and provide a clear final answer once sufficient information is gathered.
- **Backend Agnostic**: The core logic remains identical regardless of whether the backend is a local model (Ollama) or a remote API (Claude).

## System Instructions
- You are a helpful local assistant.
- Use tools when you need information you don't already have.
- Provide a clear final answer once you have enough information.
