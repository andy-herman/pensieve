"""Azure OpenAI chat client. Port of scripts/lib/Invoke-AzureOpenAI.ps1."""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

import httpx
from azure.identity import DefaultAzureCredential

from pensieve.config import Settings

# Models that require max_completion_tokens instead of max_tokens
_MAX_COMPLETION_PREFIXES = ("gpt-5", "o1", "o3", "o4")

# Shared token cache across all client instances and worker threads.
# DefaultAzureCredential is thread-safe for cached token reads, but parallel
# get_token() calls during first-acquisition can race the InteractiveBrowser
# OAuth state. Serialize first-acquisition and reuse the token until expiry.
_TOKEN_LOCK = threading.Lock()
_TOKEN_CACHE: dict[str, tuple[str, float]] = {}  # scope -> (token, expires_on_epoch)
_SHARED_CRED: Optional[DefaultAzureCredential] = None


def _get_shared_token(scope: str) -> str:
    """Get a bearer token for the given scope, with a thread-safe cache."""
    global _SHARED_CRED
    now = time.time()
    cached = _TOKEN_CACHE.get(scope)
    if cached and cached[1] - now > 60:
        return cached[0]
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(scope)
        if cached and cached[1] - now > 60:
            return cached[0]
        if _SHARED_CRED is None:
            _SHARED_CRED = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        tok = _SHARED_CRED.get_token(scope)
        _TOKEN_CACHE[scope] = (tok.token, float(tok.expires_on))
        return tok.token


def _uses_max_completion_tokens(deployment: str) -> bool:
    name = (deployment or "").lower()
    return any(name.startswith(p) for p in _MAX_COMPLETION_PREFIXES)


class AzureOpenAIChatClient:
    """Thin Azure OpenAI chat-completions client.

    Auth precedence mirrors the PowerShell shim:
      1. AZURE_OPENAI_API_KEY if set (and not the placeholder)
      2. Otherwise AAD bearer via DefaultAzureCredential (shared, cached, thread-safe)
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        if not settings.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is not set. Add it to .env or environment.")
        if not settings.azure_openai_deployment:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT is not set.")

    @property
    def _use_api_key(self) -> bool:
        key = self.settings.azure_openai_api_key
        return bool(key) and key != "REPLACE_WITH_KEY_FROM_AZURE_PORTAL"

    def _get_token(self) -> str:
        return _get_shared_token(self.settings.azure_openai_token_scope)

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._use_api_key:
            h["api-key"] = self.settings.azure_openai_api_key
        else:
            h["Authorization"] = f"Bearer {self._get_token()}"
        return h

    def _url(self) -> str:
        endpoint = self.settings.azure_openai_endpoint.rstrip("/")
        return (
            f"{endpoint}/openai/deployments/{self.settings.azure_openai_deployment}"
            f"/chat/completions?api-version={self.settings.azure_openai_api_version}"
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        max_output_tokens: int = 1500,
        response_format: Optional[str] = "json_object",
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"messages": messages}
        if _uses_max_completion_tokens(self.settings.azure_openai_deployment):
            body["max_completion_tokens"] = max_output_tokens
        else:
            body["max_tokens"] = max_output_tokens
        if response_format:
            body["response_format"] = {"type": response_format}

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(self._url(), headers=self._headers(), json=body)
            if resp.status_code >= 400:
                raise RuntimeError(f"Azure OpenAI call failed [{resp.status_code}]: {resp.text}")
            return resp.json()
