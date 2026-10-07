# Documentation: Handling Model Tool Support Errors

## 1. Problem Description

When the orchestrator attempts to use a tool, and the selected model does not support tools, an error is currently thrown, which terminates the conversation flow.

This occurs because the `backend.chat()` method, when called, returns a response that might contain an error or lack tool calls, and the orchestrator's logic directly proceeds based on the presence of `tool_calls`.

**Example Error Context:**
The system reported: `An error occurred: Model 'gemma3:4b' does not support tools. Capabilities: completion, vision.`

## 2. Goal

The goal is to modify the orchestrator's logic to detect when a model does not support tools and inform the user about this limitation, allowing the conversation to continue instead of stopping the execution.

## 3. Intended State / Proposed Solution

The `interactive_chat` function should be updated to:
1.  Check the model's capabilities or the response structure for indicators that tool use is unsupported.
2.  If tool use is unsupported, generate a user-friendly message informing the user about the model's limitations.
3.  Continue the loop by processing the model's response content, even if it contains no tool calls.

## 4. User Cases

A human or another AI agent should be able to locate this documentation file to understand the context and intended changes.

**How to access this documentation:**
```bash
cd Documentation/Tool_Support_Issues/Tool_Support_Issues.md
```