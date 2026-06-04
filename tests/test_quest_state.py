"""Garden v2: quest_state persistence + day rollover + streak math tests."""

from __future__ import annotations

from datetime import datetime, timezone

from pensieve import quest_state, quests

UTC = timezone.utc
NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "garden-quests.json"
    state = quest_state.QuestState(
        today=quest_state.TodayRow(
            date="2026-06-05",
            generated_at=NOW,
            quests=[
                quests.Quest(
                    id="q1", kind="bury-ghost", title="t", description="d",
                    target_memory_ids=["g"],
                ),
            ],
        ),
        clean_streak_d=3,
        history=[
            {"date": "2026-06-04", "clean": True},
            {"date": "2026-06-03", "clean": True},
            {"date": "2026-06-02", "clean": True},
        ],
    )
    quest_state.save_state(state, path)
    assert path.exists()
    back = quest_state.load_state(path)
    assert back.clean_streak_d == 3
    assert back.today is not None
    assert back.today.date == "2026-06-05"
    assert len(back.today.quests) == 1
    assert back.today.quests[0].kind == "bury-ghost"
    assert len(back.history) == 3


def test_load_missing_file_returns_empty_state(tmp_path):
    state = quest_state.load_state(tmp_path / "nope.json")
    assert state.today is None
    assert state.clean_streak_d == 0
    assert state.history == []


def test_load_corrupted_file_returns_empty_state(tmp_path):
    path = tmp_path / "garden-quests.json"
    path.write_text("{ this is not json", encoding="utf-8")
    state = quest_state.load_state(path)
    assert state.today is None
    assert state.clean_streak_d == 0


def test_is_today_row_matches_calendar_day():
    row = quest_state.TodayRow(date="2026-06-05", generated_at=NOW)
    assert quest_state.is_today_row(row, NOW)
    # Different calendar day → False
    next_day = datetime(2026, 6, 6, 0, 1, 0, tzinfo=UTC)
    assert not quest_state.is_today_row(row, next_day)
    # Same day late evening → True
    same_day_late = datetime(2026, 6, 5, 23, 59, 0, tzinfo=UTC)
    assert quest_state.is_today_row(row, same_day_late)


def test_is_today_row_returns_false_for_none():
    assert not quest_state.is_today_row(None, NOW)


def test_record_yesterday_clean_appends_and_bumps_streak():
    state = quest_state.QuestState(
        history=[
            {"date": "2026-06-03", "clean": True},
            {"date": "2026-06-04", "clean": True},
        ],
        clean_streak_d=2,
    )
    # Today is 2026-06-05 → record yesterday = 2026-06-04 was already there;
    # overwrite (not duplicate) and bump streak.
    quest_state.record_yesterday_clean(state, was_clean=True, now=NOW)
    assert len(state.history) == 2  # no duplicate
    # Walk back: 06-04 clean + 06-03 clean = 2 (history hasn't grown).
    assert state.clean_streak_d == 2


def test_record_yesterday_clean_new_day_appends():
    state = quest_state.QuestState(
        history=[{"date": "2026-06-03", "clean": True}],
        clean_streak_d=1,
    )
    # Today is 2026-06-05; yesterday=06-04 is NEW.
    quest_state.record_yesterday_clean(state, was_clean=True, now=NOW)
    assert state.history[-1] == {"date": "2026-06-04", "clean": True}
    assert state.clean_streak_d == 2


def test_record_yesterday_dirty_resets_streak():
    state = quest_state.QuestState(
        history=[
            {"date": "2026-06-02", "clean": True},
            {"date": "2026-06-03", "clean": True},
            {"date": "2026-06-04", "clean": True},
        ],
        clean_streak_d=3,
    )
    # Overwrite 06-04 as dirty → streak collapses
    quest_state.record_yesterday_clean(state, was_clean=False, now=NOW)
    assert state.clean_streak_d == 0
    assert state.history[-1] == {"date": "2026-06-04", "clean": False}


def test_record_yesterday_clean_caps_history_length(tmp_path):
    state = quest_state.QuestState(
        history=[
            {"date": f"2025-06-{i:02d}", "clean": True}
            for i in range(1, 30)
        ] + [
            {"date": f"2025-07-{i:02d}", "clean": True}
            for i in range(1, 30)
        ] + [
            {"date": f"2025-08-{i:02d}", "clean": True}
            for i in range(1, 30)
        ] + [
            {"date": f"2025-09-{i:02d}", "clean": True}
            for i in range(1, 30)
        ] + [
            {"date": f"2025-10-{i:02d}", "clean": True}
            for i in range(1, 30)
        ],
    )
    quest_state.record_yesterday_clean(state, was_clean=True, now=NOW)
    assert len(state.history) <= quest_state.MAX_HISTORY_ENTRIES


def test_quest_bonus_today_zero_when_pending():
    q = quests.Quest(id="x", kind="bury-ghost", title="t", description="d")
    state = quest_state.QuestState(
        today=quest_state.TodayRow(
            date="2026-06-05", generated_at=NOW, quests=[q],
        ),
    )
    assert quest_state.quest_bonus_today(state) == 0


def test_quest_bonus_today_five_when_all_done():
    q = quests.Quest(
        id="x", kind="bury-ghost", title="t", description="d",
        completed_at=NOW,
    )
    state = quest_state.QuestState(
        today=quest_state.TodayRow(
            date="2026-06-05", generated_at=NOW, quests=[q],
        ),
    )
    assert quest_state.quest_bonus_today(state) == 5


def test_quest_bonus_today_zero_for_empty_quests():
    state = quest_state.QuestState(
        today=quest_state.TodayRow(
            date="2026-06-05", generated_at=NOW, quests=[],
        ),
    )
    assert quest_state.quest_bonus_today(state) == 0


def test_quest_bonus_today_zero_when_no_today_row():
    assert quest_state.quest_bonus_today(quest_state.QuestState()) == 0


def test_save_then_corrupt_recovers_gracefully(tmp_path):
    path = tmp_path / "garden-quests.json"
    state = quest_state.QuestState(clean_streak_d=5)
    quest_state.save_state(state, path)
    assert quest_state.load_state(path).clean_streak_d == 5
    # Corrupt the file and reload — should return empty default, not raise.
    path.write_text("xxx not json xxx", encoding="utf-8")
    recovered = quest_state.load_state(path)
    assert recovered.clean_streak_d == 0
    # And a fresh save should overwrite cleanly.
    quest_state.save_state(quest_state.QuestState(clean_streak_d=7), path)
    assert quest_state.load_state(path).clean_streak_d == 7
