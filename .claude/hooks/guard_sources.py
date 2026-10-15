#!/usr/bin/env python3
"""PreToolUse hook: keep TaskSource implementations read-only.

AGENTS.md hard rule: sources never mutate. tests/test_sources.py enforces it
at test time; this hook enforces it at edit time, blocking any Write/Edit
that introduces a mutation method into pensieve/sources/ (sink.py excluded,
it is the one sanctioned writeback path).

Exit 2 blocks the tool call and returns stderr to the model.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_DIR = REPO_ROOT / "pensieve" / "sources"

FORBIDDEN_DEF_RE = re.compile(
    r"^\s*def\s+(save|update_task|patch|delete_task|set_notes|create_task)\s*\(",
    re.MULTILINE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or ""
    if not raw_path:
        return 0

    try:
        target = Path(raw_path)
        if not target.is_absolute():
            target = REPO_ROOT / target
        target = target.resolve()
        target.relative_to(SOURCES_DIR)
    except (OSError, ValueError):
        return 0  # not under pensieve/sources/

    if target.name == "sink.py":
        return 0  # the sanctioned, namespaced writeback path

    new_text = "".join(
        str(tool_input.get(k) or "") for k in ("content", "new_string")
    )
    match = FORBIDDEN_DEF_RE.search(new_text)
    if match:
        print(
            f"BLOCKED: adding `def {match.group(1)}(` to {target.name} violates the "
            "read-only source contract (AGENTS.md hard rule, enforced by "
            "tests/test_sources.py). Sources never mutate; writeback goes through "
            "the namespaced TaskSink in pensieve/sources/sink.py only.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
