"""Garden v3: persistence + merge_unlocked tests for AchievementState."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pensieve import achievement_state

UTC = timezone.utc
NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "achievements.json"
    state = achievement_state.AchievementState(
        unlocked=[
            achievement_state.UnlockedEntry(id="sprout", unlocked_at=NOW),
            achievement_state.UnlockedEntry(
                id="scribe", unlocked_at=NOW + timedelta(hours=2)
            ),
        ]
    )
    achievement_state.save_state(state, path)
    back = achievement_state.load_state(path)
    assert back.unlocked_ids() == {"sprout", "scribe"}
    ts_by_id = {u.id: u.unlocked_at for u in back.unlocked}
    assert ts_by_id["sprout"] == NOW
    assert ts_by_id["scribe"] == NOW + timedelta(hours=2)


def test_load_missing_file_returns_empty(tmp_path):
    state = achievement_state.load_state(tmp_path / "nope.json")
    assert state.unlocked == []


def test_load_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "achievements.json"
    path.write_text("{ not valid json", encoding="utf-8")
    assert achievement_state.load_state(path).unlocked == []


def test_load_non_dict_root_returns_empty(tmp_path):
    path = tmp_path / "achievements.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert achievement_state.load_state(path).unlocked == []


def test_save_then_load_deduplicates_ids(tmp_path):
    path = tmp_path / "achievements.json"
    # Hand-craft a payload with a duplicate ID — load should dedupe.
    import json
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "unlocked": [
                    {"id": "sprout", "unlocked_at": NOW.isoformat()},
                    {"id": "sprout", "unlocked_at": NOW.isoformat()},
                    {"id": "scribe", "unlocked_at": NOW.isoformat()},
                ],
            }
        ),
        encoding="utf-8",
    )
    state = achievement_state.load_state(path)
    assert state.unlocked_ids() == {"sprout", "scribe"}
    assert len(state.unlocked) == 2


def test_merge_unlocked_adds_new_ids_and_returns_them():
    state = achievement_state.AchievementState(
        unlocked=[achievement_state.UnlockedEntry(id="sprout", unlocked_at=NOW)]
    )
    state, new_ids = achievement_state.merge_unlocked(
        state, {"sprout", "scribe", "centurion"}, NOW + timedelta(minutes=5)
    )
    assert new_ids == {"scribe", "centurion"}
    assert state.unlocked_ids() == {"sprout", "scribe", "centurion"}
    # Original Sprout timestamp preserved.
    sprout = next(u for u in state.unlocked if u.id == "sprout")
    assert sprout.unlocked_at == NOW


def test_merge_unlocked_empty_when_nothing_new():
    state = achievement_state.AchievementState(
        unlocked=[achievement_state.UnlockedEntry(id="sprout", unlocked_at=NOW)]
    )
    state, new_ids = achievement_state.merge_unlocked(state, {"sprout"}, NOW)
    assert new_ids == set()


def test_merge_unlocked_never_re_locks():
    state = achievement_state.AchievementState(
        unlocked=[
            achievement_state.UnlockedEntry(id="sprout", unlocked_at=NOW),
            achievement_state.UnlockedEntry(id="sharpshooter", unlocked_at=NOW),
        ]
    )
    # Predicate says sharpshooter no longer holds (health dipped); merge must
    # NOT remove it.
    state, new_ids = achievement_state.merge_unlocked(state, {"sprout"}, NOW)
    assert new_ids == set()
    assert state.unlocked_ids() == {"sprout", "sharpshooter"}


def test_save_is_atomic_tmp_then_replace(tmp_path):
    """Sanity: after save, only the target file exists, no .tmp left over."""
    path = tmp_path / "achievements.json"
    state = achievement_state.AchievementState(
        unlocked=[achievement_state.UnlockedEntry(id="sprout", unlocked_at=NOW)]
    )
    achievement_state.save_state(state, path)
    assert path.exists()
    assert not (tmp_path / "achievements.json.tmp").exists()
