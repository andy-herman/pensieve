"""Accounts / first-run connections: no real Microsoft or GitHub sign-in."""

from __future__ import annotations

import os
import threading
import time

import pytest
from fastapi.testclient import TestClient

from pensieve import connections
from pensieve.api.server import create_app
from pensieve.config import Settings, get_settings


def _settings(tmp_path, **kw) -> Settings:
    base = {"PENSIEVE_DATA_DIR": str(tmp_path), "COPILOT_GITHUB_USER": "", "PERSONAL_GRAPH_CLIENT_ID": "test-app-id"}
    base.update(kw)
    return Settings(_env_file=None, **base)


@pytest.fixture(autouse=True)
def _clean_flows():
    connections._FLOWS.clear()
    connections._forget_auth()
    yield
    for p in list(connections._FLOWS):
        connections.cancel_flow(p)
    connections._forget_auth()


# ----- config / source -----


def test_effective_source_prefers_in_app_choice(tmp_path):
    s = _settings(tmp_path, PENSIEVE_DEFAULT_SOURCE="outlook_com")
    assert connections.effective_source(s) == "outlook_com"
    connections.save_config(s, source="personal_graph")
    assert connections.effective_source(s) == "personal_graph"
    connections.save_config(s, source="nonsense")
    assert connections.effective_source(s) == "outlook_com"


# ----- Microsoft -----


class _FakeMsal:
    def __init__(self):
        self.accounts: list[dict] = []
        self.approve = threading.Event()

    def get_accounts(self):
        return list(self.accounts)

    def initiate_device_flow(self, scopes):
        return {"user_code": "ABCD1234", "verification_uri": "https://microsoft.com/devicelogin",
                "expires_at": time.time() + 600}

    def acquire_token_by_device_flow(self, flow):
        while not self.approve.is_set():
            if flow.get("expires_at", 1) == 0:
                return {"error": "authorization_declined"}
            time.sleep(0.01)
        self.accounts = [{"username": "friend@outlook.com"}]
        return {"access_token": "t"}

    def acquire_token_silent(self, scopes, account):
        return {"access_token": "graph-token"} if self.accounts else None

    def remove_account(self, account):
        self.accounts.remove(account)


@pytest.fixture
def fake_msal(monkeypatch):
    fake = _FakeMsal()
    monkeypatch.setattr(connections, "_msal_app", lambda settings: fake)
    return fake


def _wait(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_microsoft_unconfigured_reports_missing_app_id(tmp_path):
    st = connections.microsoft_status(_settings(tmp_path, PERSONAL_GRAPH_CLIENT_ID=""))
    assert st == {"configured": False, "connected": False, "account": None, "flow": None}


def test_graph_token_requires_connection(tmp_path, fake_msal):
    with pytest.raises(connections.NotConnected, match="Connect your Microsoft account"):
        connections.graph_token(_settings(tmp_path))


def test_microsoft_device_flow_connects(tmp_path, fake_msal):
    s = _settings(tmp_path)
    started = connections.start_microsoft(s)
    assert started["state"] == "pending" and started["user_code"] == "ABCD1234"
    assert connections.microsoft_status(s)["flow"]["user_code"] == "ABCD1234"
    fake_msal.approve.set()
    assert _wait(lambda: connections.microsoft_status(s)["connected"])
    assert connections.microsoft_status(s)["account"] == "friend@outlook.com"
    assert connections.graph_token(s) == "graph-token"
    connections.disconnect_microsoft(s)
    assert connections.microsoft_status(s)["connected"] is False


def test_cancel_stops_a_pending_microsoft_flow(tmp_path, fake_msal):
    s = _settings(tmp_path)
    connections.start_microsoft(s)
    connections.cancel_flow("microsoft")
    assert connections.microsoft_status(s)["flow"] is None
    assert connections.microsoft_status(s)["connected"] is False


# ----- GitHub -----


class _FakeProc:
    """Popen stand-in whose stdout is a real pipe (the pump uses os.read)."""

    def __init__(self, text: str, exit_code: int, hold: threading.Event):
        r, w = os.pipe()
        self.stdout = os.fdopen(r, "rb")
        self._w = w
        self._code = exit_code
        self._hold = hold
        self._done = False
        os.write(w, text.encode())
        threading.Thread(target=self._finish, daemon=True).start()

    def _finish(self):
        self._hold.wait(5)
        os.close(self._w)
        self._done = True

    def poll(self):
        return self._code if self._done else None

    def wait(self, timeout=None):
        end = time.time() + (timeout or 10)
        while not self._done and time.time() < end:
            time.sleep(0.01)
        return self._code

    def kill(self):
        self._hold.set()


def test_github_device_login_surfaces_code_then_connects(tmp_path, monkeypatch):
    s = _settings(tmp_path)
    hold = threading.Event()
    prompt = "To authenticate, visit https://github.com/login/device and enter code WXYZ-9876\nWaiting...\n"
    monkeypatch.setattr(connections, "_copilot_cli", lambda settings: "copilot.exe")
    monkeypatch.setattr(connections.subprocess, "Popen", lambda *a, **k: _FakeProc(prompt, 0, hold))
    monkeypatch.setattr("pensieve.enrichment.copilot_client.reset_runtimes", lambda: None)
    monkeypatch.setattr(connections, "_cached_auth_info",
                        lambda settings, wait=True: {"authenticated": hold.is_set(), "login": "friend-gh" if hold.is_set() else None})

    started = connections.start_github(s)
    assert started["user_code"] == "WXYZ-9876"
    assert started["verification_uri"] == "https://github.com/login/device"
    assert connections.github_status(s)["flow"]["state"] == "pending"

    hold.set()  # user approves; the CLI exits 0
    assert _wait(lambda: connections._FLOWS["github"]["state"] == "connected")
    st = connections.github_status(s)
    assert st["connected"] is True and st["account"] == "friend-gh"


def test_github_pinned_account_is_managed(tmp_path):
    st = connections.github_status(_settings(tmp_path, COPILOT_GITHUB_USER="work-login"))
    assert st["managed"] is True and st["connected"] is True and st["account"] == "work-login"


# ----- API -----


@pytest.fixture
def api(tmp_path, monkeypatch, fake_msal):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_ENABLED", "false")
    monkeypatch.setenv("COPILOT_GITHUB_USER", "")
    monkeypatch.setenv("PERSONAL_GRAPH_CLIENT_ID", "test-app-id")
    monkeypatch.setenv("PENSIEVE_DEFAULT_SOURCE", "outlook_com")
    monkeypatch.setattr(connections, "_cached_auth_info", lambda settings, wait=True: {"authenticated": False, "login": None})
    get_settings.cache_clear()  # type: ignore[attr-defined]
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_api_status_source_and_finish(api, fake_msal):
    st = api.get("/api/connect").json()
    assert st["source"] == "outlook_com" and st["setup_complete"] is False and st["dismissed"] is False
    assert api.put("/api/connect/source", json={"source": "personal_graph"}).json()["source"] == "personal_graph"
    assert api.put("/api/connect/source", json={"source": "bogus"}).status_code == 400
    assert api.post("/api/connect/finish").json()["dismissed"] is True
    assert api.get("/api/healthz").json()["default_source"] == "personal_graph"


def test_api_microsoft_start_and_cancel(api, fake_msal):
    body = api.post("/api/connect/microsoft/start").json()
    assert body["user_code"] == "ABCD1234"
    assert api.post("/api/connect/microsoft/cancel").json()["microsoft"]["flow"] is None
    assert api.post("/api/connect/nope/start").status_code == 404


def test_cli_login_hint_reads_commented_config(tmp_path, monkeypatch):
    lines = [
        "// User settings",
        "// more comments",
        '{"lastLoggedInUser": {"login": "friend-gh"},',
        ' "loggedInUsers": [{"host": "https://github.com", "login": "friend-gh"}]}',
    ]
    (tmp_path / "config.json").write_text(chr(10).join(lines), encoding="utf-8")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path))
    assert connections._cli_login_hint() == "friend-gh"
    (tmp_path / "config.json").write_text('{"loggedInUsers": []}', encoding="utf-8")
    assert connections._cli_login_hint() is None
