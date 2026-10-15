"""In-app model choice: preference store + /api/ai endpoints (no Copilot calls)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from pensieve import ai_prefs
from pensieve.api.server import create_app
from pensieve.config import Settings, get_settings

MODELS = [
    {"id": "gpt-5.4", "name": "GPT-5.4", "enabled": True, "context_tokens": 1_050_000},
    {"id": "claude-sonnet-5.5", "name": "Claude Sonnet 5.5", "enabled": True, "context_tokens": 1_000_000},
    {"id": "grok-4.7", "name": "Grok 4.7", "enabled": False, "context_tokens": 500_000},
]


def _settings(tmp_path, **kw) -> Settings:
    return Settings(_env_file=None, PENSIEVE_DATA_DIR=str(tmp_path), COPILOT_MODEL="gpt-5.4", **kw)


def test_load_defaults_to_inherit_everywhere(tmp_path):
    assert set(ai_prefs.load(_settings(tmp_path)).values()) == {None}


def test_save_roundtrip_cleans_values(tmp_path):
    s = _settings(tmp_path)
    saved = ai_prefs.save(s, {"default": " claude-sonnet-5.5 ", "recap": "", "bogus": "x"})
    assert saved == {"default": "claude-sonnet-5.5", "enrichment": None, "recap": None, "goals": None}
    assert ai_prefs.load(s) == saved
    assert json.loads((tmp_path / ai_prefs.FILENAME).read_text(encoding="utf-8"))["default"] == "claude-sonnet-5.5"


def test_model_for_precedence(tmp_path):
    s = _settings(tmp_path)
    assert ai_prefs.model_for(s, "recap") == "gpt-5.4"  # .env default
    ai_prefs.save(s, {"default": "claude-sonnet-5.5"})
    assert ai_prefs.model_for(s, "recap") == "claude-sonnet-5.5"  # panel default
    ai_prefs.save(s, {"default": "claude-sonnet-5.5", "recap": "gpt-6-sol"})
    assert ai_prefs.model_for(s, "recap") == "gpt-6-sol"  # purpose override
    assert ai_prefs.model_for(s, "enrichment") == "claude-sonnet-5.5"


def test_corrupt_file_falls_back_to_inherit(tmp_path):
    (tmp_path / ai_prefs.FILENAME).write_text("{not json", encoding="utf-8")
    assert ai_prefs.model_for(_settings(tmp_path), "goals") == "gpt-5.4"


class _FakeCopilot:
    def __init__(self):
        self.pinged: list[str] = []

    def list_models(self):
        return [dict(m) for m in MODELS]

    def ping(self, model):
        self.pinged.append(model)
        return {"ok": True, "model": model, "reply": "OK", "seconds": 0.5, "tokens": 12}


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_ENABLED", "false")
    monkeypatch.setenv("LLM_PROVIDER", "github_copilot")
    monkeypatch.setenv("COPILOT_MODEL", "gpt-5.4")
    monkeypatch.setenv("COPILOT_GITHUB_USER", "someone_work")
    fake = _FakeCopilot()
    monkeypatch.setattr(
        "pensieve.enrichment.chat_provider.get_chat_client", lambda settings=None, purpose="enrichment": fake
    )
    get_settings.cache_clear()  # type: ignore[attr-defined]
    with TestClient(create_app()) as c:
        yield c, fake
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_get_state_reports_provider_account_and_effective_models(api):
    c, _ = api
    body = c.get("/api/ai").json()
    assert body["provider"] == "github_copilot"
    assert body["account"] == "someone_work"
    assert body["editable"] is True
    assert body["default_effective"] == "gpt-5.4"
    assert [p["key"] for p in body["purposes"]] == ["enrichment", "recap", "goals"]
    assert all(p["effective"] == "gpt-5.4" and p["model"] is None for p in body["purposes"])


def test_models_lists_enabled_first(api):
    c, _ = api
    ids = [m["id"] for m in c.get("/api/ai/models").json()["models"]]
    assert ids[-1] == "grok-4.7"
    assert set(ids) == {m["id"] for m in MODELS}


def test_save_applies_and_validates(api):
    c, _ = api
    r = c.put("/api/ai", json={"default": "claude-sonnet-5.5", "recap": "gpt-5.4"})
    assert r.status_code == 200
    eff = {p["key"]: p["effective"] for p in r.json()["purposes"]}
    assert eff == {"enrichment": "claude-sonnet-5.5", "recap": "gpt-5.4", "goals": "claude-sonnet-5.5"}

    bad = c.put("/api/ai", json={"default": "not-a-model"})
    assert bad.status_code == 400
    assert "not-a-model" in bad.json()["detail"]


def test_test_endpoint_pings_requested_or_effective_model(api):
    c, fake = api
    assert c.post("/api/ai/test", json={"model": "claude-sonnet-5.5"}).json()["ok"] is True
    c.post("/api/ai/test", json={})
    assert fake.pinged == ["claude-sonnet-5.5", "gpt-5.4"]
