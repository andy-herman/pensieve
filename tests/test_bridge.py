"""Vault bridge: Now.md for other agents and `to: pensieve` task requests (temp vault)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from pensieve import bridge
from pensieve.api.server import create_app
from pensieve.config import Settings, get_settings
from pensieve.store.schema import Memory

NOW = datetime.now(timezone.utc)


def _vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Agents" / "Hermes" / "Handoffs").mkdir(parents=True)
    (root / "Agents" / "Luna").mkdir(parents=True)
    return root


def _settings(tmp_path, root, **kw) -> Settings:
    return Settings(_env_file=None, PENSIEVE_DATA_DIR=str(tmp_path / "data"), PENSIEVE_VAULT_DIR=str(root), **kw)


def _mem(mid, title, column, list_name="Home", due=None, completed_at=None, why=""):
    return Memory(id=mid, source="outlook_com", source_task_id=mid, title=title, list_name=list_name,
                  column=column, due_date=due, completed_at=completed_at, completed=column == "closed", why=why)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ----- Now.md -----


def test_now_note_sections_filter_and_skip_unchanged(tmp_path):
    root = _vault(tmp_path)
    s = _settings(tmp_path, root, PENSIEVE_VAULT_LISTS="Home, CISO GRC")
    mems = [
        _mem("a", "Draft the risk summary", "dive", "CISO GRC", due=NOW - timedelta(days=2), why="Leadership asked"),
        _mem("b", "Book the venue", "memory", "Home", due=NOW + timedelta(days=3)),
        _mem("c", "Grade lab 3", "dive", "UW Lectures"),  # not shared
        _mem("d", "Ship the deck", "closed", "Home", completed_at=NOW - timedelta(days=1)),
    ]
    assert bridge.write_now(s, mems, {}) is True
    text = (root / "Agents" / "Pensieve" / "Now.md").read_text(encoding="utf-8")
    assert "do_not_touch: true" in text and "lists: ciso grc, home" in text
    assert "**[overdue] Draft the risk summary** (CISO GRC; due" in text and "Why: Leadership asked" in text
    assert "Book the venue" in text and "Ship the deck" in text
    assert "Grade lab 3" not in text
    assert bridge.write_now(s, mems, {}) is False  # unchanged board: no rewrite, no Sync churn


def test_bridge_off_without_vault(tmp_path):
    s = Settings(_env_file=None, PENSIEVE_DATA_DIR=str(tmp_path), PENSIEVE_VAULT_DIR="")
    assert bridge.write_now(s, [], {}) is False and bridge.scan_requests(s) == []


# ----- requests -----


REQ = """---
kind: task
to: pensieve
from: yor
created: 2026-10-15
title: Send the offer questions to the recruiter
due: 2026-10-17
list: Home
importance: high
status: draft
# keep this comment
---
Context: from tonight's career session.
"""


def test_scan_finds_only_pending_pensieve_tasks(tmp_path):
    root = _vault(tmp_path)
    _write(root / "Agents" / "Hermes" / "Handoffs" / "2026-10-15_pensieve_offer.md", REQ)
    _write(root / "Agents" / "Hermes" / "Handoffs" / "2026-10-15_luna_post.md",
           REQ.replace("to: pensieve", "to: luna"))
    _write(root / "Agents" / "Hermes" / "Handoffs" / "old.md", REQ.replace("status: draft", "status: executed"))
    _write(root / "Agents" / "Pensieve" / "Inbox" / "from-luna.md",
           "---\nkind: task\nto: pensieve\nfrom: luna\ntitle: Renew domain\n---\n")
    reqs = bridge.scan_requests(_settings(tmp_path, root))
    assert [r["title"] for r in reqs] == ["Renew domain", "Send the offer questions to the recruiter"]
    yor = reqs[1]
    assert (yor["from"], yor["due_date"], yor["list_name"], yor["importance"]) == ("yor", "2026-10-17", "Home", "high")
    assert yor["notes"] == "Context: from tonight's career session."


def test_resolve_writes_only_status_and_outcome(tmp_path):
    root = _vault(tmp_path)
    path = root / "Agents" / "Hermes" / "Handoffs" / "req.md"
    _write(path, REQ)
    s = _settings(tmp_path, root)
    rid = bridge.scan_requests(s)[0]["id"]
    bridge.resolve_request(s, rid, "executed", 'added to "Home"')
    text = path.read_text(encoding="utf-8")
    assert "status: executed" in text and "outcome: \"added to 'Home'\"" in text and "outcome_date:" in text
    assert "# keep this comment" in text and text.endswith("Context: from tonight's career session.\n")
    assert bridge.scan_requests(s) == []
    with pytest.raises(ValueError):
        bridge.resolve_request(s, rid, "deleted", "x")


# ----- API -----


@pytest.fixture
def api(tmp_path, monkeypatch):
    root = _vault(tmp_path)
    _write(root / "Agents" / "Hermes" / "Handoffs" / "req.md", REQ)
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PENSIEVE_VAULT_DIR", str(root))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_ENABLED", "false")
    monkeypatch.setenv("PENSIEVE_DEFAULT_SOURCE", "outlook_com")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    with TestClient(create_app()) as c:
        yield c, root
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_api_lists_and_adds_a_request(api, monkeypatch):
    c, root = api
    state = c.get("/api/bridge").json()
    assert state["enabled"] is True and len(state["requests"]) == 1
    rid = state["requests"][0]["id"]
    added = {}
    monkeypatch.setattr("pensieve.capture.add_task",
                        lambda settings, task: added.setdefault("t", task) and
                        {"source": "outlook_com", "id": "E1", "list_name": "Home"})
    monkeypatch.setattr("pensieve.api.server.start_sync_job", lambda **kw: object())
    r = c.post(f"/api/bridge/requests/{rid}/add", json={"title": "Send the offer questions"})
    assert r.status_code == 200 and r.json()["request"] == rid
    assert added["t"].title == "Send the offer questions" and added["t"].due_date == date(2026, 10, 17)
    assert "status: executed" in (root / "Agents" / "Hermes" / "Handoffs" / "req.md").read_text(encoding="utf-8")
    assert c.get("/api/bridge").json()["requests"] == []


def test_api_dismiss(api):
    c, root = api
    rid = c.get("/api/bridge").json()["requests"][0]["id"]
    assert c.post(f"/api/bridge/requests/{rid}/dismiss").status_code == 200
    assert "status: dropped" in (root / "Agents" / "Hermes" / "Handoffs" / "req.md").read_text(encoding="utf-8")
    assert c.post("/api/bridge/requests/nope/dismiss").status_code == 404


def test_now_note_shows_goal_names_not_ids(tmp_path):
    root = _vault(tmp_path)
    s = _settings(tmp_path, root)
    m = _mem("g", "Plan the offsite", "dive", "Home")
    m.connect_goal_ids = ["goal-1-career"]
    bridge.write_now(s, [m], {"goal-1-career": {"id": "goal-1-career", "short_name": "Career and work"}})
    text = (root / "Agents" / "Pensieve" / "Now.md").read_text(encoding="utf-8")
    assert "goal: Career and work" in text and "goal-1-career" not in text
