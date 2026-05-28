"""Smoke test: enrichment payload shape (no actual LLM call)."""

from __future__ import annotations

from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.enrichment.enricher import _build_user_payload  # noqa: SLF001 (test access)
from pensieve.enrichment.prompt import load_system_prompt
from pensieve.sources.base import RawTask


def test_system_prompt_loads():
    prompt = load_system_prompt()
    assert "Pensieve Memory Enrichment" in prompt


def test_connect_goals_load():
    goals = load_connect_goals()
    assert len(goals) >= 4
    ids = {g.get("id") for g in goals}
    assert "goal-1-dora-deep-dive" in ids


def test_payload_builds_valid_json():
    task = RawTask(id="t1", title="Test", notes="", list_name="Tasks")
    payload = _build_user_payload(task, [], load_connect_goals(), {})
    assert '"task"' in payload
    assert '"connect_goals"' in payload
