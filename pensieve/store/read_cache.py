"""Process-wide cache for whole-collection Chroma reads.

One dashboard refresh asks for the full memory list and the full vial list
several times (memories, board health, quests, achievements), and the 30-second
poll repeats that even when nothing changed. In Chroma 0.6 every full ``get()``
walks every metadata row in SQLite, which dominated those endpoints.

This module keeps the raw ``get()`` result per collection and reuses it until
the database changes. Change detection uses SQLite's ``PRAGMA data_version`` on
a private read-only connection to Chroma's ``chroma.sqlite3``: the value changes
whenever any OTHER connection commits. That covers writes from every store
instance in this process (the API's, the sync worker's), direct collection
writes, and other processes such as a CLI sync. The version is read before the
fetch, so a write that lands mid-fetch leaves the snapshot tagged with the old
version and the next call refetches. A cached snapshot is therefore never older
than the last committed write.

If the version cannot be read for any reason, the cache steps aside and every
call goes straight to Chroma, which is the pre-cache behavior.

Callers must treat the returned object as read-only (it is shared between
calls). The stores rebuild fresh Memory / Vial objects from it on every call.
"""

from __future__ import annotations

import itertools
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")

DB_FILENAME = "chroma.sqlite3"
# Bound the number of databases we hold a connection to (tests create many).
_MAX_DATABASES = 8

# data_version numbering is per connection, so every version is paired with a
# token for the connection that produced it. A reopened connection can never
# match a snapshot taken through an earlier one.
Version = tuple[int, int]  # (connection token, data_version)

_lock = threading.Lock()
_tokens = itertools.count(1)
_conns: dict[str, tuple[int, sqlite3.Connection]] = {}
_snapshots: dict[tuple[str, str], tuple[Version, Any]] = {}


def db_key(chroma_dir: Path) -> str:
    """Stable cache key for a Chroma persist directory."""
    return str((Path(chroma_dir) / DB_FILENAME).resolve())


def _close(key: str) -> None:
    entry = _conns.pop(key, None)
    if entry is not None:
        try:
            entry[1].close()
        except Exception:
            pass
    for k in [k for k in _snapshots if k[0] == key]:
        _snapshots.pop(k, None)


def data_version(key: str) -> Optional[Version]:
    """Current (connection token, data_version) for the database at ``key``, or None."""
    with _lock:
        entry = _conns.get(key)
        if entry is None:
            path = Path(key)
            if not path.exists():
                return None
            try:
                conn = sqlite3.connect(
                    path.as_uri() + "?mode=ro",
                    uri=True,
                    timeout=5.0,
                    isolation_level=None,
                    check_same_thread=False,
                )
            except sqlite3.Error:
                return None
            entry = (next(_tokens), conn)
            _conns[key] = entry
            while len(_conns) > _MAX_DATABASES:
                _close(next(iter(_conns)))
        token, conn = entry
        try:
            return token, int(conn.execute("PRAGMA data_version").fetchone()[0])
        except sqlite3.Error:
            _close(key)
            return None


def cached_get(key: str, collection: str, fetch: Callable[[], T]) -> T:
    """Return ``fetch()``'s result, reusing the last one if the database is unchanged."""
    version = data_version(key)
    if version is None:
        return fetch()
    with _lock:
        hit = _snapshots.get((key, collection))
    if hit is not None and hit[0] == version:
        return hit[1]
    result = fetch()
    with _lock:
        _snapshots[(key, collection)] = (version, result)
    return result


def clear() -> None:
    """Drop every snapshot and close every connection (used by tests)."""
    with _lock:
        for key in list(_conns):
            _close(key)
        _snapshots.clear()
