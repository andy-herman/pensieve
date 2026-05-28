"""Pytest config — clear settings cache before each test."""

from __future__ import annotations

import pytest

from pensieve.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]
