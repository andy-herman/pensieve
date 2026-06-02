"""Tests for recap power-ups: DOCX export, run history, and section revise."""

from __future__ import annotations

import json

from pensieve.config import Settings
from pensieve.recap import revise_recap_section
from pensieve.recap_export import build_recap_docx
from pensieve.recap_history import list_history, load_recap, save_recap
from pensieve.store.schema import Memory

SAMPLE_RECAP = {
    "period_label": "Oct 2025 - May 2026",
    "scope": "all",
    "memories_considered": 2,
    "section_count": 1,
    "tokens_used": 100,
    "sections": [
        {
            "goal_id": "goal-a",
            "short_name": "Goal A",
            "name": "Goal A full",
            "lane": "crimson",
            "task_count": 2,
            "task_titles": ["t1", "t2"],
            "accomplishments": [
                {"heading": "Did A", "narrative": "I did A well.", "impact": "It mattered."}
            ],
        }
    ],
}

GOALS = [
    {"id": "goal-a", "short_name": "Goal A", "name": "Goal A full", "lane": "crimson", "summary": "do A"},
]


def _settings(tmp_path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path
    return s


def test_build_recap_docx_returns_valid_docx_bytes():
    data = build_recap_docx(SAMPLE_RECAP)
    assert isinstance(data, (bytes, bytearray))
    assert len(data) > 1000
    assert data[:2] == b"PK"  # .docx is a zip archive


def test_history_save_list_load_roundtrip(tmp_path):
    s = _settings(tmp_path)
    summary = save_recap(SAMPLE_RECAP, settings=s)
    assert summary["id"].startswith("recap-")
    runs = list_history(s)
    assert len(runs) == 1
    assert runs[0]["id"] == summary["id"]
    assert runs[0]["section_count"] == 1
    full = load_recap(summary["id"], s)
    assert full is not None
    assert full["recap"]["sections"][0]["short_name"] == "Goal A"


def test_history_load_missing_returns_none(tmp_path):
    s = _settings(tmp_path)
    assert load_recap("recap-does-not-exist", s) is None


def test_history_multiple_runs_sorted_newest_first(tmp_path):
    from datetime import datetime, timezone

    s = _settings(tmp_path)
    save_recap(SAMPLE_RECAP, settings=s, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    save_recap(SAMPLE_RECAP, settings=s, now=datetime(2026, 2, 1, tzinfo=timezone.utc))
    runs = list_history(s)
    assert len(runs) == 2
    assert runs[0]["created_at"] > runs[1]["created_at"]


class _FakeClient:
    def __init__(self):
        self.last_user = None

    def chat(self, *, messages, max_output_tokens, response_format):
        self.last_user = messages[-1]["content"]
        payload = {"accomplishments": [{"heading": "Revised", "narrative": "Now correct.", "impact": "Better."}]}
        return {"choices": [{"message": {"content": json.dumps(payload)}}], "usage": {"total_tokens": 50}}


def _mem(mid, goals):
    return Memory(id=mid, source="t", source_task_id=mid, title=f"task {mid}", connect_goal_ids=goals)


def test_revise_section_includes_feedback_and_rewrites():
    client = _FakeClient()
    mems = [_mem("1", ["goal-a"]), _mem("2", ["goal-a"])]
    section = revise_recap_section(
        mems, "goal-a", "Task 1 was about NIS2 testing, not a report.",
        scope="all", goals=GOALS, client=client,
    )
    assert section["goal_id"] == "goal-a"
    assert section["accomplishments"][0]["heading"] == "Revised"
    assert section["task_count"] == 2
    # the correction text must have been sent to the model
    assert "NIS2 testing" in client.last_user
    assert "Reviewer correction" in client.last_user


def test_revise_unknown_goal_raises():
    import pytest

    with pytest.raises(ValueError):
        revise_recap_section([], "goal-nope", "fix it", goals=GOALS, client=_FakeClient())
