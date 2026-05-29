"""Structural tests for PersonalGraphSource (no network, no MSAL)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from pensieve.config import Settings
from pensieve.sources.base import RawTask, TaskSource
from pensieve.sources.personal_graph import (
    PersonalGraphSource,
    PersonalGraphUnavailable,
    _parse_graph_datetime,
    _parse_iso,
)


def _settings(**overrides) -> Settings:
    base = {
        "personal_graph_client_id": "00000000-0000-0000-0000-000000000000",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_personal_graph_implements_task_source():
    assert issubclass(PersonalGraphSource, TaskSource)


def test_personal_graph_no_write_methods():
    forbidden = {"save", "update_task", "patch", "delete_task", "set_notes", "create_task"}
    names = {n for n, _ in inspect.getmembers(PersonalGraphSource, predicate=inspect.isfunction)
             if not n.startswith("_")}
    leaked = names & forbidden
    assert not leaked, f"PersonalGraphSource has forbidden write methods: {leaked}"


def test_constructor_filters_blank_list_names():
    src = PersonalGraphSource(list_names=["  ", "", "Personal"], settings=_settings(), token="x")
    assert src.list_names == ["Personal"]


def test_constructor_defaults():
    src = PersonalGraphSource(settings=_settings(), token="x")
    assert src.list_names == []
    assert src.include_completed is True
    assert src.name == "personal_graph"


def test_covered_lists_starts_empty():
    src = PersonalGraphSource(settings=_settings(), token="x")
    assert src.covered_lists() is None


def test_to_raw_maps_graph_payload():
    src = PersonalGraphSource(settings=_settings(), token="x")
    raw = src._to_raw(
        {
            "id": "AAA==",
            "title": "Draft DORA paper",
            "body": {"content": "Outline + sources", "contentType": "text"},
            "status": "notStarted",
            "createdDateTime": "2026-05-20T10:00:00Z",
            "lastModifiedDateTime": "2026-05-21T12:00:00Z",
            "categories": ["work"],
        },
        list_name="Tasks",
    )
    assert isinstance(raw, RawTask)
    assert raw.id == "AAA=="
    assert raw.title == "Draft DORA paper"
    assert raw.notes == "Outline + sources"
    assert raw.list_name == "Tasks"
    assert raw.completed is False
    assert raw.categories == ["work"]
    assert raw.source == "personal_graph"
    assert raw.created_at == datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)


def test_to_raw_detects_completed():
    src = PersonalGraphSource(settings=_settings(), token="x")
    raw = src._to_raw(
        {
            "id": "BBB==",
            "title": "Done thing",
            "status": "completed",
            "completedDateTime": {"dateTime": "2026-05-22T15:00:00.0000000", "timeZone": "UTC"},
        },
        list_name="Personal",
    )
    assert raw.completed is True
    assert raw.completed_at is not None
    assert raw.completed_at.year == 2026


def test_parse_iso_handles_z_suffix():
    dt = _parse_iso("2026-05-20T10:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_parse_iso_handles_none_and_garbage():
    assert _parse_iso(None) is None
    assert _parse_iso("not-a-date") is None


def test_parse_graph_datetime_handles_wrapped_blob():
    dt = _parse_graph_datetime({"dateTime": "2026-05-20T10:00:00Z", "timeZone": "UTC"})
    assert dt is not None
    assert dt.year == 2026


def test_parse_graph_datetime_handles_none():
    assert _parse_graph_datetime(None) is None
    assert _parse_graph_datetime({}) is None


def test_acquire_token_without_msal_raises_unavailable(monkeypatch):
    """If msal is not importable AND no token injected, source surfaces a useful error."""
    src = PersonalGraphSource(settings=_settings())
    # Force the import inside _acquire_token to fail by shadowing the name in sys.modules.
    import sys

    real_msal = sys.modules.pop("msal", None)
    monkeypatch.setitem(sys.modules, "msal", None)
    try:
        with pytest.raises(PersonalGraphUnavailable, match="msal"):
            src._acquire_token()
    finally:
        if real_msal is not None:
            sys.modules["msal"] = real_msal
        else:
            sys.modules.pop("msal", None)
