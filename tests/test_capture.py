"""Voice capture: draft parsing and add-only task creation (no Outlook, no network)."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from pensieve.api.server import create_app
from pensieve.capture import NewTask, TaskCreationDisabled, add_task, creators, parse_spoken_task
from pensieve.config import Settings, get_settings

LISTS = ["Tasks", "CISO GRC", "Home"]
TODAY = date(2026, 10, 15)  # a Thursday


class _FakeClient:
    def __init__(self, reply):
        self.reply = reply
        self.messages = None

    def chat(self, messages, **kw):
        self.messages = messages
        if isinstance(self.reply, Exception):
            raise self.reply
        return {"model": "gpt-5.4", "choices": [{"message": {"content": self.reply}}]}


def _settings(tmp_path, **kw) -> Settings:
    return Settings(_env_file=None, PENSIEVE_DATA_DIR=str(tmp_path), **kw)


# ----- parse -----


def test_parse_returns_clean_draft_and_grounds_the_prompt(tmp_path):
    client = _FakeClient(json.dumps({
        "title": "Send the status report to my manager.",
        "notes": "Include the risk register",
        "due_date": "2026-10-16",
        "list_name": "ciso grc",
        "importance": "HIGH",
    }))
    draft = parse_spoken_task(_settings(tmp_path), "send the status report...", LISTS, today=TODAY, client=client)
    assert draft == {
        "title": "Send the status report to my manager",
        "notes": "Include the risk register",
        "due_date": "2026-10-16",
        "list_name": "CISO GRC",
        "importance": "high",
        "ai": True,
        "model": "gpt-5.4",
    }
    system = client.messages[0]["content"]
    assert "2026-10-15 (Thursday)" in system and "- CISO GRC" in system


def test_parse_drops_invented_lists_and_bad_dates(tmp_path):
    client = _FakeClient(json.dumps({"title": "Call mom", "due_date": "Friday", "list_name": "Errands"}))
    draft = parse_spoken_task(_settings(tmp_path), "call mom", LISTS, today=TODAY, client=client)
    assert draft["due_date"] is None and draft["list_name"] is None and draft["importance"] == "normal"


def test_parse_falls_back_to_transcript_when_ai_fails(tmp_path):
    long_text = "remember to " + "really " * 20 + "book the venue"
    draft = parse_spoken_task(_settings(tmp_path), long_text, LISTS, client=_FakeClient(RuntimeError("down")))
    assert draft["ai"] is False and draft["title"].endswith("...") and draft["notes"] == long_text
    assert "down" in draft["error"]


def test_parse_rejects_empty(tmp_path):
    with pytest.raises(ValueError):
        parse_spoken_task(_settings(tmp_path), "   ", LISTS, client=_FakeClient("{}"))


# ----- creation gates -----


def test_add_task_respects_the_switch(tmp_path):
    s = _settings(tmp_path, PENSIEVE_ALLOW_TASK_CREATE=False, PENSIEVE_DEFAULT_SOURCE="outlook_com")
    with pytest.raises(TaskCreationDisabled):
        add_task(s, NewTask(title="x"))


def test_add_task_refuses_sample_source(tmp_path):
    with pytest.raises(TaskCreationDisabled):
        add_task(_settings(tmp_path, PENSIEVE_DEFAULT_SOURCE="sample_file"), NewTask(title="x"))


def test_add_task_routes_to_outlook_and_normalizes(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(creators, "_com_add", lambda task: seen.setdefault("task", task) and {"id": "E1", "list_name": "Home"})
    out = add_task(_settings(tmp_path, PENSIEVE_DEFAULT_SOURCE="outlook_com"),
                   NewTask(title="  Water the plants  ", importance="URGENT"))
    assert out == {"source": "outlook_com", "id": "E1", "list_name": "Home"}
    assert seen["task"].title == "Water the plants" and seen["task"].importance == "normal"
    with pytest.raises(ValueError):
        add_task(_settings(tmp_path, PENSIEVE_DEFAULT_SOURCE="outlook_com"), NewTask(title="  "))


def test_graph_add_posts_only_a_new_task(tmp_path, monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.content))
        if request.method == "GET":
            return httpx.Response(200, json={"value": [
                {"id": "L1", "displayName": "Tasks", "wellknownListName": "defaultList"},
                {"id": "L2", "displayName": "Home", "wellknownListName": "none"},
            ]})
        return httpx.Response(201, json={"id": "T9"})

    monkeypatch.setattr(creators, "_graph_client", lambda settings: httpx.Client(
        base_url=creators.GRAPH_BASE, transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(creators, "_local_tz_id", lambda: "Pacific Standard Time")
    s = _settings(tmp_path, PENSIEVE_DEFAULT_SOURCE="personal_graph")
    out = add_task(s, NewTask(title="Buy milk", due_date=date(2026, 10, 17), list_name="home", importance="high"))
    assert out == {"source": "personal_graph", "id": "T9", "list_name": "Home"}
    method, path, content = calls[-1]
    assert method == "POST" and path.endswith("/me/todo/lists/L2/tasks")
    body = json.loads(content)
    assert body == {"title": "Buy milk", "importance": "high",
                    "dueDateTime": {"dateTime": "2026-10-17T00:00:00", "timeZone": "Pacific Standard Time"}}
    assert [m for m, _, _ in calls].count("POST") == 1  # never PATCH or DELETE


# ----- API -----


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_ENABLED", "false")
    monkeypatch.setenv("PENSIEVE_DEFAULT_SOURCE", "outlook_com")
    get_settings.cache_clear()  # type: ignore[attr-defined]
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_api_add_creates_then_starts_a_narrow_sync(api, monkeypatch):
    created = {}
    monkeypatch.setattr("pensieve.capture.add_task",
                        lambda settings, task: created.setdefault("t", task) and
                        {"source": "outlook_com", "id": "E1", "list_name": "Home"})
    started = {}
    monkeypatch.setattr("pensieve.api.server.start_sync_job", lambda **kw: started.update(kw) or object())
    r = api.post("/api/capture/add", json={"title": "Water plants", "due_date": "2026-10-20", "list_name": "Home"})
    assert r.status_code == 200 and r.json()["sync_started"] is True
    assert created["t"].due_date == date(2026, 10, 20)
    assert started["list_names"] == ["Home"] and started["src_name"] == "outlook_com"
    assert api.post("/api/capture/add", json={"title": "x", "due_date": "Friday"}).status_code == 400
