"""GitHub Copilot chat client, backed by the official GitHub Copilot SDK.

Every Pensieve LLM call (enrichment, goals import, Connect recaps, the
regenerate button) goes through ``get_chat_client()``. With
``LLM_PROVIDER=github_copilot`` that returns this client, which drives the
GitHub Copilot CLI over the SDK's JSON-RPC connection and bills against the
signed-in user's Copilot subscription.

Identity: set ``COPILOT_GITHUB_USER`` to the GitHub login whose Copilot
license should be used (for work data, the company-managed account). The
token comes from ``gh auth token --user <login>`` at runtime, so nothing
secret lives in ``.env``. ``COPILOT_GITHUB_TOKEN`` is an explicit-token
fallback; with neither set, the CLI's own stored login is used.

Safety: each call runs in a fresh, single-turn session with every tool
disabled, a deny-all permission handler, no custom instructions, skills,
memory, or config discovery, and the session is deleted afterwards. The model
only ever returns text; task content cannot make it act on the machine.

The SDK is async; Pensieve calls ``chat()`` from worker threads. One
background event loop owns a single CLI process for the whole Python process,
and ``chat()`` hands coroutines to it.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

from pensieve.config import Settings

# Appended to the system prompt when the caller wants a JSON object back.
# Copilot sessions have no response_format switch, so this is enforced by
# instruction plus the extraction in _extract_json().
_JSON_INSTRUCTION = (
    "\n\nRespond with a single valid JSON object only. "
    "No prose before or after it and no Markdown code fences."
)


class CopilotUnavailable(RuntimeError):
    """The Copilot runtime could not be started or authenticated."""


def _default_cli_path() -> Optional[str]:
    """The Copilot CLI's native binary from a global npm install, if present."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    base = Path(appdata) / "npm" / "node_modules" / "@github" / "copilot" / "node_modules" / "@github"
    for arch in ("win32-arm64", "win32-x64"):
        exe = base / f"copilot-{arch}" / "copilot.exe"
        if exe.is_file():
            return str(exe)
    return None


_TOKEN_TTL_S = 1800.0
_token_cache: dict[str, tuple[str, float]] = {}


def _token_for_user(login: str) -> str:
    cached = _token_cache.get(login)
    if cached and cached[1] > _now():
        return cached[0]
    token = _fetch_token_for_user(login)
    _token_cache[login] = (token, _now() + _TOKEN_TTL_S)
    return token


def _now() -> float:
    import time

    return time.monotonic()


def _fetch_token_for_user(login: str) -> str:
    try:
        out = subprocess.run(
            ["gh", "auth", "token", "--user", login],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as e:
        raise CopilotUnavailable("GitHub CLI (gh) is not installed or not on PATH.") from e
    token = (out.stdout or "").strip()
    if out.returncode != 0 or not token:
        raise CopilotUnavailable(
            f"No GitHub token for '{login}'. Run: gh auth login (and sign in as {login})."
        )
    return token


def _deny_all(request: Any, invocation: Any) -> Any:
    from copilot.generated.rpc import PermissionDecisionReject

    return PermissionDecisionReject(feedback="Tools are disabled for Pensieve.")


def _split_messages(messages: list[dict[str, str]], json_mode: bool) -> tuple[str, str]:
    """Flatten OpenAI-style messages into (system prompt, single user prompt)."""
    system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
    turns = [m for m in messages if m.get("role") != "system"]
    system = "\n\n".join(p for p in system_parts if p).strip() or "You are a helpful assistant."
    if json_mode:
        system += _JSON_INSTRUCTION
    if len(turns) == 1:
        prompt = turns[0].get("content", "")
    else:
        # Multi-turn history, replayed as a transcript for a one-shot session.
        lines = []
        for m in turns[:-1]:
            lines.append(f"[{m.get('role', 'user')}]\n{m.get('content', '')}")
        prompt = (
            "Conversation so far:\n\n" + "\n\n".join(lines) + "\n\n[user]\n" + turns[-1].get("content", "")
            if turns
            else ""
        )
    return system, prompt


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _extract_json(text: str) -> str:
    """Return the JSON object in ``text`` (tolerates code fences or stray prose)."""
    t = (text or "").strip()
    m = _FENCE.match(t)
    if m:
        t = m.group(1).strip()
    try:
        json.loads(t)
        return t
    except ValueError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        candidate = t[start : end + 1]
        try:
            json.loads(candidate)
            return candidate
        except ValueError:
            pass
    return t  # let the caller's json.loads raise with the real content


class _CopilotRuntime:
    """One Copilot CLI process plus the event loop that talks to it."""

    def __init__(self, github_token: Optional[str], cli_path: Optional[str]) -> None:
        self._github_token = github_token
        self._cli_path = cli_path
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="pensieve-copilot")
        self._thread.start()
        self._client: Any = None
        self._start_lock: Optional[asyncio.Lock] = None
        # Sessions start in an empty scratch folder, never the repo or data dir.
        self._workdir = str(Path(tempfile.gettempdir()) / "pensieve-copilot")
        os.makedirs(self._workdir, exist_ok=True)

    def run(self, coro: Any, timeout: float) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def shutdown(self, timeout: float = 15.0) -> None:
        """Stop the CLI process and the event loop thread."""

        async def stop() -> None:
            client, self._client = self._client, None
            if client is not None:
                try:
                    await client.force_stop()
                except Exception:
                    pass

        try:
            self.run(stop(), timeout)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    async def client(self) -> Any:
        if self._client is not None:
            return self._client
        if self._start_lock is None:
            self._start_lock = asyncio.Lock()
        async with self._start_lock:
            if self._client is None:
                try:
                    from copilot import CopilotClient, RuntimeConnection
                except ImportError as e:
                    raise CopilotUnavailable(
                        "github-copilot-sdk is not installed. Run: pip install github-copilot-sdk"
                    ) from e
                kwargs: dict[str, Any] = {"log_level": "error", "working_directory": self._workdir}
                if self._cli_path:
                    kwargs["connection"] = RuntimeConnection.for_stdio(path=self._cli_path)
                if self._github_token:
                    kwargs["github_token"] = self._github_token
                    kwargs["use_logged_in_user"] = False
                client = CopilotClient(**kwargs)
                try:
                    await client.start()
                    status = await client.get_auth_status()
                except Exception as e:
                    raise CopilotUnavailable(f"Could not start GitHub Copilot: {e}") from e
                if not getattr(status, "isAuthenticated", True):
                    await client.stop()
                    raise CopilotUnavailable(
                        f"GitHub Copilot is not authenticated ({getattr(status, 'statusMessage', '')})."
                    )
                self._client = client
        return self._client

    async def _reset(self, dead: Any) -> None:
        """Forget a dead CLI connection so the next call starts a fresh one."""
        if self._client is not dead:
            return  # another caller already replaced it
        self._client = None
        try:
            await dead.force_stop()
        except Exception:
            pass

    async def _call(self, op: Any) -> Any:
        """Run ``op(client)``; if the CLI process has died, restart it once and retry."""
        client = await self.client()
        try:
            return await op(client)
        except Exception:
            try:
                await asyncio.wait_for(client.ping(), 5.0)
            except Exception:
                await self._reset(client)
                return await op(await self.client())
            raise  # the CLI is alive, so this is a real error

    async def models(self) -> list[dict[str, Any]]:
        listed = await self._call(lambda c: c.list_models())
        out = []
        for m in listed:
            d = m.to_dict()
            if d.get("id") == "auto":
                continue
            limits = (d.get("capabilities") or {}).get("limits") or {}
            out.append(
                {
                    "id": d.get("id"),
                    "name": d.get("name") or d.get("id"),
                    "enabled": ((d.get("policy") or {}).get("state") or "enabled") == "enabled",
                    "context_tokens": limits.get("maxContextWindowTokens"),
                }
            )
        return out

    async def ask(self, model: str, system: str, prompt: str, timeout: float) -> tuple[str, dict[str, int], str]:
        async def open_session(c: Any) -> tuple[Any, Any]:
            return c, await c.create_session(
                model=model or None,
                available_tools=[],
                on_permission_request=_deny_all,
                system_message={"mode": "replace", "content": system},
                working_directory=self._workdir,
                skip_custom_instructions=True,
                enable_config_discovery=False,
                enable_skills=False,
                enable_session_store=False,
                enable_session_telemetry=False,
                skip_embedding_retrieval=True,
            )

        client, session = await self._call(open_session)
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        used_model = {"name": model}

        def on_event(event: Any) -> None:
            etype = getattr(getattr(event, "type", None), "value", getattr(event, "type", None))
            if etype == "assistant.usage":
                data = getattr(event, "data", None)
                usage["prompt_tokens"] += int(getattr(data, "input_tokens", 0) or 0)
                usage["completion_tokens"] += int(getattr(data, "output_tokens", 0) or 0)
                used_model["name"] = getattr(data, "model", None) or used_model["name"]

        unsubscribe = session.on(on_event)
        try:
            event = await session.send_and_wait(prompt, timeout=timeout)
        finally:
            unsubscribe()
            sid = getattr(session, "session_id", None)
            try:
                await session.disconnect()
            except Exception:
                pass
            if sid:
                try:
                    await client.delete_session(sid)
                except Exception:
                    pass
        content = getattr(getattr(event, "data", None), "content", None)
        if content is None:
            raise RuntimeError("GitHub Copilot returned no reply (timed out or the session ended early).")
        return str(content), usage, str(used_model["name"] or "")


_RUNTIMES: dict[tuple[Optional[str], Optional[str]], _CopilotRuntime] = {}
_RUNTIMES_LOCK = threading.Lock()


def resolve_cli_path(settings: Settings) -> Optional[str]:
    """Copilot CLI binary: COPILOT_CLI_PATH setting/env, else the global npm install."""
    return settings.copilot_cli_path or os.environ.get("COPILOT_CLI_PATH") or _default_cli_path()


def _runtime_for(settings: Settings) -> _CopilotRuntime:
    if settings.copilot_github_user:
        token: Optional[str] = _token_for_user(settings.copilot_github_user)
    else:
        token = settings.copilot_github_token or None
    cli_path = resolve_cli_path(settings)
    key = (token, cli_path)
    with _RUNTIMES_LOCK:
        rt = _RUNTIMES.get(key)
        if rt is None:
            rt = _CopilotRuntime(token, cli_path)
            _RUNTIMES[key] = rt
        return rt


def reset_runtimes() -> None:
    """Stop every Copilot CLI this process started (e.g. after a new login)."""
    with _RUNTIMES_LOCK:
        runtimes = list(_RUNTIMES.values())
        _RUNTIMES.clear()
    for rt in runtimes:
        rt.shutdown()


def auth_info(settings: Settings, timeout: float = 90.0) -> dict[str, Any]:
    """Who Copilot is signed in as: ``{"authenticated", "login", "error"?}``."""
    try:
        rt = _runtime_for(settings)

        async def check() -> dict[str, Any]:
            client = await rt.client()
            st = await client.get_auth_status()
            return {"authenticated": bool(st.isAuthenticated), "login": st.login}

        return rt.run(check(), timeout)
    except Exception as e:  # not signed in, CLI missing, timeout
        return {"authenticated": False, "login": None, "error": str(e)}


class CopilotChatClient:
    """Same ``.chat()`` contract as AzureOpenAIChatClient, served by GitHub Copilot.

    ``purpose`` selects which in-app model choice applies (see pensieve.ai_prefs);
    the model is resolved on every call, so a change in the dashboard takes
    effect on the next request.
    """

    def __init__(self, settings: Settings, purpose: str = "enrichment") -> None:
        self.settings = settings
        self.purpose = purpose
        self._runtime = _runtime_for(settings)

    def current_model(self) -> str:
        from pensieve import ai_prefs

        return ai_prefs.model_for(self.settings, self.purpose)

    def list_models(self, timeout: float = 120.0) -> list[dict[str, Any]]:
        """Models the signed-in Copilot account can use (cached by the SDK)."""
        return self._runtime.run(self._runtime.models(), timeout)

    def ping(self, model: str, timeout: float = 90.0) -> dict[str, Any]:
        """One tiny call to prove ``model`` answers for this account."""
        import time

        t0 = time.monotonic()
        content, usage, used = self._runtime.run(
            self._runtime.ask(
                model,
                "You are a connectivity check. Reply with the single word OK.",
                "Reply with OK.",
                timeout,
            ),
            timeout + 30.0,
        )
        return {
            "ok": "ok" in content.lower(),
            "model": used or model,
            "reply": content.strip()[:80],
            "seconds": round(time.monotonic() - t0, 2),
            "tokens": usage["prompt_tokens"] + usage["completion_tokens"],
        }

    def warm(self, timeout: float = 120.0) -> None:
        """Start the Copilot CLI ahead of the first real call (startup takes several seconds)."""
        self._runtime.run(self._runtime.client(), timeout)

    def chat(
        self,
        messages: list[dict[str, str]],
        max_output_tokens: int = 1500,
        response_format: Optional[str] = "json_object",
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        # max_output_tokens has no per-call equivalent in a Copilot session; the
        # prompts already bound their output, so it is accepted and ignored.
        json_mode = response_format == "json_object"
        system, prompt = _split_messages(messages, json_mode)
        # Copilot models can take longer than Azure's single completion; give the
        # session a floor so short caller timeouts do not cut off normal replies.
        session_timeout = max(timeout, 90.0)
        content, usage, model = self._runtime.run(
            self._runtime.ask(self.current_model(), system, prompt, session_timeout),
            session_timeout + 60.0,
        )
        if json_mode:
            content = _extract_json(content)
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        return {
            "model": model,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
            "usage": usage,
        }
