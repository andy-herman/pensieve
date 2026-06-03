"""Unit tests for the TaskSink interface helpers + OutlookCOMSink stubs.

The COM-touching paths are exercised via a fake item so the test runs on
machines without Outlook installed (CI, second devbox, etc.).
"""

from __future__ import annotations

import pytest

from pensieve.sources.outlook_com_sink import OutlookCOMSink, get_sink_for_source
from pensieve.sources.sink import (
    TaskSink,
    extract_pensieve_column,
    merge_pensieve_tag,
)

PREFIX = "pensieve/col:"


# ---------- merge_pensieve_tag ----------


def test_merge_drops_existing_pensieve_tag_and_appends_new():
    cats = ["Work", "pensieve/col:memory", "Personal"]
    out = merge_pensieve_tag(cats, "dive", prefix=PREFIX)
    assert out == ["Work", "Personal", "pensieve/col:dive"]


def test_merge_preserves_user_categories_byte_for_byte():
    cats = ["Customer A/B", "Mid-quarter Review"]
    out = merge_pensieve_tag(cats, "review", prefix=PREFIX)
    assert out == ["Customer A/B", "Mid-quarter Review", "pensieve/col:review"]


def test_merge_with_none_column_strips_pensieve_tags_only():
    cats = ["Work", "pensieve/col:dive", "pensieve/col:closed", "Personal"]
    out = merge_pensieve_tag(cats, None, prefix=PREFIX)
    assert out == ["Work", "Personal"]


def test_merge_is_idempotent_when_already_correct():
    cats = ["Work", "pensieve/col:dive"]
    out = merge_pensieve_tag(cats, "dive", prefix=PREFIX)
    assert out == ["Work", "pensieve/col:dive"]


def test_merge_prefix_match_is_case_insensitive():
    cats = ["Work", "Pensieve/Col:memory"]
    out = merge_pensieve_tag(cats, "dive", prefix=PREFIX)
    # original-case tag dropped, new tag uses the configured prefix exactly
    assert out == ["Work", "pensieve/col:dive"]


def test_merge_custom_prefix():
    cats = ["Work", "pensieve:memory"]
    out = merge_pensieve_tag(cats, "dive", prefix="pensieve:")
    assert out == ["Work", "pensieve:dive"]


def test_merge_empty_input():
    assert merge_pensieve_tag([], "dive", prefix=PREFIX) == ["pensieve/col:dive"]
    assert merge_pensieve_tag([], None, prefix=PREFIX) == []


# ---------- extract_pensieve_column ----------


def test_extract_returns_first_match():
    cats = ["Work", "pensieve/col:dive", "pensieve/col:review"]
    assert extract_pensieve_column(cats, prefix=PREFIX) == "dive"


def test_extract_returns_none_when_absent():
    cats = ["Work", "Personal"]
    assert extract_pensieve_column(cats, prefix=PREFIX) is None


def test_extract_handles_whitespace_in_column():
    cats = ["pensieve/col:  dive  "]
    assert extract_pensieve_column(cats, prefix=PREFIX) == "dive"


def test_extract_empty_column_returns_none():
    cats = ["pensieve/col:"]
    assert extract_pensieve_column(cats, prefix=PREFIX) is None


def test_extract_case_insensitive_on_prefix():
    cats = ["Pensieve/Col:dive"]
    assert extract_pensieve_column(cats, prefix=PREFIX) == "dive"


# ---------- OutlookCOMSink with a fake COM item ----------


class _FakeItem:
    """Minimal stand-in for a `MailItem` / `TaskItem` COM dispatch object."""

    def __init__(self, categories: str = "", complete: bool = False) -> None:
        self.Categories = categories
        self.Complete = complete
        self.save_calls = 0
        self.mark_complete_calls = 0

    def Save(self) -> None:
        self.save_calls += 1

    def MarkComplete(self) -> None:
        self.mark_complete_calls += 1
        self.Complete = True


class _SinkUnderTest(OutlookCOMSink):
    """Subclass that swaps the COM lookup for a dict lookup."""

    def __init__(self, items: dict[str, _FakeItem]) -> None:
        super().__init__()
        self._items = items

    def _connect(self) -> None:  # pragma: no cover - bypassed in tests
        return

    def _get_item(self, task_id: str):
        return self._items.get(task_id)


def test_set_column_tag_writes_new_tag_and_saves():
    item = _FakeItem(categories="Work, Personal")
    sink = _SinkUnderTest({"abc": item})
    assert sink.set_column_tag("abc", "dive", prefix=PREFIX) is True
    assert item.Categories == "Work, Personal, pensieve/col:dive"
    assert item.save_calls == 1


def test_set_column_tag_replaces_existing_pensieve_tag():
    item = _FakeItem(categories="Work, pensieve/col:memory, Personal")
    sink = _SinkUnderTest({"abc": item})
    sink.set_column_tag("abc", "review", prefix=PREFIX)
    assert item.Categories == "Work, Personal, pensieve/col:review"
    assert item.save_calls == 1


def test_set_column_tag_skips_save_when_unchanged():
    item = _FakeItem(categories="Work, pensieve/col:dive")
    sink = _SinkUnderTest({"abc": item})
    sink.set_column_tag("abc", "dive", prefix=PREFIX)
    assert item.save_calls == 0


def test_set_column_tag_returns_false_when_task_missing():
    sink = _SinkUnderTest({})
    assert sink.set_column_tag("ghost", "dive", prefix=PREFIX) is False


def test_clear_column_tag_strips_only_pensieve_tags():
    item = _FakeItem(categories="Work, pensieve/col:dive, Personal")
    sink = _SinkUnderTest({"abc": item})
    sink.clear_column_tag("abc", prefix=PREFIX)
    assert item.Categories == "Work, Personal"
    assert item.save_calls == 1


def test_clear_column_tag_is_noop_when_no_pensieve_tag():
    item = _FakeItem(categories="Work, Personal")
    sink = _SinkUnderTest({"abc": item})
    sink.clear_column_tag("abc", prefix=PREFIX)
    assert item.save_calls == 0


# ---------- set_completion (PENSIEVE_MIRROR_COMPLETION writeback) ----------


def test_set_completion_uses_MarkComplete_and_saves():
    item = _FakeItem(complete=False)
    sink = _SinkUnderTest({"abc": item})
    assert sink.set_completion("abc", True) is True
    assert item.mark_complete_calls == 1
    assert item.Complete is True
    assert item.save_calls == 1


def test_set_completion_is_noop_when_already_complete():
    """If the source is already complete, no MarkComplete / Save call is made.
    This keeps auto-sync re-confirmations cheap and avoids touching
    DateCompleted on tasks the user closed manually.
    """
    item = _FakeItem(complete=True)
    sink = _SinkUnderTest({"abc": item})
    assert sink.set_completion("abc", True) is True
    assert item.mark_complete_calls == 0
    assert item.save_calls == 0


def test_set_completion_uses_property_fallback_when_marker_missing():
    """If the COM object lacks MarkComplete (e.g. MailItem flagged as task),
    fall back to ``item.Complete = True`` + Save."""

    class _ItemNoMark:
        def __init__(self) -> None:
            self.Complete = False
            self.save_calls = 0

        def Save(self) -> None:
            self.save_calls += 1

    item = _ItemNoMark()
    sink = _SinkUnderTest({"abc": item})  # type: ignore[arg-type]
    assert sink.set_completion("abc", True) is True
    assert item.Complete is True
    assert item.save_calls == 1


def test_set_completion_to_false_uses_property_assignment():
    """v1 is one-way (close-only) so the API layer never calls
    ``set_completion(False)``, but the sink still implements it for symmetry
    and because Outlook has no inverse ``MarkIncomplete()``.
    """
    item = _FakeItem(complete=True)
    sink = _SinkUnderTest({"abc": item})
    assert sink.set_completion("abc", False) is True
    assert item.mark_complete_calls == 0
    assert item.Complete is False
    assert item.save_calls == 1


def test_set_completion_returns_false_when_task_missing():
    sink = _SinkUnderTest({})
    assert sink.set_completion("ghost", True) is False


# ---------- get_sink_for_source ----------


def test_get_sink_returns_outlook_sink_for_matching_source():
    assert isinstance(get_sink_for_source("outlook_com"), OutlookCOMSink)


def test_get_sink_returns_none_for_unknown_source():
    assert get_sink_for_source("sample_file") is None
    assert get_sink_for_source(None) is None


# ---------- TaskSink contract is read-only-safe ----------


def test_taskSink_is_distinct_from_taskSource():
    """The mirror writer must NOT live on the TaskSource hierarchy.

    This locks in the AGENTS.md "Sources are read-only" invariant: even if a
    future refactor merges interfaces, this test will trip and force the
    author to re-justify it.
    """
    from pensieve.sources.base import TaskSource

    assert not issubclass(OutlookCOMSink, TaskSource)
    assert not issubclass(TaskSink, TaskSource)


def test_outlook_sink_has_no_read_surface():
    """The sink must not accidentally expose the source's read methods."""
    forbidden = {"list_tasks", "get_task", "discover_lists", "covered_lists"}
    leaked = forbidden & set(dir(OutlookCOMSink))
    assert not leaked, f"OutlookCOMSink leaks read methods: {leaked}"


# ---------- Connection failure surfaces a clean error ----------


def test_real_sink_raises_outlookCOMUnavailable_when_pywin32_missing(monkeypatch):
    sink = OutlookCOMSink()

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

    def fake_import(name, *args, **kwargs):
        if name == "win32com.client":
            raise ImportError("no pywin32")
        return real_import(name, *args, **kwargs)

    monkeypatch.setitem(
        __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__, "__import__", fake_import
    )

    from pensieve.sources.outlook_com import OutlookCOMUnavailable

    with pytest.raises(OutlookCOMUnavailable):
        sink._connect()
