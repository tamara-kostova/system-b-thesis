"""
LLM provider abstraction. All three providers share the same interface so
the rest of the gateway never needs to know which one is active.

Ollama uses OpenAI's client pointed at localhost — no extra SDK needed.
"""

from abc import ABC, abstractmethod
from typing import Any

from .config import settings


class Message(dict):
    """Simple typed alias for a chat message dict."""


class LLMResponse:
    def __init__(self, content: str, tool_calls: list[dict] | None = None):
        self.content = content
        self.tool_calls = tool_calls or []


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse: ...

    @property
    @abstractmethod
    def model(self) -> str: ...


class AnthropicProvider(LLMProvider):
    def __init__(self):
        import anthropic
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @property
    def model(self) -> str:
        return settings.anthropic_model

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text = block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return LLMResponse(content=content_text, tool_calls=tool_calls)


class _OpenAICompatibleProvider(LLMProvider):
    """Shared implementation for OpenAI and Ollama (same client, different base_url)."""

    def __init__(self, api_key: str, base_url: str | None, model: str):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key or "ollama", base_url=base_url)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str | None = None,
    ) -> LLMResponse:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        kwargs: dict[str, Any] = {"model": self.model, "messages": all_messages}
        if tools:
            # Convert Anthropic-style tool defs to OpenAI format if needed
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0].message

        tool_calls = []
        if choice.tool_calls:
            import json
            for tc in choice.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                })

        return LLMResponse(content=choice.content or "", tool_calls=tool_calls)


class OpenAIProvider(_OpenAICompatibleProvider):
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        super().__init__(
            api_key=settings.openai_api_key,
            base_url=None,
            model=settings.openai_model,
        )


class OllamaProvider(_OpenAICompatibleProvider):
    def __init__(self):
        super().__init__(
            api_key="ollama",
            base_url=f"{settings.ollama_base_url}/v1",
            model=settings.ollama_model,
        )


def get_provider() -> LLMProvider:
    match settings.llm_provider:
        case "anthropic":
            return AnthropicProvider()
        case "openai":
            return OpenAIProvider()
        case "ollama":
            return OllamaProvider()
        case _:
            raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")


def _to_openai_tool(tool: dict) -> dict:
    """Normalize an Anthropic-style tool definition to OpenAI format."""
    if "input_schema" in tool:
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool["input_schema"],
            },
        }
    # Already OpenAI format
    return tool
