"""Tests for Connect recap generation (pensieve/recap.py).

Uses a fake chat client so no Azure calls happen. Verifies scope filtering,
goal grouping (including multi-goal and unaligned buckets), and that the
per-goal LLM output is threaded into the section payload.
"""

from __future__ import annotations

import json

from pensieve.recap import filter_by_scope, generate_recap
from pensieve.store.schema import Memory

GOALS = [
    {
        "id": "goal-a",
        "short_name": "Goal A",
        "name": "Goal A full",
        "lane": "crimson",
        "summary": "do A",
        "success_criteria": ["crit a1"],
        "impact_statement": "impact a",
    },
    {
        "id": "goal-b",
        "short_name": "Goal B",
        "name": "Goal B full",
        "lane": "azure",
        "summary": "do B",
        "success_criteria": [],
        "impact_statement": "",
    },
]


class FakeChatClient:
    """Records prompts and returns a deterministic accomplishments payload."""

    def __init__(self):
        self.calls = []

    def chat(self, *, messages, max_output_tokens, response_format):  # noqa: D401
        self.calls.append(messages)
        user = messages[-1]["content"]
        payload = {
            "accomplishments": [
                {
                    "heading": "Heading",
                    "narrative": "I did the work.",
                    "impact": "It mattered.",
                }
            ]
        }
        # Echo whether the unaligned synthetic goal was the subject, so a test
        # can confirm routing without parsing the whole prompt.
        if "not mapped to a committed goal" in user:
            payload["accomplishments"][0]["heading"] = "Other Work"
        return {
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": {"total_tokens": 42},
        }


def _mem(mid: str, *, goals=None, completed=False, column="memory", cs=0.9, ci=0.9) -> Memory:
    return Memory(
        id=mid,
        source="test",
        source_task_id=mid,
        title=f"task {mid}",
        why="why",
        impact="impact",
        connect_goal_ids=goals or [],
        completed=completed,
        column=column,
        confidence_strand=cs,
        confidence_impact=ci,
    )


def test_filter_by_scope_completed():
    mems = [
        _mem("1", completed=True),
        _mem("2", column="closed"),
        _mem("3", column="memory"),
    ]
    out = filter_by_scope(mems, "completed")
    assert {m.id for m in out} == {"1", "2"}


def test_filter_by_scope_review():
    mems = [_mem("1", cs=0.2), _mem("2", ci=0.3), _mem("3")]
    out = filter_by_scope(mems, "review")
    assert {m.id for m in out} == {"1", "2"}


def test_filter_by_scope_all_passthrough():
    mems = [_mem("1"), _mem("2", completed=True)]
    assert len(filter_by_scope(mems, "all")) == 2


def test_generate_recap_groups_by_goal_and_unaligned():
    mems = [
        _mem("1", goals=["goal-a"]),
        _mem("2", goals=["goal-a", "goal-b"]),  # multi-goal: appears under both
        _mem("3", goals=[]),  # unaligned
    ]
    client = FakeChatClient()
    recap = generate_recap(
        mems,
        scope="all",
        goals=GOALS,
        client=client,
        period_label="Test Period",
    )

    assert recap["period_label"] == "Test Period"
    assert recap["memories_considered"] == 3
    by_id = {s["goal_id"]: s for s in recap["sections"]}

    assert by_id["goal-a"]["task_count"] == 2
    assert set(by_id["goal-a"]["task_titles"]) == {"task 1", "task 2"}
    assert by_id["goal-b"]["task_count"] == 1
    # Unaligned synthetic section present
    assert "_unaligned" in by_id
    assert by_id["_unaligned"]["accomplishments"][0]["heading"] == "Other Work"
    # Tokens summed across the 3 goal calls (a, b, unaligned) = 3 * 42
    assert recap["tokens_used"] == 126


def test_generate_recap_respects_goal_ids_filter_and_skips_unaligned():
    mems = [
        _mem("1", goals=["goal-a"]),
        _mem("2", goals=["goal-b"]),
        _mem("3", goals=[]),
    ]
    client = FakeChatClient()
    recap = generate_recap(mems, scope="all", goal_ids=["goal-a"], goals=GOALS, client=client)
    ids = {s["goal_id"] for s in recap["sections"]}
    assert ids == {"goal-a"}  # goal-b filtered out, unaligned suppressed when filtering


def test_generate_recap_empty_when_no_items():
    client = FakeChatClient()
    recap = generate_recap([], scope="all", goals=GOALS, client=client)
    assert recap["sections"] == []
    assert recap["tokens_used"] == 0
    assert client.calls == []
