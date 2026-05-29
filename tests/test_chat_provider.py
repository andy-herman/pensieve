"""Provider factory tests — no network calls."""

from __future__ import annotations

import pytest

from pensieve.config import Settings
from pensieve.enrichment.chat_provider import get_chat_client
from pensieve.enrichment.github_models_client import GitHubModelsChatClient
from pensieve.enrichment.llm_client import AzureOpenAIChatClient


def _azure_settings(**overrides) -> Settings:
    base = {
        "llm_provider": "azure_openai",
        "azure_openai_endpoint": "https://example.cognitiveservices.azure.com/",
        "azure_openai_deployment": "gpt-5.4-2",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _github_settings(**overrides) -> Settings:
    base = {
        "llm_provider": "github_models",
        "github_token": "ghp_test_token",
        "github_models_model": "openai/gpt-4o-mini",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_factory_returns_azure_by_default():
    s = _azure_settings()
    c = get_chat_client(s)
    assert isinstance(c, AzureOpenAIChatClient)


def test_factory_returns_github_models_when_configured():
    s = _github_settings()
    c = get_chat_client(s)
    assert isinstance(c, GitHubModelsChatClient)


def test_factory_rejects_unknown_provider():
    """Factory's defensive check (the typed Literal already prevents this at the
    Settings level, but the factory still guards in case someone constructs a
    raw object or extends the enum without updating the factory)."""
    class _StubSettings:
        llm_provider = "ollama"

    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        get_chat_client(_StubSettings())  # type: ignore[arg-type]


def test_github_models_requires_token():
    s = _github_settings(github_token="")
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        GitHubModelsChatClient(s)


def test_github_models_requires_model():
    s = _github_settings(github_models_model="")
    with pytest.raises(ValueError, match="GITHUB_MODELS_MODEL"):
        GitHubModelsChatClient(s)


def test_github_models_url_and_headers():
    s = _github_settings()
    c = GitHubModelsChatClient(s)
    assert c._url().endswith("/chat/completions")
    assert "models.github.ai" in c._url()
    h = c._headers()
    assert h["Authorization"] == "Bearer ghp_test_token"
    assert h["Content-Type"] == "application/json"


def test_github_models_custom_base_url():
    s = _github_settings(github_models_base_url="https://example.com/v1/")
    c = GitHubModelsChatClient(s)
    assert c._url() == "https://example.com/v1/chat/completions"
