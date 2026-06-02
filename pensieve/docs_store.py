"""Markdown document store for the in-app Documents tab.

SOPs and tool docs are stored as plain .md files under data_dir/docs/. Each
document's title is its first level-1 heading (``# Title``); the file stem is its
id. First access seeds a couple of starter docs so the tab is never empty.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from pensieve.config import Settings, get_settings

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def _docs_dir(settings: Settings) -> Path:
    d = settings.data_dir / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(title: str) -> str:
    s = _SLUG_STRIP.sub("-", (title or "").strip().lower()).strip("-")
    return s or "untitled"


def _title_of(content: str, fallback: str) -> str:
    m = _H1.search(content or "")
    return m.group(1).strip() if m else fallback


_SEED_OVERVIEW = """# What is Pensieve

Pensieve is a memory store for your work. It sits on top of Microsoft To-Do and
enriches each task with the context To-Do cannot hold: the *why*, the project or
strand it belongs to, the impact, and how it aligns to your committed Connect
goals.

## How it works

1. **Pull from To-Do** - Pensieve reads your tasks (read-only) from Outlook.
2. **Enrich** - each task is turned into a "memory" with a why, an impact, a
   strand, and Connect-goal alignment, using Azure OpenAI.
3. **Board** - work flows across four columns: Memory, Dive, Review, Closed.
   Switch to the Lanes view to group by Connect goal.
4. **Recap** - draft a Connect "Reflect on the past" summary of what you
   accomplished, grouped by goal. Export to DOCX, keep a run history, and chat
   to correct any misread task.
5. **Graph** - a Constellation view of your tasks: goal hubs, task nodes, and
   semantic links derived from the same embeddings that power search.

## Tips

- Use the **This week** toggle to keep the Closed column from growing forever;
  it hides closed tasks from before this Monday (nothing is deleted).
- Add or edit lanes from the Lanes view ("+ Add lane") or the Set goals editor.
"""

_SEED_SOP = """# SOP Template

Use this template to write a standard operating procedure.

## Purpose

What this procedure is for and when to use it.

## Prerequisites

- Access or tools needed
- Anything to prepare first

## Steps

1. First step
2. Second step
3. Third step

## Verification

How to confirm it worked.

## Troubleshooting

- Symptom -> fix
"""


def _seed_if_empty(settings: Settings) -> None:
    d = _docs_dir(settings)
    if any(d.glob("*.md")):
        return
    (d / "what-is-pensieve.md").write_text(_SEED_OVERVIEW, encoding="utf-8")
    (d / "sop-template.md").write_text(_SEED_SOP, encoding="utf-8")


def list_docs(settings: Optional[Settings] = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    _seed_if_empty(settings)
    out: list[dict[str, Any]] = []
    for path in sorted(_docs_dir(settings).glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        out.append(
            {
                "id": path.stem,
                "title": _title_of(content, path.stem),
                "updated": path.stat().st_mtime,
            }
        )
    out.sort(key=lambda r: r["title"].lower())
    return out


def read_doc(doc_id: str, settings: Optional[Settings] = None) -> Optional[dict[str, Any]]:
    settings = settings or get_settings()
    path = _docs_dir(settings) / f"{slugify(doc_id)}.md"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    return {"id": path.stem, "title": _title_of(content, path.stem), "content": content}


def save_doc(doc_id: str, content: str, settings: Optional[Settings] = None) -> dict[str, Any]:
    settings = settings or get_settings()
    sid = slugify(doc_id)
    path = _docs_dir(settings) / f"{sid}.md"
    path.write_text(content or "", encoding="utf-8")
    return {"id": sid, "title": _title_of(content, sid)}


def create_doc(title: str, settings: Optional[Settings] = None) -> dict[str, Any]:
    settings = settings or get_settings()
    title = (title or "Untitled").strip() or "Untitled"
    base = slugify(title)
    d = _docs_dir(settings)
    sid = base
    n = 1
    while (d / f"{sid}.md").exists():
        n += 1
        sid = f"{base}-{n}"
    content = f"# {title}\n\n"
    (d / f"{sid}.md").write_text(content, encoding="utf-8")
    return {"id": sid, "title": title, "content": content}


def delete_doc(doc_id: str, settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    path = _docs_dir(settings) / f"{slugify(doc_id)}.md"
    if path.exists():
        path.unlink()
        return True
    return False
