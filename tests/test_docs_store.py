"""Tests for the Documents store (pensieve/docs_store.py)."""

from __future__ import annotations

from pensieve.config import Settings
from pensieve.docs_store import (
    create_doc,
    delete_doc,
    list_docs,
    read_doc,
    save_doc,
    slugify,
)


def _settings(tmp_path) -> Settings:
    s = Settings()
    s.data_dir = tmp_path
    return s


def test_slugify():
    assert slugify("What is Pensieve") == "what-is-pensieve"
    assert slugify("  SOP: Onboarding!! ") == "sop-onboarding"
    assert slugify("") == "untitled"


def test_list_seeds_when_empty(tmp_path):
    s = _settings(tmp_path)
    docs = list_docs(s)
    ids = {d["id"] for d in docs}
    assert "what-is-pensieve" in ids
    assert "sop-template" in ids


def test_create_read_save_roundtrip(tmp_path):
    s = _settings(tmp_path)
    created = create_doc("My Runbook", settings=s)
    assert created["id"] == "my-runbook"
    doc = read_doc("my-runbook", settings=s)
    assert doc is not None
    assert doc["title"] == "My Runbook"

    save_doc("my-runbook", "# My Runbook\n\nStep one.\n", settings=s)
    doc2 = read_doc("my-runbook", settings=s)
    assert "Step one." in doc2["content"]
    assert doc2["title"] == "My Runbook"


def test_create_dedupes_ids(tmp_path):
    s = _settings(tmp_path)
    a = create_doc("Dup", settings=s)
    b = create_doc("Dup", settings=s)
    assert a["id"] != b["id"]


def test_delete(tmp_path):
    s = _settings(tmp_path)
    create_doc("Temp Doc", settings=s)
    assert delete_doc("temp-doc", settings=s) is True
    assert read_doc("temp-doc", settings=s) is None
    assert delete_doc("temp-doc", settings=s) is False


def test_title_from_first_heading(tmp_path):
    s = _settings(tmp_path)
    save_doc("notes", "intro line\n\n# Real Title\n\nbody", settings=s)
    doc = read_doc("notes", settings=s)
    assert doc["title"] == "Real Title"
