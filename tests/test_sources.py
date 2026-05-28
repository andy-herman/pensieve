"""Tests for the SampleFileSource (no LLM, no Chroma)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from pensieve.sources.base import RawTask, TaskSource
from pensieve.sources.outlook_com import OutlookCOMSource
from pensieve.sources.sample_file import SampleFileSource

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_PATH = REPO_ROOT / "data" / "samples.json"


def test_sample_source_loads():
    src = SampleFileSource(SAMPLES_PATH)
    tasks = list(src.list_tasks())
    assert len(tasks) > 0
    assert all(isinstance(t, RawTask) for t in tasks)
    assert all(t.source == "sample_file" for t in tasks)


def test_sample_source_get_by_id():
    src = SampleFileSource(SAMPLES_PATH)
    first = next(iter(src.list_tasks()))
    again = src.get_task(first.id)
    assert again is not None
    assert again.id == first.id


def test_sample_source_strand_catalog():
    src = SampleFileSource(SAMPLES_PATH)
    assert len(src.strand_catalog) > 0


def test_sample_source_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SampleFileSource(tmp_path / "no-such.json")


def _public_methods(cls):
    return {
        n for n, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not n.startswith("_")
    }


def test_sources_are_read_only_no_write_methods():
    """Pull-only contract: source classes must not expose write methods."""
    forbidden = {"save", "update_task", "patch", "delete_task", "set_notes", "create_task"}
    for cls in (SampleFileSource, OutlookCOMSource):
        names = _public_methods(cls)
        leaked = names & forbidden
        assert not leaked, f"{cls.__name__} has forbidden write methods: {leaked}"


def test_taskSource_interface_contract():
    """All concrete sources implement TaskSource."""
    for cls in (SampleFileSource, OutlookCOMSource):
        assert issubclass(cls, TaskSource)
