"""Vault bridge: lets Andy's other agents (Hermes/Yor, Luna, Loid) see what he is
working on and ask Pensieve to add a task, through the Luna Master vault.

Obsidian Sync already carries the vault between this PC and the Mac Mini where
the agents run, so nothing listens on the network and no agent needs new tools:

- **Now note** ``<vault>/Agents/Pensieve/Now.md``: what Andy is working on,
  rewritten only when the board actually changes (so Sync is not churned).
  Machine-written; ``do_not_touch: true`` tells agents not to edit it.
- **Task requests**: an agent writes a note in its own ``Agents/<agent>/Handoffs/``
  folder (or ``Agents/Pensieve/Inbox/``) with ``to: pensieve`` and
  ``kind: task``. Pensieve lists pending ones in the dashboard under
  "From your agents". Nothing is created until Andy adds it there; Pensieve then
  sets the note's ``status:`` (executed or dropped) and ``outcome:``, the same
  lifecycle Yor's handoff briefs already use. Only those two frontmatter fields
  are ever written; the agent's text is left alone.

The contract agents follow lives in ``Agents/Pensieve/README.md``.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from pensieve.config import Settings

BRIDGE_DIR = Path("Agents") / "Pensieve"
NOW_FILE = "Now.md"
INBOX_DIR = "Inbox"
PENDING = {"", "draft", "delivered", "pending", "new"}
_FM = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_lock = threading.Lock()


# ----- paths ----------------------------------------------------------------------


def vault_root(settings: Settings) -> Optional[Path]:
    raw = (settings.vault_dir or "").strip()
    if not raw:
        return None
    root = Path(raw)
    return root if (root / "Agents").is_dir() else None


def bridge_dir(settings: Settings) -> Optional[Path]:
    root = vault_root(settings)
    return root / BRIDGE_DIR if root else None


def _shared_lists(settings: Settings) -> Optional[set[str]]:
    names = [n.strip().lower() for n in (settings.vault_bridge_lists or "").split(",") if n.strip()]
    return set(names) or None  # None = every list


# ----- Now note -------------------------------------------------------------------


def _fmt_due(dt: Optional[datetime]) -> Optional[str]:
    return dt.date().isoformat() if dt else None


def _one_line(text: str, limit: int = 220) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= limit else t[: limit - 3].rstrip() + "..."


def _goal_names(memory: Any, goals: dict[str, dict[str, Any]]) -> list[str]:
    out = []
    for gid in getattr(memory, "connect_goal_ids", []) or []:
        g = goals.get(gid)
        if g:
            out.append(str(g.get("short_title") or g.get("title") or gid))
    return out


def _task_line(memory: Any, goals: dict[str, dict[str, Any]]) -> str:
    title = (memory.display_title or memory.title or "").strip()
    bits = [memory.list_name] if memory.list_name else []
    due = _fmt_due(memory.due_date)
    if due:
        bits.append(f"due {due}")
    names = _goal_names(memory, goals)
    if names:
        bits.append("goal: " + ", ".join(names))
    line = f"- **{title}**" + (f" ({'; '.join(bits)})" if bits else "")
    why = _one_line(memory.why)
    if why:
        line += f"\n  - Why: {why}"
    return line


def render_now(memories: Iterable[Any], goals: dict[str, dict[str, Any]], shared: Optional[set[str]],
               today: Optional[date] = None) -> str:
    """Markdown body for Now.md (no frontmatter; deterministic for change detection)."""
    today = today or date.today()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    mems = [m for m in memories if shared is None or (m.list_name or "").lower() in shared]

    def due_key(m: Any) -> tuple:
        return (m.due_date is None, m.due_date or datetime.max.replace(tzinfo=timezone.utc), (m.title or "").lower())

    sections = [
        ("In progress", [m for m in mems if m.column == "dive"]),
        ("Needs his review", [m for m in mems if m.column == "review"]),
        ("Backlog", [m for m in mems if m.column == "memory"]),
    ]
    closed = [m for m in mems if m.column == "closed" and m.completed_at and m.completed_at >= week_ago]
    overdue = [m for m in mems if m.column != "closed" and m.due_date and m.due_date.date() < today]

    out = ["# What Andy is working on", "",
           "Written by Pensieve from his task board and refreshed when the board changes. "
           "Read-only for agents. To ask for a task, follow [[Agents/Pensieve/README|the Pensieve bridge contract]].", ""]
    if overdue:
        out += [f"Overdue: {len(overdue)} task(s), marked below.", ""]
    for heading, items in sections:
        out.append(f"## {heading}")
        if not items:
            out += ["- Nothing here right now.", ""]
            continue
        for m in sorted(items, key=due_key):
            line = _task_line(m, goals)
            if m in overdue:
                line = line.replace("- **", "- **[overdue] ", 1)
            out.append(line)
        out.append("")
    out.append("## Closed in the last 7 days")
    out += [f"- {(m.display_title or m.title).strip()} ({m.list_name or 'no list'}, closed {m.completed_at.date().isoformat()})"
            for m in sorted(closed, key=lambda m: m.completed_at, reverse=True)] or ["- Nothing closed this week."]
    out.append("")
    return "\n".join(out)


def write_now(settings: Settings, memories: Iterable[Any], goals: dict[str, dict[str, Any]]) -> bool:
    """Rewrite Now.md if its content changed. Returns True when the file was written."""
    target_dir = bridge_dir(settings)
    if target_dir is None:
        return False
    shared = _shared_lists(settings)
    body = render_now(memories, goals, shared)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    path = target_dir / NOW_FILE
    try:
        existing = path.read_text(encoding="utf-8")
        if f"content_hash: {digest}" in existing:
            return False
    except OSError:
        pass
    lists_line = ", ".join(sorted(shared)) if shared else "all"
    front = (
        "---\n"
        "type: dashboard\n"
        "generated_by: pensieve\n"
        "do_not_touch: true\n"
        f"updated: {datetime.now().astimezone().isoformat(timespec='minutes')}\n"
        f"lists: {lists_line}\n"
        f"content_hash: {digest}\n"
        "---\n\n"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(front + body, encoding="utf-8")
    os.replace(tmp, path)
    return True


# ----- task requests --------------------------------------------------------------


def _request_files(root: Path) -> Iterable[Path]:
    agents = root / "Agents"
    for handoffs in agents.glob("*/Handoffs"):
        yield from handoffs.glob("*.md")
    inbox = agents / BRIDGE_DIR.name / INBOX_DIR
    if inbox.is_dir():
        yield from inbox.glob("*.md")


def _parse(path: Path) -> Optional[tuple[dict[str, Any], str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FM.match(text)
    if not m:
        return None
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(meta, dict):
        return None
    return meta, text[m.end():]


def _request_id(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    return hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]


def _as_date(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            return None
    return None


def scan_requests(settings: Settings, include_done: bool = False) -> list[dict[str, Any]]:
    """Task requests agents filed for Pensieve (pending only unless ``include_done``)."""
    root = vault_root(settings)
    if root is None:
        return []
    out = []
    for path in _request_files(root):
        parsed = _parse(path)
        if not parsed:
            continue
        meta, body = parsed
        if str(meta.get("to", "")).strip().lower() != "pensieve" or str(meta.get("kind", "")).strip().lower() != "task":
            continue
        status = str(meta.get("status") or "").strip().lower()
        if not include_done and status not in PENDING:
            continue
        title = str(meta.get("title") or "").strip()
        if not title:
            continue
        out.append({
            "id": _request_id(root, path),
            "from": str(meta.get("from") or path.parent.parent.name).strip(),
            "created": _as_date(meta.get("created")),
            "title": title[:255],
            "notes": body.strip()[:2000],
            "due_date": _as_date(meta.get("due")),
            "list_name": (str(meta.get("list")).strip() if meta.get("list") else None),
            "importance": "high" if str(meta.get("importance") or "").lower() == "high" else "normal",
            "status": status or "draft",
            "path": path.relative_to(root).as_posix(),
        })
    out.sort(key=lambda r: (r["created"] or "", r["title"]))
    return out


def _find(settings: Settings, request_id: str) -> Path:
    root = vault_root(settings)
    if root is None:
        raise LookupError("The vault bridge is not configured (PENSIEVE_VAULT_DIR).")
    for path in _request_files(root):
        if _request_id(root, path) == request_id:
            return path
    raise LookupError(f"No task request {request_id}.")


def _set_fields(text: str, fields: dict[str, str]) -> str:
    """Set top-level frontmatter keys in place, keeping every other line as written."""
    m = _FM.match(text)
    if not m:
        raise ValueError("The request note has no frontmatter.")
    lines = m.group(1).splitlines()
    for key, value in fields.items():
        rendered = f"{key}: {value}"
        for i, line in enumerate(lines):
            if re.match(rf"^{re.escape(key)}\s*:", line):
                lines[i] = rendered
                break
        else:
            lines.append(rendered)
    nl = "\r\n" if "\r\n" in m.group(0) else "\n"
    return f"---{nl}{nl.join(lines)}{nl}---{nl}" + text[m.end():]


def resolve_request(settings: Settings, request_id: str, status: str, outcome: str) -> dict[str, Any]:
    """Close the loop on a request: status executed|dropped plus a one-line outcome."""
    if status not in ("executed", "dropped"):
        raise ValueError("status must be executed or dropped")
    path = _find(settings, request_id)
    with _lock:
        text = path.read_text(encoding="utf-8")
        safe = outcome.replace("\n", " ").replace('"', "'")
        updated = _set_fields(text, {
            "status": status,
            "outcome": f'"{safe}"',
            "outcome_date": date.today().isoformat(),
        })
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(tmp, path)
    return {"id": request_id, "status": status}


def request_by_id(settings: Settings, request_id: str) -> dict[str, Any]:
    for r in scan_requests(settings, include_done=True):
        if r["id"] == request_id:
            return r
    raise LookupError(f"No task request {request_id}.")


# ----- background worker ------------------------------------------------------------


class BridgeWorker:
    """Keeps Now.md current. Runs beside the API; a no-op when no vault is set."""

    def __init__(self, settings: Settings, interval_s: float = 60.0) -> None:
        self.settings = settings
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_written: Optional[str] = None
        self.last_error: Optional[str] = None

    def start(self) -> None:
        if bridge_dir(self.settings) is None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="pensieve-bridge")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def refresh(self) -> bool:
        from pensieve.enrichment.connect_goals import goals_index
        from pensieve.store import ChromaMemoryStore

        wrote = write_now(self.settings, ChromaMemoryStore().list_memories(), goals_index())
        if wrote:
            self.last_written = datetime.now().astimezone().isoformat(timespec="seconds")
        return wrote

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh()
                self.last_error = None
            except Exception as e:  # keep the API alive; surface the error in /api/bridge
                self.last_error = str(e)
            self._stop.wait(self.interval_s)
