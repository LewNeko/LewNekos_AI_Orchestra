"""
backends.py
-----------
One interface, multiple model backends. The orchestrator never talks
to Ollama or Anthropic directly -- it only calls ModelBackend.chat().
Swapping backends is a one-line config change, not a rewrite.
"""

import json
import os
import requests

class ModelBackend:
    """
    Every backend implements this interface.

    The orchestrator works with a small normalized representation.

    Backend-specific API formats stay inside the backend.
    """

    def chat(self, messages: list, tools: list) -> dict:
        """
        Returns:

        {
            "content": str,
            "tool_calls": list | None,
            ...
        }
        """
        raise NotImplementedError

    def normalize_tool_call(self, tool_call: dict) -> dict:
        """
        Convert the provider-specific tool-call representation into:

        {
            "id": str,
            "name": str,
            "input": dict,
        }
        """
        raise NotImplementedError

    def make_assistant_message(self, reply: dict) -> dict:
        """
        Convert the backend's reply into the assistant message that
        must be preserved in the next model request.
        """
        raise NotImplementedError

    def make_tool_result_message(
        self,
        tool_call: dict,
        result: str,
    ) -> dict:
        """
        Convert a normalized tool result into the provider-specific
        message format expected by the backend.
        """
        raise NotImplementedError

class OllamaBackend(ModelBackend):
    """Local model served by Ollama via its OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str = "qwen3:4b",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.host = host
        self.url = f"{host}/v1/chat/completions"

    def _ensure_tool_support(self) -> None:
        """Raise a clear error only when the caller asks to use tools."""

        response = requests.post(
            f"{self.host}/api/show",
            json={"model": self.model},
            timeout=10,
        )

        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama model '{self.model}' is not installed."
            )

        response.raise_for_status()

        capabilities = response.json().get(
            "capabilities",
            [],
        )

        if "tools" not in capabilities:
            raise RuntimeError(
                f"Model '{self.model}' does not support tools. "
                f"Capabilities: "
                f"{', '.join(capabilities) or 'none'}."
            )

    def chat(
        self,
        messages: list,
        tools: list,
        ) -> dict:

        payload = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            self._ensure_tool_support()
            payload["tools"] = tools

        resp = requests.post(
            self.url,
            json=payload,
            # Keep your current behavior for now.
            # We can later add a configurable timeout.
        )

        resp.raise_for_status()

        data = resp.json()

        choice = data["choices"][0]["message"]

        return {
            "content": choice.get("content") or "",
            "tool_calls": choice.get("tool_calls") or None,
        }

    def normalize_tool_call(
        self,
        tool_call: dict,
        ) -> dict:
        """
        Ollama/OpenAI-style:

        {
            "id": "...",
            "function": {
                "name": "...",
                "arguments": "{...}"
            }
        }

        becomes our internal representation.
        """

        function = tool_call["function"]

        arguments = function.get(
            "arguments",
            {},
        )

        if isinstance(arguments, str):
            arguments = json.loads(arguments)

        return {
            "id": tool_call.get(
                "id",
                function["name"],
            ),
            "name": function["name"],
            "input": arguments,
        }

    def make_assistant_message(
        self,
        reply: dict,
        ) -> dict:
        """
        Preserve the assistant's tool_calls.

        THIS is the important fix for your current bug.
        """

        message = {
            "role": "assistant",
            "content": reply.get("content") or "",
        }

        if reply.get("tool_calls"):
            message["tool_calls"] = reply["tool_calls"]

        return message

    def make_tool_result_message(
        self,
        tool_call: dict,
        result: str,
        ) -> dict:
        """
        OpenAI/Ollama-compatible tool result.
        """

        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": result,
        }

class ClaudeBackend(ModelBackend):
    """Anthropic API. Requires ANTHROPIC_API_KEY in your environment."""

    def __init__(self, model: str = "claude-sonnet-5"):
        self.model = model
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Set ANTHROPIC_API_KEY before using ClaudeBackend "
                "(export ANTHROPIC_API_KEY=sk-ant-...)"
            )
        self.url = "https://api.anthropic.com/v1/messages"

    def chat(self, messages: list, tools: list) -> dict:
        # Anthropic wants system prompts separated out, not in the messages list.
        system_prompt = None
        anthropic_messages = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                anthropic_messages.append(m)

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": anthropic_messages,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = _openai_tools_to_anthropic(tools)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        resp = requests.post(self.url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        text_parts = [b["text"] for b in data["content"] if b["type"] == "text"]
        tool_calls = [b for b in data["content"] if b["type"] == "tool_use"]

        return {
            "content": "\n".join(text_parts),
            "tool_calls": tool_calls or None,

            # Preserve the original Anthropic content blocks.
            # The orchestrator needs these when continuing the conversation.
            "raw_content": data["content"],
        }
    def normalize_tool_call(
        self,
        tool_call: dict,
        ) -> dict:
        """
        Anthropic tool_use format:

        {
            "type": "tool_use",
            "id": "...",
            "name": "...",
            "input": {...}
        }

        becomes our internal representation.
        """

        return {
            "id": tool_call["id"],
            "name": tool_call["name"],
            "input": tool_call.get("input", {}),
        }

    def make_assistant_message(
        self,
        reply: dict,
        ) -> dict:
        """
        Anthropic requires the assistant's tool_use blocks
        to remain in the conversation.

        Therefore ClaudeBackend needs the original content blocks,
        not merely the extracted text.
        """

        return {
            "role": "assistant",
            "content": reply["raw_content"],
        }

    def make_tool_result_message(
        self,
        tool_call: dict,
        result: str,
        ) -> dict:
        """
        Anthropic represents tool results as a user content block.
        """

        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call["id"],
                    "content": result,
                }
            ],
        }

def _openai_tools_to_anthropic(tools: list) -> list:
    """Convert OpenAI-style tool schema to Anthropic's format."""
    converted = []
    for t in tools:
        fn = t["function"]
        converted.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return converted

# ---- Backend registry: this is the "swap" switch ----
"""
qwen3:4b is at home, no need to use it if device can use a stronger version.
qwen3-coder is massive, please do not use it casually.

qwen3-coder:latest       06c1097efce0    18 GB     STRONGEST
qwen3:8b                 500a1f067a9f    5.2 GB    Good
embeddinggemma:latest    85462619ee72    621 MB    functionality
gemma3:4b                a2af6cc3eb7f    3.3 GB    
"""
BACKENDS = {
    "ollama-qwen3:4b": lambda: OllamaBackend(model="qwen3:4b"),
    "ollama-qwen3:8b": lambda: OllamaBackend(model="qwen3:8b"),
    "ollama-gemma4:e2b": lambda: OllamaBackend(model="gemma4:e2b"),
    "ollama-gemma4:e4b": lambda: OllamaBackend(model="gemma4:e4b"),
    "ollama-gemma4:12b": lambda: OllamaBackend(model="gemma4:12b"),
    "ollama-gemma4:26b-a4b": lambda: OllamaBackend(model="gemma4:26b-a4b"),
    "ollama-qwen3-coder": lambda: OllamaBackend(model="qwen3-coder:latest"),
    "ollama-embed4gemma": lambda: OllamaBackend(model="embeddinggemma:latest"),
    "ollama": lambda: OllamaBackend(model="gemma3:4b"),
    "claude": lambda: ClaudeBackend(model="claude-sonnet-5"),
}

def get_backend(name: str) -> ModelBackend:
    if name not in BACKENDS:
        raise ValueError(f"Unknown backend '{name}'. Choose from: {list(BACKENDS)}")
    return BACKENDS[name]()
