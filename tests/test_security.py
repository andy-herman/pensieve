"""Local API hardening: the per-launch session token and security headers."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pensieve.api.server import create_app
from pensieve.config import get_settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PENSIEVE_SESSION_TOKEN", "s3cret-token")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_api_refuses_calls_without_the_token(client):
    assert client.get("/api/memories").status_code == 401
    assert client.get("/api/session/check").status_code == 401


def test_healthz_stays_open_for_the_splash(client):
    r = client.get("/api/healthz")
    assert r.status_code == 200
    assert "chroma_dir" not in r.json()


def test_launcher_header_is_accepted(client):
    r = client.get("/api/session/check", headers={"X-Pensieve-Token": "s3cret-token"})
    assert r.status_code == 200


def test_one_time_link_sets_the_cookie_and_strips_the_token(client):
    r = client.get("/?t=s3cret-token", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/session/check").status_code == 200


def test_wrong_link_token_is_refused(client):
    assert client.get("/?t=nope", follow_redirects=False).status_code == 401
    assert client.get("/api/session/check").status_code == 401


def test_other_host_names_are_refused(client):
    r = client.get("/api/healthz", headers={"Host": "evil.example"})
    assert r.status_code == 400


def test_pages_carry_a_strict_script_policy(client):
    r = client.get("/legal.html")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_shipped_pages_have_no_inline_scripts():
    import re

    from pensieve.config import REPO_ROOT

    for name in ("index.html", "legal.html"):
        html = (REPO_ROOT / "frontend-proto" / name).read_text(encoding="utf-8")
        for tag in re.findall(r"<script\b[^>]*>", html):
            assert "src=" in tag, f"{name} has an inline <script>; the CSP would block it"
        assert not re.search(r"\son[a-z]+=", html), f"{name} has an inline event handler"
