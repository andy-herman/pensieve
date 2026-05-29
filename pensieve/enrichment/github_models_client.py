"""GitHub Models chat client — OpenAI-compatible /chat/completions.

For personal-device installs where Azure OpenAI Cortex hub is not available.
Auth is a GitHub PAT with the `models:read` scope. Free tier exists; rate
limits are documented at https://docs.github.com/en/github-models.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from pensieve.config import Settings


class GitHubModelsChatClient:
    """Thin OpenAI-compatible chat client backed by GitHub Models.

    Matches the surface of ``AzureOpenAIChatClient.chat()`` so call sites
    can depend on a duck-typed ``.chat()`` contract.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        if not settings.github_token:
            raise ValueError(
                "GITHUB_TOKEN is not set. Generate a PAT with `models:read` scope "
                "(https://github.com/settings/personal-access-tokens/new) and add it "
                "to .env as GITHUB_TOKEN=<pat>."
            )
        if not settings.github_models_model:
            raise ValueError("GITHUB_MODELS_MODEL is not set (e.g. 'gpt-4o' or 'openai/gpt-4o').")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self) -> str:
        base = self.settings.github_models_base_url.rstrip("/")
        return f"{base}/chat/completions"

    def chat(
        self,
        messages: list[dict[str, str]],
        max_output_tokens: int = 1500,
        response_format: Optional[str] = "json_object",
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.settings.github_models_model,
            "messages": messages,
            "max_tokens": max_output_tokens,
        }
        if response_format:
            body["response_format"] = {"type": response_format}

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(self._url(), headers=self._headers(), json=body)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"GitHub Models call failed [{resp.status_code}]: {resp.text}"
                )
            return resp.json()
