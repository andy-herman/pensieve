"""Factory for the chat client. Returns the configured LLM provider.

Both clients implement the same duck-typed surface:

    client.chat(messages, max_output_tokens=..., response_format=..., timeout=...)
        -> dict (OpenAI-style /chat/completions response)

Provider is selected by ``settings.llm_provider``:
  - "azure_openai" (default) — Cortex hub via DefaultAzureCredential
  - "github_models" — GitHub Models via a PAT (personal-device installs)
"""

from __future__ import annotations

from typing import Any, Protocol

from pensieve.config import Settings, get_settings


class ChatClient(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        max_output_tokens: int = 1500,
        response_format: str | None = "json_object",
        timeout: float = 60.0,
    ) -> dict[str, Any]: ...


def get_chat_client(settings: Settings | None = None) -> ChatClient:
    """Return the configured chat client. Lazy-imports so users don't pay for
    the provider they don't use."""
    s = settings or get_settings()
    provider = (s.llm_provider or "azure_openai").lower()

    if provider == "github_models":
        from pensieve.enrichment.github_models_client import GitHubModelsChatClient

        return GitHubModelsChatClient(s)

    if provider == "azure_openai":
        from pensieve.enrichment.llm_client import AzureOpenAIChatClient

        return AzureOpenAIChatClient(s)

    raise ValueError(
        f"Unknown LLM_PROVIDER: {provider!r}. Expected 'azure_openai' or 'github_models'."
    )
