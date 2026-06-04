"""Pure-function tests for pensieve.garden (no I/O, no fixtures)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pensieve import garden
from pensieve.store.schema import Memory


UTC = timezone.utc
NOW = datetime(2026, 6, 5, 12, 0, 0, tzinfo=UTC)


def _mem(
    *,
    mid: str = "m1",
    column: str = "memory",
    last_tended_at: datetime | None = None,
    enriched_at: datetime | None = None,
    due_date: datetime | None = None,
) -> Memory:
    return Memory(
        id=mid,
        source="sample_file",
        source_task_id=mid,
        title=f"Memory {mid}",
        column=column,
        last_tended_at=last_tended_at,
        enriched_at=enriched_at or NOW - timedelta(days=1),
        due_date=due_date,
    )


# --- derive_freshness -------------------------------------------------------


def test_freshness_fresh_when_tended_today():
    m = _mem(last_tended_at=NOW - timedelta(hours=2))
    assert garden.derive_freshness(m, NOW) == "fresh"


def test_freshness_active_for_5_days():
    m = _mem(last_tended_at=NOW - timedelta(days=5))
    assert garden.derive_freshness(m, NOW) == "active"


def test_freshness_stale_for_10_days():
    m = _mem(last_tended_at=NOW - timedelta(days=10))
    assert garden.derive_freshness(m, NOW) == "stale"


def test_freshness_stale_for_25_days():
    m = _mem(last_tended_at=NOW - timedelta(days=25))
    assert garden.derive_freshness(m, NOW) == "stale"


def test_freshness_ghost_for_40_days():
    m = _mem(last_tended_at=NOW - timedelta(days=40))
    assert garden.derive_freshness(m, NOW) == "ghost"


def test_freshness_closed_without_vial_is_neutral():
    """Closed cards without a captured Vial are NOT stale; they get
    the pending_closure_capture chevron instead."""
    m = _mem(column="closed", last_tended_at=NOW - timedelta(days=40))
    assert garden.derive_freshness(m, NOW, has_captured_vial=False) == "closed"


def test_freshness_closed_with_captured_vial():
    m = _mem(column="closed", last_tended_at=NOW - timedelta(days=2))
    assert garden.derive_freshness(m, NOW, has_captured_vial=True) == "closed_vialed"


def test_freshness_backfills_from_enriched_at_when_no_tend():
    """No last_tended_at: should fall back to enriched_at."""
    m = _mem(
        last_tended_at=None,
        enriched_at=NOW - timedelta(days=10),
    )
    assert garden.derive_freshness(m, NOW) == "stale"


def test_freshness_naive_due_date_doesnt_crash():
    """Outlook can deliver naive datetimes. Must not raise."""
    naive_due = datetime(2026, 1, 1)  # naive
    m = _mem(column="memory", due_date=naive_due)
    assert garden.is_overdue(m, NOW) is True


def test_freshness_naive_tended_doesnt_crash():
    naive_tended = datetime(2026, 5, 1)  # naive
    m = _mem(last_tended_at=naive_tended)
    f = garden.derive_freshness(m, NOW)
    assert f in {"fresh", "active", "stale", "ghost"}


# --- is_overdue -------------------------------------------------------------


def test_overdue_true_for_past_due_open():
    m = _mem(column="memory", due_date=NOW - timedelta(days=2))
    assert garden.is_overdue(m, NOW) is True


def test_overdue_false_when_due_in_future():
    m = _mem(column="dive", due_date=NOW + timedelta(days=1))
    assert garden.is_overdue(m, NOW) is False


def test_overdue_false_when_no_due_date():
    m = _mem(column="memory", due_date=None)
    assert garden.is_overdue(m, NOW) is False


def test_overdue_false_for_closed_card_even_if_past():
    m = _mem(column="closed", due_date=NOW - timedelta(days=10))
    assert garden.is_overdue(m, NOW) is False


# --- compute_board_health ---------------------------------------------------


def test_health_perfect_board_returns_100():
    mems = [
        _mem(mid="a", last_tended_at=NOW - timedelta(hours=1)),
        _mem(mid="b", last_tended_at=NOW - timedelta(hours=1)),
    ]
    r = garden.compute_board_health(mems, NOW)
    assert r["score"] == 100
    assert r["terms"]["stale_count"] == 0
    assert r["terms"]["ghost_count"] == 0


def test_health_empty_board_returns_100():
    r = garden.compute_board_health([], NOW)
    assert r["score"] == 100
    assert r["counts"]["open"] == 0
    assert r["counts"]["closed"] == 0


def test_health_ghost_heavy_board_low_score():
    mems = [_mem(mid=f"m{i}", last_tended_at=NOW - timedelta(days=40)) for i in range(5)]
    r = garden.compute_board_health(mems, NOW)
    # 5 ghost penalty (5 * 10 = 50) + stale_pct=0 (none are stale, all ghost)
    # = 100 - 0 - 0 - 50 = 50
    assert r["score"] == 50
    assert r["terms"]["ghost_count"] == 5


def test_health_overdue_costs_5_per_card():
    mems = [
        _mem(
            mid=f"m{i}",
            column="memory",
            last_tended_at=NOW,
            due_date=NOW - timedelta(days=1),
        )
        for i in range(3)
    ]
    r = garden.compute_board_health(mems, NOW)
    # 100 - 0 stale - 3*5 overdue - 0 ghost = 85
    assert r["score"] == 85
    assert r["terms"]["overdue_count"] == 3


def test_health_capture_pct_uses_captured_only_not_skipped():
    """Skipped Vials must NOT earn capture credit (Skip ≠ Capture)."""
    closed_with_captured = _mem(mid="cap", column="closed", last_tended_at=NOW)
    closed_with_skipped = _mem(mid="skp", column="closed", last_tended_at=NOW)
    captured_counts = {"cap": 1}  # only cap has a CAPTURED vial; skp was skipped
    r = garden.compute_board_health(
        [closed_with_captured, closed_with_skipped],
        NOW,
        captured_counts=captured_counts,
    )
    # capture_pct = 1/2 = 0.5 → +5 boost
    assert r["terms"]["capture_pct"] == 0.5
    assert r["counts"]["captured_closed"] == 1


def test_health_clamped_at_zero():
    """Many ghosts shouldn't drive score negative."""
    mems = [_mem(mid=f"m{i}", last_tended_at=NOW - timedelta(days=60)) for i in range(20)]
    r = garden.compute_board_health(mems, NOW)
    assert r["score"] == 0


def test_health_quest_bonus_applies():
    mems = [_mem(mid="a", last_tended_at=NOW)]
    r = garden.compute_board_health(mems, NOW, quest_bonus=5)
    # Perfect base 100 stays at 100 (clamped), but bonus is in terms
    assert r["terms"]["quest_bonus"] == 5


def test_health_clean_streak_capped_at_10():
    mems = [_mem(mid="a", last_tended_at=NOW - timedelta(days=10))]
    r1 = garden.compute_board_health(mems, NOW, clean_streak_d=5)
    r2 = garden.compute_board_health(mems, NOW, clean_streak_d=999)
    # stale_pct=1, so -30 baseline. r1 + 5 streak = 75. r2 + 10 streak (cap) = 80.
    assert r2["score"] - r1["score"] == 5


def test_board_health_tier():
    assert garden.board_health_tier(95) == "green"
    assert garden.board_health_tier(80) == "green"
    assert garden.board_health_tier(70) == "yellow"
    assert garden.board_health_tier(60) == "yellow"
    assert garden.board_health_tier(40) == "red"
