"""Garden v3: pure-function tests for achievement predicates + level-summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pensieve import achievements
from pensieve.store.schema import Memory, Vial

UTC = timezone.utc
NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _mem(
    mid: str = "m",
    *,
    column: str = "memory",
    enriched_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Memory:
    return Memory(
        id=mid,
        source="sample_file",
        source_task_id=mid,
        list_name="CISO GRC",
        title=f"Memory {mid}",
        display_title=f"Memory {mid}",
        why="why",
        impact="impact",
        column=column,
        enriched_at=enriched_at or (NOW - timedelta(days=1)),
        completed=(column == "closed"),
        completed_at=completed_at,
    )


def _vial(vid: str, *, kind: str = "captured", mid: str = "m") -> Vial:
    return Vial(
        id=vid,
        memory_id=mid,
        captured_at=NOW - timedelta(days=1),
        capture_kind=kind,
        captured_text="x" if kind == "captured" else "",
    )


# ----- sprout ---------------------------------------------------------------


def test_sprout_unlocks_when_at_least_one_memory_exists():
    out = achievements.evaluate([_mem("m1")], [])
    assert "sprout" in out


def test_sprout_locked_on_empty_board():
    out = achievements.evaluate([], [])
    assert "sprout" not in out


# ----- scribe / centurion ---------------------------------------------------


def test_scribe_unlocks_at_ten_captured_vials():
    vs = [_vial(f"v{i}") for i in range(10)]
    out = achievements.evaluate([_mem("m1")], vs)
    assert "scribe" in out
    assert "centurion" not in out


def test_scribe_locked_at_nine():
    vs = [_vial(f"v{i}") for i in range(9)]
    assert "scribe" not in achievements.evaluate([_mem("m1")], vs)


def test_skipped_vials_do_not_count_toward_scribe():
    vs = [_vial(f"v{i}", kind="skipped") for i in range(20)]
    out = achievements.evaluate([_mem("m1")], vs)
    assert "scribe" not in out
    assert "centurion" not in out


def test_centurion_unlocks_at_one_hundred_captured():
    vs = [_vial(f"v{i}") for i in range(100)]
    out = achievements.evaluate([_mem("m1")], vs)
    assert "centurion" in out
    assert "scribe" in out


# ----- custodian (ghost-buried derivation) ---------------------------------


def test_custodian_unlocks_when_closed_memory_lived_longer_than_thirty_days():
    born = NOW - timedelta(days=45)
    closed = NOW - timedelta(days=2)
    m = _mem("m1", column="closed", enriched_at=born, completed_at=closed)
    out = achievements.evaluate([m], [])
    assert "custodian" in out


def test_custodian_locked_when_closed_quickly():
    born = NOW - timedelta(days=5)
    closed = NOW - timedelta(days=1)
    m = _mem("m1", column="closed", enriched_at=born, completed_at=closed)
    assert "custodian" not in achievements.evaluate([m], [])


def test_custodian_ignores_still_open_old_memories():
    born = NOW - timedelta(days=120)
    m = _mem("m1", column="memory", enriched_at=born)
    assert "custodian" not in achievements.evaluate([m], [])


# ----- storm (5 closures in one UTC day) ------------------------------------


def test_storm_unlocks_when_five_closures_share_a_day():
    day = NOW - timedelta(days=3)
    mems = [
        _mem(f"m{i}", column="closed", completed_at=day.replace(hour=i + 1))
        for i in range(5)
    ]
    out = achievements.evaluate(mems, [])
    assert "storm" in out


def test_storm_locked_when_closures_spread_across_days():
    mems = [
        _mem(f"m{i}", column="closed", completed_at=NOW - timedelta(days=i + 1))
        for i in range(5)
    ]
    assert "storm" not in achievements.evaluate(mems, [])


# ----- sharpshooter ---------------------------------------------------------


def test_sharpshooter_locked_on_empty_board_even_at_perfect_score():
    """Empty board scores 100 but we don't celebrate a phantom victory."""
    out = achievements.evaluate([], [], current_health=100)
    assert "sharpshooter" not in out
    assert "sprout" not in out


def test_sharpshooter_unlocks_at_health_95():
    out = achievements.evaluate([_mem("m1")], [], current_health=95)
    assert "sharpshooter" in out


def test_sharpshooter_locked_at_health_94():
    out = achievements.evaluate([_mem("m1")], [], current_health=94)
    assert "sharpshooter" not in out


def test_sharpshooter_locked_when_health_is_none():
    out = achievements.evaluate([_mem("m1")], [], current_health=None)
    assert "sharpshooter" not in out


# ----- clean week / streak keeper (history-derived) ------------------------


def _clean_history(n: int) -> list[dict]:
    return [
        {"date": (NOW - timedelta(days=n - i)).strftime("%Y-%m-%d"), "clean": True}
        for i in range(n)
    ]


def test_clean_week_unlocks_at_seven_consecutive_clean_days():
    out = achievements.evaluate([_mem("m1")], [], history=_clean_history(7))
    assert "clean-week" in out
    assert "streak-keeper" not in out


def test_clean_week_locked_at_six_days():
    out = achievements.evaluate([_mem("m1")], [], history=_clean_history(6))
    assert "clean-week" not in out


def test_streak_keeper_unlocks_at_thirty_consecutive_days():
    out = achievements.evaluate([_mem("m1")], [], history=_clean_history(30))
    assert "streak-keeper" in out
    assert "clean-week" in out


def test_clean_week_uses_longest_run_not_current():
    # Run of 8 clean days, then a dirty day, then 2 more clean. Longest = 8.
    history = (
        _clean_history(8)
        + [{"date": "2026-05-15", "clean": False}]
        + [{"date": "2026-06-04", "clean": True}, {"date": "2026-06-05", "clean": True}]
    )
    out = achievements.evaluate([_mem("m1")], [], history=history)
    assert "clean-week" in out


# ----- gardener (meta) ------------------------------------------------------


def test_gardener_locked_when_any_other_locked():
    # Have everything but storm.
    born = NOW - timedelta(days=45)
    closed = NOW - timedelta(days=2)
    mems = [
        _mem("m1", column="closed", enriched_at=born, completed_at=closed)
    ]
    vs = [_vial(f"v{i}") for i in range(100)]
    history = _clean_history(30)
    out = achievements.evaluate(mems, vs, current_health=99, history=history)
    assert "gardener" not in out
    assert "storm" not in out


def test_gardener_unlocks_when_all_others_unlock():
    # Construct conditions for every non-meta badge.
    day_with_storm = (NOW - timedelta(days=3)).replace(hour=10)
    born = NOW - timedelta(days=45)
    # 5 closures same day (storm) + the oldest = custodian source
    storm_mems = [
        _mem(
            f"s{i}",
            column="closed",
            enriched_at=born,  # so each also satisfies custodian individually
            completed_at=day_with_storm.replace(hour=i + 1),
        )
        for i in range(5)
    ]
    open_mem = _mem("m_open", column="memory")
    vs = [_vial(f"v{i}") for i in range(100)]
    history = _clean_history(30)
    out = achievements.evaluate(
        storm_mems + [open_mem], vs, current_health=99, history=history
    )
    assert "sprout" in out
    assert "scribe" in out
    assert "centurion" in out
    assert "custodian" in out
    assert "storm" in out
    assert "clean-week" in out
    assert "streak-keeper" in out
    assert "sharpshooter" in out
    assert "gardener" in out


# ----- definitions ----------------------------------------------------------


def test_definitions_lists_all_nine_badges():
    defs = achievements.definitions()
    ids = [d["id"] for d in defs]
    assert set(ids) == {
        "sprout", "scribe", "centurion", "custodian", "storm",
        "clean-week", "streak-keeper", "sharpshooter", "gardener",
    }
    for d in defs:
        assert d["emoji"]
        assert d["name"]
        assert d["description"]


# ----- build_level_summary --------------------------------------------------


def test_level_summary_empty_board_zero_counts():
    summary = achievements.build_level_summary([], [], now=NOW, history=[])
    assert summary["closed_this_week"] == 0
    assert summary["closed_prev_week"] == 0
    assert summary["captured_this_week"] == 0
    assert summary["capture_rate_pct"] is None
    assert summary["health_now"] is None
    assert summary["health_prev_week"] is None
    assert summary["health_delta"] is None
    assert summary["current_streak_d"] == 0
    assert summary["longest_streak_d"] == 0


def test_level_summary_counts_this_week_vs_prev_week():
    this_week = _mem("a", column="closed", completed_at=NOW - timedelta(days=2))
    prev_week = _mem("b", column="closed", completed_at=NOW - timedelta(days=10))
    ancient = _mem("c", column="closed", completed_at=NOW - timedelta(days=200))
    summary = achievements.build_level_summary(
        [this_week, prev_week, ancient], [], now=NOW
    )
    assert summary["closed_this_week"] == 1
    assert summary["closed_prev_week"] == 1


def test_level_summary_capture_rate():
    closed = [
        _mem(f"c{i}", column="closed", completed_at=NOW - timedelta(days=2))
        for i in range(4)
    ]
    vials = [_vial(f"v{i}", mid="c0") for i in range(2)]
    summary = achievements.build_level_summary(closed, vials, now=NOW)
    assert summary["closed_this_week"] == 4
    assert summary["captured_this_week"] == 2
    assert summary["capture_rate_pct"] == 50


def test_level_summary_health_delta_uses_history_snapshots():
    history = [
        {"date": (NOW - timedelta(days=8)).strftime("%Y-%m-%d"), "clean": True,
         "health_score": 70},
        {"date": (NOW - timedelta(days=1)).strftime("%Y-%m-%d"), "clean": True,
         "health_score": 92},
    ]
    summary = achievements.build_level_summary(
        [_mem("m1")], [], now=NOW, history=history
    )
    assert summary["health_now"] == 92
    assert summary["health_prev_week"] == 70
    assert summary["health_delta"] == 22


def test_level_summary_health_delta_none_when_history_missing_scores():
    history = [
        {"date": (NOW - timedelta(days=8)).strftime("%Y-%m-%d"), "clean": True},
        {"date": (NOW - timedelta(days=1)).strftime("%Y-%m-%d"), "clean": True},
    ]
    summary = achievements.build_level_summary(
        [_mem("m1")], [], now=NOW, history=history
    )
    assert summary["health_now"] is None
    assert summary["health_prev_week"] is None
    assert summary["health_delta"] is None


def test_level_summary_current_streak_from_tail():
    history = (
        [{"date": "2026-05-30", "clean": False}]
        + [
            {"date": (NOW - timedelta(days=i)).strftime("%Y-%m-%d"), "clean": True}
            for i in range(5, 0, -1)
        ]
    )
    summary = achievements.build_level_summary(
        [_mem("m1")], [], now=NOW, history=history
    )
    assert summary["current_streak_d"] == 5
    assert summary["longest_streak_d"] == 5
