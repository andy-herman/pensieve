"""Azure OpenAI chat client. Port of scripts/lib/Invoke-AzureOpenAI.ps1."""

from __future__ import annotations

from typing import Any, Optional

import httpx
from azure.identity import DefaultAzureCredential

from pensieve.config import Settings

# Models that require max_completion_tokens instead of max_tokens
_MAX_COMPLETION_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _uses_max_completion_tokens(deployment: str) -> bool:
    name = (deployment or "").lower()
    return any(name.startswith(p) for p in _MAX_COMPLETION_PREFIXES)


class AzureOpenAIChatClient:
    """Thin Azure OpenAI chat-completions client.

    Auth precedence mirrors the PowerShell shim:
      1. AZURE_OPENAI_API_KEY if set (and not the placeholder)
      2. Otherwise AAD bearer via DefaultAzureCredential
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._cred: Optional[DefaultAzureCredential] = None

        if not settings.azure_openai_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is not set. Add it to .env or environment.")
        if not settings.azure_openai_deployment:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT is not set.")

    @property
    def _use_api_key(self) -> bool:
        key = self.settings.azure_openai_api_key
        return bool(key) and key != "REPLACE_WITH_KEY_FROM_AZURE_PORTAL"

    def _get_token(self) -> str:
        if self._cred is None:
            self._cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
        scope = self.settings.azure_openai_token_scope
        token = self._cred.get_token(scope)
        return token.token

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
