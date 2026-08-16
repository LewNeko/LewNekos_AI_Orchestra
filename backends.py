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
    """Every backend must implement this shape."""

    def chat(self, messages: list, tools: list = None) -> dict:
        """
        messages: [{"role": "user"/"assistant"/"system"/"tool", "content": "..."}]
        tools: OpenAI-style tool schema (list of dicts) or None
        Returns: {"content": str, "tool_calls": list|None}
        """
        raise NotImplementedError


class OllamaBackend(ModelBackend):
    """Local model served by Ollama, via its OpenAI-compatible endpoint."""

    def __init__(self, model: str = "qwen3:4b", host: str = "http://localhost:11434"):
        self.model = model
        self.url = f"{host}/v1/chat/completions"
        # Check if the model supports tools by querying the Ollama API for model details.
        details = requests.post(
            f"{host}/api/show",
            json={"model": self.model},
            timeout=10,
        ).json()
        # Extract the list of capabilities from the model details.
        capabilities = details.get("capabilities", [])
        # Check if the model supports tools. 
        # Ollama's API returns a list of capabilities, 
        # and "tools" is one of them if the model can handle tool calls.
        if "tools" not in capabilities:
            raise RuntimeError(
                f"Model '{self.model}' does not support tools. "
                f"Capabilities: {', '.join(capabilities) or 'none'}."
            )

    def chat(self, messages: list, tools: list = None) -> dict:
        
        
        payload = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools

        resp = requests.post(self.url, json=payload, timeout=120)
        resp.raise_for_status()
        if resp.status_code != 200:
            raise requests.exceptions.HTTPError(f"""
            Ollama API error: {resp.status_code} {resp.text}
(^_^)/ yo, looks like the model you selected may not be capable of tool calls.
 Try a different model or remove the tools argument.""")
        data = resp.json()

        choice = data["choices"][0]["message"]
        return {
            "content": choice.get("content") or "",
            "tool_calls": choice.get("tool_calls"),
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

    def chat(self, messages: list, tools: list = None) -> dict:
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
    "ollama-qwen3-coder": lambda: OllamaBackend(model="qwen3-coder:latest"),
    "ollama-embed4gemma": lambda: OllamaBackend(model="embeddinggemma:latest"),
    "ollama": lambda: OllamaBackend(model="gemma3:4b"),
    "claude": lambda: ClaudeBackend(model="claude-sonnet-5"),
}


def get_backend(name: str) -> ModelBackend:
    if name not in BACKENDS:
        raise ValueError(f"Unknown backend '{name}'. Choose from: {list(BACKENDS)}")
    return BACKENDS[name]()
