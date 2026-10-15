"""GitHub Copilot client tests: no network, no Copilot CLI."""

from __future__ import annotations

import json

import pytest

from pensieve.config import Settings
from pensieve.enrichment import copilot_client as cc
from pensieve.enrichment.chat_provider import get_chat_client


class _FakeRuntime:
    """Stands in for the CLI-backed runtime: records the prompt, returns a canned reply."""

    def __init__(self, reply: str, usage: tuple[int, int] = (120, 30)) -> None:
        self.reply = reply
        self.usage = usage
        self.calls: list[tuple[str, str, str]] = []

    def run(self, coro, timeout):  # noqa: ARG002 - mirrors _CopilotRuntime.run
        return coro

    def ask(self, model, system, prompt, timeout):  # noqa: ARG002
        self.calls.append((model, system, prompt))
        return self.reply, {"prompt_tokens": self.usage[0], "completion_tokens": self.usage[1]}, model


_DATA_DIR: list[str] = []


def _settings(**overrides) -> Settings:
    # data_dir points at the test's tmp dir so saved in-app model choices
    # (data/ai-models.json) on this machine cannot leak into the test.
    base = {"llm_provider": "github_copilot", "copilot_model": "gpt-5.4", "data_dir": _DATA_DIR[-1]}
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path):
    _DATA_DIR.append(str(tmp_path))
    yield
    _DATA_DIR.pop()


@pytest.fixture
def fake_runtime(monkeypatch):
    rt = _FakeRuntime('{"ok": true}')
    monkeypatch.setattr(cc, "_runtime_for", lambda settings: rt)
    return rt


def test_chat_uses_in_app_model_choice_per_purpose(fake_runtime):
    from pensieve import ai_prefs

    s = _settings()
    ai_prefs.save(s, {"default": "claude-sonnet-5.5", "recap": "gpt-6-sol"})
    cc.CopilotChatClient(s, purpose="recap").chat([{"role": "user", "content": "x"}])
    cc.CopilotChatClient(s, purpose="enrichment").chat([{"role": "user", "content": "x"}])
    assert [call[0] for call in fake_runtime.calls] == ["gpt-6-sol", "claude-sonnet-5.5"]


def test_factory_returns_copilot_client(fake_runtime):
    assert isinstance(get_chat_client(_settings()), cc.CopilotChatClient)


def test_chat_returns_openai_shaped_response(fake_runtime):
    fake_runtime.reply = '```json\n{"title": "x"}\n```'
    resp = cc.CopilotChatClient(_settings()).chat(
        [{"role": "system", "content": "Enrich this."}, {"role": "user", "content": "task"}]
    )
    assert json.loads(resp["choices"][0]["message"]["content"]) == {"title": "x"}
    assert resp["usage"] == {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150}
    model, system, prompt = fake_runtime.calls[0]
    assert model == "gpt-5.4"
    assert system.startswith("Enrich this.") and "single valid JSON object" in system
    assert prompt == "task"


def test_chat_plain_text_mode_skips_json_instruction(fake_runtime):
    fake_runtime.reply = "Plain answer."
    resp = cc.CopilotChatClient(_settings()).chat(
        [{"role": "user", "content": "hi"}], response_format=None
    )
    assert resp["choices"][0]["message"]["content"] == "Plain answer."
    assert "JSON" not in fake_runtime.calls[0][1]


def test_split_messages_replays_multi_turn_history():
    system, prompt = cc._split_messages(
        [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "second"},
        ],
        json_mode=False,
    )
    assert system == "S"
    assert prompt.index("first") < prompt.index("reply") < prompt.index("second")
    assert prompt.rstrip().endswith("second")


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        'Here you go:\n{"a": 1}\nHope that helps.',
    ],
)
def test_extract_json_tolerates_fences_and_prose(raw):
    assert json.loads(cc._extract_json(raw)) == {"a": 1}


def test_extract_json_leaves_non_json_for_caller_to_reject():
    assert cc._extract_json("no json here") == "no json here"


def test_token_lookup_reports_missing_gh_login(monkeypatch):
    class _Out:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(cc.subprocess, "run", lambda *a, **k: _Out())
    with pytest.raises(cc.CopilotUnavailable, match="gh auth login"):
        cc._token_for_user("someone")
