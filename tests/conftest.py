"""Pytest config: clear process-wide caches around each test."""

from __future__ import annotations

import os

import pytest

# Never boot a real GitHub Copilot CLI from a TestClient's app startup.
os.environ["COPILOT_PREWARM"] = "0"

from pensieve.config import get_settings
from pensieve.enrichment import connect_goals


def _clear_caches() -> None:
    get_settings.cache_clear()  # type: ignore[attr-defined]
    # The goals catalog is cached per process, not per data dir, so a test that
    # points PENSIEVE_DATA_DIR at an empty tmp dir must not leak [] to others.
    connect_goals.load_connect_goals.cache_clear()  # type: ignore[attr-defined]
    connect_goals.goals_index.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    _clear_caches()
    yield
    _clear_caches()
