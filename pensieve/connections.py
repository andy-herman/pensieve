"""Account connections behind the dashboard's "Connect your accounts" screen.

Each person runs their own Pensieve and connects their own accounts on their
own machine; nothing is hosted and nobody else ever holds their tokens.

- Microsoft To Do (personal Microsoft account): Microsoft Graph via MSAL's
  device-code flow, ``Tasks.ReadWrite`` (read, plus voice capture's confirmed create). The token cache is encrypted
  with Windows DPAPI (msal-extensions), so only this Windows user can read it.
  Needs the public client id of a Pensieve app registration
  (``PERSONAL_GRAPH_CLIENT_ID``); see desktop/SHARING.md.
- GitHub Copilot: the Copilot CLI's own ``copilot login --device-code``
  (GitHub's official Copilot app). The CLI stores the token in Windows
  Credential Manager, and the Copilot SDK picks it up.

Non-secret choices (which task source to sync) live in
``<data_dir>/connections.json``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

from pensieve.config import Settings

CONFIG_FILE = "connections.json"
GRAPH_CACHE_FILE = "ms-token-cache.bin"
SOURCES = ("personal_graph", "outlook_com", "sample_file")

_lock = threading.Lock()


class NotConnected(RuntimeError):
    """The account this operation needs has not been connected (or has expired)."""


# ----- non-secret user config -------------------------------------------------


def _config_path(settings: Settings) -> Path:
    return Path(settings.data_dir) / CONFIG_FILE


def load_config(settings: Settings) -> dict[str, Any]:
    try:
        with _config_path(settings).open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(settings: Settings, **updates: Any) -> dict[str, Any]:
    with _lock:
        data = load_config(settings)
        data.update(updates)
        p = _config_path(settings)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, p)
        return data


def effective_source(settings: Settings) -> str:
    """Task source to sync: the one chosen in the app, else .env, else Outlook COM."""
    chosen = load_config(settings).get("source")
    if chosen in SOURCES:
        return str(chosen)
    return (settings.default_source or "outlook_com").strip()


# ----- Microsoft To Do (MSAL device flow) ------------------------------------

_MSAL_APPS: dict[tuple[str, str], Any] = {}
_FLOWS: dict[str, dict[str, Any]] = {}


def _graph_cache(settings: Settings) -> Any:
    path = Path(settings.data_dir) / GRAPH_CACHE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    from msal_extensions import PersistedTokenCache, build_encrypted_persistence

    # DPAPI on Windows; raises where no encryption is available rather than
    # silently writing refresh tokens in plain text.
    return PersistedTokenCache(build_encrypted_persistence(str(path)))


def _msal_app(settings: Settings) -> Any:
    client_id = (settings.personal_graph_client_id or "").strip()
    if not client_id:
        raise NotConnected(
            "This copy of Pensieve has no Microsoft app id yet (PERSONAL_GRAPH_CLIENT_ID). "
            "See desktop/SHARING.md."
        )
    key = (client_id, str(Path(settings.data_dir).resolve()))
    with _lock:
        app = _MSAL_APPS.get(key)
        if app is None:
            import msal

            app = msal.PublicClientApplication(
                client_id,
                authority=settings.personal_graph_authority,
                token_cache=_graph_cache(settings),
            )
            _MSAL_APPS[key] = app
        return app


def graph_token(settings: Settings) -> str:
    """Access token for Graph, silently from the cache. Never prompts."""
    app = _msal_app(settings)
    accounts = app.get_accounts()
    if not accounts:
        raise NotConnected("Connect your Microsoft account in Pensieve (More menu > Accounts).")
    result = app.acquire_token_silent(settings.personal_graph_scope_list(), account=accounts[0])
    if not result or "access_token" not in result:
        raise NotConnected("Microsoft sign-in has expired. Reconnect it in Pensieve (More menu > Accounts).")
    return str(result["access_token"])


def _public_flow(flow: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not flow:
        return None
    return {k: flow.get(k) for k in ("state", "user_code", "verification_uri", "expires_at", "error", "account")}


def start_microsoft(settings: Settings) -> dict[str, Any]:
    """Begin the device-code sign-in; completion is picked up in the background."""
    app = _msal_app(settings)
    cancel_flow("microsoft")
    flow = app.initiate_device_flow(scopes=settings.personal_graph_scope_list())
    if "user_code" not in flow:
        raise RuntimeError(f"Microsoft sign-in could not start: {flow.get('error_description', flow)}")
    state: dict[str, Any] = {
        "state": "pending",
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri", "https://microsoft.com/devicelogin"),
        "expires_at": int(flow.get("expires_at") or time.time() + 900),
        "_flow": flow,
    }
    _FLOWS["microsoft"] = state

    def finish() -> None:
        result = app.acquire_token_by_device_flow(flow)  # blocks until approved, declined or expired
        if state.get("state") != "pending":
            return  # cancelled meanwhile
        if "access_token" in result:
            accounts = app.get_accounts()
            state.update(state="connected", account=accounts[0].get("username") if accounts else None)
        else:
            state.update(state="error", error=result.get("error_description") or result.get("error") or "Sign-in failed.")

    threading.Thread(target=finish, daemon=True, name="pensieve-ms-signin").start()
    return _public_flow(state) or {}


def microsoft_status(settings: Settings) -> dict[str, Any]:
    out: dict[str, Any] = {"configured": bool((settings.personal_graph_client_id or "").strip())}
    flow = _FLOWS.get("microsoft")
    if not out["configured"]:
        out.update(connected=False, account=None, flow=None)
        return out
    try:
        accounts = _msal_app(settings).get_accounts()
    except Exception as e:  # cache unreadable, msal missing, ...
        out.update(connected=False, account=None, flow=None, error=str(e))
        return out
    out.update(
        connected=bool(accounts),
        account=accounts[0].get("username") if accounts else None,
        flow=_public_flow(flow) if flow and flow.get("state") in ("pending", "error") else None,
    )
    return out


def disconnect_microsoft(settings: Settings) -> None:
    cancel_flow("microsoft")
    app = _msal_app(settings)
    for account in app.get_accounts():
        app.remove_account(account)


# ----- GitHub Copilot (copilot login --device-code) --------------------------

_CODE = re.compile(r"\b([A-Z0-9]{4}-[A-Z0-9]{4})\b")
_URL = re.compile(r"https://github\.com/login/device\S*")
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def _copilot_cli(settings: Settings) -> str:
    from pensieve.enrichment.copilot_client import resolve_cli_path

    cli = resolve_cli_path(settings)
    if not cli:
        raise RuntimeError("The GitHub Copilot CLI was not found. Install it, or set COPILOT_CLI_PATH.")
    return cli


def start_github(settings: Settings) -> dict[str, Any]:
    """Run the Copilot CLI's device-code login and surface the code to the app."""
    cancel_flow("github")
    proc = subprocess.Popen(
        [_copilot_cli(settings), "login", "--device-code"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    state: dict[str, Any] = {"state": "starting", "expires_at": int(time.time() + 900), "_proc": proc}
    _FLOWS["github"] = state
    buf = bytearray()

    def pump() -> None:
        assert proc.stdout is not None
        while True:
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            buf.extend(chunk)
            text = _ANSI.sub("", buf.decode("utf-8", "replace"))
            if state.get("user_code") is None:
                m = _CODE.search(text)
                if m:
                    u = _URL.search(text)
                    state.update(
                        state="pending",
                        user_code=m.group(1),
                        verification_uri=u.group(0).rstrip(".,") if u else "https://github.com/login/device",
                    )
        code = proc.wait()
        if state.get("state") in ("cancelled",):
            return
        if code == 0:
            from pensieve.enrichment.copilot_client import reset_runtimes

            reset_runtimes()  # the next AI call starts a CLI that sees the new login
            _forget_auth()
            state.update(state="connected")
        else:
            tail = _ANSI.sub("", buf.decode("utf-8", "replace")).strip().splitlines()[-1:] or ["Sign-in failed."]
            state.update(state="error", error=tail[0][:200])

    threading.Thread(target=pump, daemon=True, name="pensieve-gh-signin").start()
    deadline = time.time() + 20  # the CLI prints the code within a few seconds
    while time.time() < deadline and state.get("state") == "starting":
        time.sleep(0.1)
    if state.get("state") == "starting":
        cancel_flow("github")
        raise RuntimeError("The Copilot CLI did not offer a sign-in code. Try again.")
    return _public_flow(state) or {}


def github_status(settings: Settings) -> dict[str, Any]:
    out: dict[str, Any] = {"provider": settings.llm_provider}
    if settings.llm_provider != "github_copilot":
        out.update(managed=True, connected=True, account=None, note=f"AI provider is {settings.llm_provider}.")
        return out
    if settings.copilot_github_user:
        out.update(managed=True, connected=True, account=settings.copilot_github_user,
                   note="Pinned in .env (COPILOT_GITHUB_USER).")
        return out
    flow = _FLOWS.get("github")
    if flow and flow.get("state") == "pending":
        out.update(managed=False, connected=False, account=None, flow=_public_flow(flow))
        return out
    info = _cached_auth_info(settings, wait=False)
    if info is None:
        # Not verified yet: answer instantly from the CLI's own record of who
        # is signed in, while the real check runs in the background.
        hint = _cli_login_hint()
        out.update(managed=False, connected=hint is not None, account=hint, verifying=True,
                   flow=_public_flow(flow) if flow and flow.get("state") == "error" else None)
        return out
    out.update(
        managed=False,
        connected=bool(info.get("authenticated")),
        account=info.get("login"),
        flow=_public_flow(flow) if flow and flow.get("state") == "error" else None,
    )
    if info.get("error") and not out["connected"]:
        out["detail"] = info["error"]
    return out


# Starting a Copilot CLI to ask "who is signed in" takes several seconds, so
# the answer is cached and refreshed in the background; connect and
# disconnect clear it.
_AUTH_TTL_S = 300.0
_auth_cache: dict[str, Any] = {"at": 0.0, "info": None, "checking": False}


def _cli_login_hint() -> Optional[str]:
    """Login the Copilot CLI last signed in as, from its config file (no process start)."""
    home = Path(os.environ.get("COPILOT_HOME") or (Path.home() / ".copilot"))
    try:
        raw = (home / "config.json").read_text(encoding="utf-8-sig")
        # The CLI writes JSON with full-line // comments; drop them before parsing.
        kept = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("//")]
        data = json.loads(chr(10).join(kept))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    last = (data.get("lastLoggedInUser") or {}).get("login")
    users = {u.get("login") for u in (data.get("loggedInUsers") or []) if isinstance(u, dict)}
    return last if last and last in users else None


def _cached_auth_info(settings: Settings, wait: bool = True) -> Optional[dict[str, Any]]:
    """Verified Copilot sign-in. With ``wait=False`` returns None and checks in the background."""
    now = time.monotonic()
    if _auth_cache["info"] is not None and now - _auth_cache["at"] < _AUTH_TTL_S:
        return _auth_cache["info"]
    from pensieve.enrichment.copilot_client import auth_info

    if wait:
        info = auth_info(settings)
        _auth_cache.update(at=time.monotonic(), info=info)
        return info
    with _lock:
        if _auth_cache["checking"]:
            return None
        _auth_cache["checking"] = True

    def check() -> None:
        try:
            info = auth_info(settings)
            _auth_cache.update(at=time.monotonic(), info=info)
        finally:
            _auth_cache["checking"] = False

    threading.Thread(target=check, daemon=True, name="pensieve-gh-check").start()
    return None


def _forget_auth() -> None:
    _auth_cache.update(at=0.0, info=None)


def disconnect_github(settings: Settings) -> None:
    cancel_flow("github")
    if settings.copilot_github_user:
        return  # pinned in .env; nothing stored by Pensieve to remove
    subprocess.run(
        [_copilot_cli(settings), "logout"],
        capture_output=True,
        timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    from pensieve.enrichment.copilot_client import reset_runtimes

    reset_runtimes()
    _forget_auth()


# ----- shared -----------------------------------------------------------------


def cancel_flow(provider: str) -> None:
    state = _FLOWS.pop(provider, None)
    if not state:
        return
    prior = state.get("state")
    state["state"] = "cancelled"
    flow = state.get("_flow")
    if flow is not None and prior == "pending":
        flow["expires_at"] = 0  # MSAL stops polling on its next tick
    proc = state.get("_proc")
    if proc is not None and proc.poll() is None:
        proc.kill()


def status(settings: Settings) -> dict[str, Any]:
    """Everything the Accounts screen needs in one call."""
    source = effective_source(settings)
    ms = microsoft_status(settings)
    gh = github_status(settings)
    tasks_ready = (source == "personal_graph" and ms.get("connected")) or source in ("outlook_com", "sample_file")
    return {
        "source": source,
        "microsoft": ms,
        "github": gh,
        "setup_complete": bool(tasks_ready and gh.get("connected")),
        "dismissed": bool(load_config(settings).get("setup_dismissed")),
    }
