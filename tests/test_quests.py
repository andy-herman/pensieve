"""Garden v2 pure-function tests: quest generation, completion, clean board."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pensieve import quests
from pensieve.store.schema import Memory

UTC = timezone.utc


def _mk(
    mid: str,
    *,
    column: str = "memory",
    last_tended_at: datetime | None = None,
    enriched_at: datetime | None = None,
    completed_at: datetime | None = None,
    due_date: datetime | None = None,
    list_name: str = "CISO GRC",
) -> Memory:
    return Memory(
        id=mid,
        source="sample_file",
        source_task_id=mid,
        list_name=list_name,
        title=f"Memory {mid}",
        display_title=f"Memory {mid}",
        why="why",
        impact="impact",
        column=column,
        last_tended_at=last_tended_at,
        enriched_at=enriched_at or datetime.now(UTC) - timedelta(days=1),
        due_date=due_date,
        completed=(column == "closed"),
        completed_at=completed_at,
    )


NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


# --- generation -------------------------------------------------------------


def test_generate_empty_board_returns_no_quests():
    assert quests.generate_quests([], NOW) == []


def test_generate_ghost_takes_priority():
    ghost = _mk("g1", last_tended_at=NOW - timedelta(days=45))
    stale1 = _mk("s1", last_tended_at=NOW - timedelta(days=10))
    stale2 = _mk("s2", last_tended_at=NOW - timedelta(days=12))
    out = quests.generate_quests([ghost, stale1, stale2], NOW)
    assert out[0].kind == "bury-ghost"
    assert out[0].target_memory_ids == ["g1"]


def test_generate_stale_quest_when_two_in_one_column():
    mems = [
        _mk("a", column="dive", last_tended_at=NOW - timedelta(days=10)),
        _mk("b", column="dive", last_tended_at=NOW - timedelta(days=15)),
        _mk("c", column="dive", last_tended_at=NOW - timedelta(days=20)),
        _mk("d", column="review", last_tended_at=NOW - timedelta(days=10)),  # solo, no quest
    ]
    out = quests.generate_quests(mems, NOW)
    assert any(q.kind == "tend-stale" for q in out)
    stale_q = next(q for q in out if q.kind == "tend-stale")
    assert "dive" in stale_q.title
    assert len(stale_q.target_memory_ids) == 3  # capped at 3
    # oldest-tended first
    assert stale_q.target_memory_ids[0] == "c"


def test_generate_no_stale_quest_for_single_stale_card():
    mems = [_mk("a", column="dive", last_tended_at=NOW - timedelta(days=10))]
    out = quests.generate_quests(mems, NOW)
    assert not any(q.kind == "tend-stale" for q in out)


def test_generate_yesterday_closures_quest():
    yesterday = NOW - timedelta(days=1)
    mems = [
        _mk("c1", column="closed", completed_at=yesterday, last_tended_at=yesterday),
        _mk("c2", column="closed", completed_at=yesterday, last_tended_at=yesterday),
    ]
    out = quests.generate_quests(mems, NOW, captured_counts={})
    assert any(q.kind == "capture-yesterday-closures" for q in out)
    closures = next(q for q in out if q.kind == "capture-yesterday-closures")
    assert set(closures.target_memory_ids) == {"c1", "c2"}


def test_generate_yesterday_closures_excludes_already_captured():
    yesterday = NOW - timedelta(days=1)
    mems = [
        _mk("c1", column="closed", completed_at=yesterday),
        _mk("c2", column="closed", completed_at=yesterday),
    ]
    out = quests.generate_quests(mems, NOW, captured_counts={"c1": 1})
    closures = next((q for q in out if q.kind == "capture-yesterday-closures"), None)
    assert closures is not None
    assert closures.target_memory_ids == ["c2"]


def test_generate_triage_inbox_when_old_memory_card_exists():
    mems = [
        _mk("old", column="memory", last_tended_at=NOW - timedelta(days=5)),
    ]
    out = quests.generate_quests(mems, NOW)
    assert any(q.kind == "triage-inbox" for q in out)


def test_generate_no_triage_when_inbox_is_fresh():
    mems = [_mk("fresh", column="memory", last_tended_at=NOW - timedelta(hours=2))]
    out = quests.generate_quests(mems, NOW)
    assert not any(q.kind == "triage-inbox" for q in out)


def test_generate_hit_95_quest_when_in_band():
    mems = [_mk("a", column="memory", last_tended_at=NOW - timedelta(hours=1))]
    out = quests.generate_quests(mems, NOW, current_health=92)
    assert any(q.kind == "hit-95-health" for q in out)


def test_generate_no_hit_95_quest_below_band():
    mems = [_mk("a", column="memory", last_tended_at=NOW - timedelta(hours=1))]
    out = quests.generate_quests(mems, NOW, current_health=70)
    assert not any(q.kind == "hit-95-health" for q in out)


def test_generate_caps_at_three_quests():
    yesterday = NOW - timedelta(days=1)
    mems = [
        _mk("g", last_tended_at=NOW - timedelta(days=45)),  # ghost
        _mk("s1", column="dive", last_tended_at=NOW - timedelta(days=10)),  # stale
        _mk("s2", column="dive", last_tended_at=NOW - timedelta(days=12)),  # stale
        _mk("c1", column="closed", completed_at=yesterday),  # yesterday closure
        _mk("old", column="memory", last_tended_at=NOW - timedelta(days=5)),  # triage
    ]
    out = quests.generate_quests(mems, NOW, current_health=92)
    assert len(out) == 3


def test_generate_quest_ids_are_deterministic_per_day():
    ghost = _mk("g", last_tended_at=NOW - timedelta(days=40))
    a = quests.generate_quests([ghost], NOW)
    b = quests.generate_quests([ghost], NOW)
    assert a[0].id == b[0].id
    assert "2026-06-05" in a[0].id


# --- completion -------------------------------------------------------------


def test_completion_bury_ghost_when_tended_today():
    ghost = _mk("g", last_tended_at=NOW - timedelta(days=45))
    q = quests.Quest(
        id="x", kind="bury-ghost", title="t", description="d",
        target_memory_ids=["g"],
    )
    # not tended today yet
    assert not quests.check_completion(
        q, now=NOW, all_memories=[ghost], captured_counts={}
    )
    # tend it today
    ghost.last_tended_at = NOW
    assert quests.check_completion(
        q, now=NOW, all_memories=[ghost], captured_counts={}
    )


def test_completion_tend_stale_requires_all_targets_tended():
    a = _mk("a", column="dive", last_tended_at=NOW - timedelta(days=10))
    b = _mk("b", column="dive", last_tended_at=NOW - timedelta(days=10))
    q = quests.Quest(
        id="x", kind="tend-stale", title="t", description="d",
        target_memory_ids=["a", "b"],
    )
    assert not quests.check_completion(
        q, now=NOW, all_memories=[a, b], captured_counts={}
    )
    a.last_tended_at = NOW
    assert not quests.check_completion(
        q, now=NOW, all_memories=[a, b], captured_counts={}
    )  # b still untended
    b.last_tended_at = NOW
    assert quests.check_completion(
        q, now=NOW, all_memories=[a, b], captured_counts={}
    )


def test_completion_capture_yesterday_requires_captured_vials():
    yesterday = NOW - timedelta(days=1)
    a = _mk("a", column="closed", completed_at=yesterday)
    b = _mk("b", column="closed", completed_at=yesterday)
    q = quests.Quest(
        id="x", kind="capture-yesterday-closures", title="t", description="d",
        target_memory_ids=["a", "b"],
    )
    assert not quests.check_completion(
        q, now=NOW, all_memories=[a, b], captured_counts={"a": 1}
    )
    assert quests.check_completion(
        q, now=NOW, all_memories=[a, b], captured_counts={"a": 1, "b": 2}
    )


def test_completion_triage_done_when_moved_out_of_memory():
    m = _mk("a", column="memory", last_tended_at=NOW - timedelta(days=5))
    q = quests.Quest(
        id="x", kind="triage-inbox", title="t", description="d",
        target_memory_ids=["a"],
    )
    assert not quests.check_completion(q, now=NOW, all_memories=[m], captured_counts={})
    m.column = "dive"
    assert quests.check_completion(q, now=NOW, all_memories=[m], captured_counts={})


def test_completion_triage_done_when_edited_today_even_if_still_in_memory():
    m = _mk("a", column="memory", last_tended_at=NOW)
    q = quests.Quest(
        id="x", kind="triage-inbox", title="t", description="d",
        target_memory_ids=["a"],
    )
    assert quests.check_completion(q, now=NOW, all_memories=[m], captured_counts={})


def test_completion_hit_95_needs_score_at_or_above_95():
    q = quests.Quest(
        id="x", kind="hit-95-health", title="t", description="d",
        target_memory_ids=[],
    )
    assert not quests.check_completion(
        q, now=NOW, all_memories=[], captured_counts={}, current_health=94
    )
    assert quests.check_completion(
        q, now=NOW, all_memories=[], captured_counts={}, current_health=95
    )


def test_completion_auto_completes_when_target_disappears():
    """Critique non-blocking #4: deleted target shouldn't block a quest forever."""
    q = quests.Quest(
        id="x", kind="bury-ghost", title="t", description="d",
        target_memory_ids=["gone"],
    )
    assert quests.check_completion(
        q, now=NOW, all_memories=[], captured_counts={}
    )


def test_completion_idempotent_when_already_done():
    q = quests.Quest(
        id="x", kind="bury-ghost", title="t", description="d",
        target_memory_ids=["any"],
        completed_at=NOW - timedelta(hours=1),
    )
    # No targets exist, but already complete — must return True.
    assert quests.check_completion(
        q, now=NOW, all_memories=[], captured_counts={}
    )


def test_evaluate_pending_only_marks_transition():
    ghost = _mk("g", last_tended_at=NOW)
    q1 = quests.Quest(
        id="a", kind="bury-ghost", title="t", description="d",
        target_memory_ids=["g"],
    )
    q2 = quests.Quest(
        id="b", kind="hit-95-health", title="t", description="d",
        target_memory_ids=[],
    )
    out = quests.evaluate_pending(
        [q1, q2], now=NOW, all_memories=[ghost], captured_counts={},
        current_health=80,
    )
    assert out[0].is_complete
    assert not out[1].is_complete


def test_all_complete_helper():
    assert not quests.all_complete([])
    q = quests.Quest(id="x", kind="bury-ghost", title="t", description="d")
    assert not quests.all_complete([q])
    q.completed_at = NOW
    assert quests.all_complete([q])


def test_quest_bonus_for_helper():
    q = quests.Quest(id="x", kind="bury-ghost", title="t", description="d")
    assert quests.quest_bonus_for([q]) == 0
    q.completed_at = NOW
    assert quests.quest_bonus_for([q]) == 5


# --- is_board_clean ---------------------------------------------------------


def test_is_board_clean_empty():
    assert quests.is_board_clean([], NOW)


def test_is_board_clean_with_only_fresh_open_and_closed_cards():
    mems = [
        _mk("fresh", column="dive", last_tended_at=NOW - timedelta(hours=2)),
        _mk("closed", column="closed", completed_at=NOW),
    ]
    assert quests.is_board_clean(mems, NOW)


def test_is_board_clean_false_with_stale_card():
    mems = [_mk("stale", column="dive", last_tended_at=NOW - timedelta(days=10))]
    assert not quests.is_board_clean(mems, NOW)


def test_is_board_clean_false_with_overdue_card():
    mems = [
        _mk(
            "od",
            column="dive",
            last_tended_at=NOW,
            due_date=NOW - timedelta(days=1),
        )
    ]
    assert not quests.is_board_clean(mems, NOW)


# --- Quest.to_dict / from_dict round-trip -----------------------------------


def test_quest_round_trip_with_completion():
    q = quests.Quest(
        id="abc",
        kind="tend-stale",
        title="Tend things",
        description="desc",
        target_memory_ids=["m1", "m2"],
        completed_at=NOW,
    )
    d = q.to_dict()
    back = quests.Quest.from_dict(d)
    assert back.id == q.id
    assert back.kind == q.kind
    assert back.target_memory_ids == q.target_memory_ids
    assert back.completed_at is not None
    assert back.completed_at.replace(microsecond=0) == NOW.replace(microsecond=0)


def test_quest_round_trip_pending():
    q = quests.Quest(
        id="abc", kind="bury-ghost", title="t", description="d",
        target_memory_ids=["g"],
    )
    back = quests.Quest.from_dict(q.to_dict())
    assert back.completed_at is None
    assert not back.is_complete
