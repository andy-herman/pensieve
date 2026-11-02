"""Unit and API tests for GitHub Copilot app task handoff."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from pensieve.api.server import create_app
from pensieve.config import get_settings
from pensieve.copilot_handoff import (
    build_copilot_kickoff_prompt,
    concise_session_title,
)
from pensieve.store import ChromaMemoryStore, Memory, Vial


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PENSIEVE_AUTO_SYNC_INTERVAL_SECONDS", "0")
    monkeypatch.delenv("PENSIEVE_SESSION_TOKEN", raising=False)
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield tmp_path
    get_settings.cache_clear()  # type: ignore[attr-defined]


def test_concise_session_title_strips_number_prefix_and_bounds_length():
    mem = Memory(
        id="m1",
        source="outlook_com",
        source_task_id="m1",
        title="[01] UK CTP 2 Nov regulator call: ISA/CAF reflections talk track and handoff",
        display_title="[01] UK CTP 2 Nov regulator call: ISA/CAF reflections talk track",
    )
    title = concise_session_title(mem, max_len=40)
    assert not title.startswith("[01]")
    assert len(title) <= 40
    assert "UK CTP" in title


def test_build_copilot_kickoff_prompt_includes_full_context(isolated_env):
    target = Memory(
        id="open-item-01",
        source="open_items_102626",
        source_task_id="open-item-01",
        list_name="CISO GRC",
        title="[01] UK CTP 2 Nov regulator meeting: Prep ISA/CAF reflections",
        display_title="UK CTP 2 Nov regulator call: ISA/CAF reflections talk track",
        why="Assigned ISA reflections on Fernando's agenda.",
        impact="Crisp speaking track for Monday regulator call.",
        original_notes="Work with: Khadija, Keith, Fernando, Hunter",
        notes_for_user="Ask Keith for Box 2 notes first.",
        suggested_strand="uk-ctp-domain",
        connect_goal_ids=["goal-2-uk-ctp"],
        connect_alignment_note="Advances UK CTP regulator readiness.",
        column="dive",
        due_date=datetime(2026, 11, 2, 16, 0, tzinfo=timezone.utc),
        categories=["UK CTP", "Priority Top 6"],
    )
    sibling = Memory(
        id="open-item-12",
        source="open_items_102626",
        source_task_id="open-item-12",
        list_name="CISO GRC",
        title="UK CTP incident playbook scope",
        display_title="UK CTP incident playbook & scenario-testing scope",
        why="5 Nov clarification sync.",
        suggested_strand="uk-ctp-domain",
        connect_goal_ids=["goal-2-uk-ctp"],
        column="review",
    )
    vial = Vial(
        id="v1",
        memory_id="open-item-01",
        captured_at=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        capture_kind="captured",
        captured_text="Slide 4 updated with three forward-looking asks.",
    )
    goals = [
        {
            "id": "goal-2-uk-ctp",
            "number": 2,
            "short_name": "UK CTP",
            "name": "UK CTP Year 1 Complete + Year 2 Launch",
            "summary": "Deliver Year 1 UK CTP obligations.",
            "success_criteria": ["Submit Self-Assessment on time"],
            "impact_statement": "Regulatory credibility with BoE, PRA, FCA.",
        }
    ]
    strands = [
        {
            "id": "uk-ctp-domain",
            "display_name": "UK CTP Domain Write-up",
            "kind": "deep",
            "description": "Drafting and iterating UK CTP deliverables.",
        }
    ]
    docs = [
        {
            "id": "catch-up",
            "title": "Workstreams & Open Actions",
            "content": "1. **UK CTP / 2 Nov (#01):** Review latest slide 4 and build talk track.",
        }
    ]

    prompt = build_copilot_kickoff_prompt(
        target,
        all_memories=[target, sibling],
        goals=goals,
        strand_catalog=strands,
        vials=[vial],
        docs=docs,
    )

    assert "UK CTP 2 Nov regulator call: ISA/CAF reflections talk track" in prompt
    assert "Assigned ISA reflections on Fernando's agenda." in prompt
    assert "Ask Keith for Box 2 notes first." in prompt
    assert "UK CTP Domain Write-up" in prompt
    assert "Goal #2: UK CTP Year 1 Complete + Year 2 Launch" in prompt
    assert "Slide 4 updated with three forward-looking asks." in prompt
    assert "UK CTP incident playbook & scenario-testing scope" in prompt
    assert "Review latest slide 4 and build talk track." in prompt


def test_copilot_handoff_endpoint_promotes_backlog_to_dive_and_bumps_tended(
    isolated_env, monkeypatch
):
    store = ChromaMemoryStore()
    mem = Memory(
        id="t-100",
        source="outlook_com",
        source_task_id="t-100",
        list_name="CISO GRC",
        title="Draft NIS2 scope note",
        display_title="Draft NIS2 scope note",
        why="Prepare Ireland transposition overview.",
        column="memory",
    )
    store.upsert_memory(mem)

    captured_call: dict = {}

    def fake_launch(memory, **kwargs):
        captured_call["memory_id"] = memory.id
        captured_call["kwargs"] = kwargs
        return {
            "session_id": "sess-1234",
            "title": "Draft NIS2 scope note",
            "app_url": "ghapp://sessions/sess-1234",
            "deep_link": "github-app://notification/open?task_session_id=sess-1234&session_type=general_chat",
            "prompt_chars": 900,
        }

    monkeypatch.setattr(
        "pensieve.copilot_handoff.launch_memory_in_copilot_app",
        fake_launch,
    )

    app = create_app()
    with TestClient(app) as client:
        res = client.post("/api/memories/mem_t-100/copilot", json={})
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["session_id"] == "sess-1234"
        assert body["app_url"] == "ghapp://sessions/sess-1234"
        assert body["memory"]["column"] == "dive"
        assert captured_call["memory_id"] == "t-100"
