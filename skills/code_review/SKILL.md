# Code Review Skill

This skill provides a structured framework for reviewing code changes using a multi-agent approach. It leverages specialized agents to provide comprehensive feedback on different aspects of the code (e.g., security, performance, readability, logic) and includes a validation step to ensure all areas are covered.

## Overview
The `codeReader.py` script orchestrates a team of AI agents to review a given `diff`. Each agent is assigned a specific role and scope of review, ensuring that different facets of the code are analyzed independently before their outputs are validated.

## Components
- `codeReader.py`: The core engine that reads the diff, invokes specialist agents, and aggregates their findings.
- `agents/`: A directory containing Markdown files, each defining a specialist agent (e.g., SecurityReviewer, PerformanceExpert, ReadabilityChecker). In progress, this doesn't exist yet.

## Usage
To use this skill, provide a `sample.diff` file containing the code changes to be reviewed. The script will:
1. Parse each agent's system prompt from its respective `.md` file in the `agents` folder
2. Send the diff to each agent individually for specialized feedback.
3. Perform a validation pass to identify any gaps or vague responses from the specialists.
4. Output the consolidated findings and the validation report.

## Requirements
- Ollama service running with good model for coding.
- A `sample.diff` file in the locall directory.
- A directory named `agents` populated with agent definition files.

## Workflow
1. **Input**: A diff file representing the code changes.
2. **Specialist Review**: Parallel (or sequential) execution of multiple agent prompts focused on specific metrics.
3. **Validation**: A final pass by a "Validator" agent to verify the quality and completeness of the previous outputs.
4. **Output**: A comprehensive review report showcasing each agent's findings and a final validation summary.
