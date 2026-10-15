"""Create a new task in the user's own task list: Pensieve's one additive writeback.

Pensieve's sources are read-only and stay that way. Voice capture is the only
place Pensieve writes a task, and only under these rules:

- it creates a NEW task, after the user confirms it in the dashboard;
- it never edits, completes, or deletes an existing task;
- it is gated by ``PENSIEVE_ALLOW_TASK_CREATE`` (on by default on this branch).

It lives outside ``pensieve/sources`` on purpose, so the read-only source
contract (tests/test_sources.py, .claude/hooks/guard_sources.py) is untouched.

Where the task goes follows the sync source:
- ``outlook_com``: a TaskItem in the matching Outlook task folder (classic
  Outlook on this PC; it reaches Microsoft To Do through the mailbox).
- ``personal_graph``: Microsoft Graph ``POST /me/todo/lists/{id}/tasks``.
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Iterator, Optional, TypeVar

import httpx

from pensieve.config import Settings
from pensieve.connections import effective_source, graph_token

T = TypeVar("T")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
OL_FOLDER_TASKS = 13
OL_TASK_ITEM = 3
OL_IMPORTANCE_HIGH = 2


class TaskCreationDisabled(RuntimeError):
    """Task creation is switched off or unsupported for the current source."""


@dataclass
class NewTask:
    title: str
    notes: str = ""
    due_date: Optional[date] = None
    list_name: Optional[str] = None
    importance: str = "normal"  # "normal" | "high"


def _check_enabled(settings: Settings) -> str:
    if not settings.allow_task_create:
        raise TaskCreationDisabled("Adding tasks is switched off (PENSIEVE_ALLOW_TASK_CREATE=false).")
    src = effective_source(settings)
    if src not in ("outlook_com", "personal_graph"):
        raise TaskCreationDisabled(f"Tasks cannot be added while syncing from '{src}'.")
    return src


# ----- Outlook COM ---------------------------------------------------------------


def _in_com_apartment(fn: Callable[[], T]) -> T:
    """Run ``fn`` in its own COM apartment.

    The COM objects ``fn`` touches are locals of ``fn``, so they are released
    when it returns, before CoUninitialize; a reference that outlived the
    apartment would crash or leak when Python later freed it.
    """
    import pythoncom  # type: ignore[import-not-found]

    pythoncom.CoInitialize()
    try:
        return fn()
    finally:
        gc.collect()
        pythoncom.CoUninitialize()


def _outlook_root() -> Any:
    import win32com.client  # type: ignore[import-not-found]

    ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    try:
        ns.Logon("", "", False, False)  # headless classic Outlook needs a session
    except Exception:
        pass
    return ns.GetDefaultFolder(OL_FOLDER_TASKS)


def _walk(folder: Any) -> Iterator[Any]:
    try:
        children = list(folder.Folders)
    except Exception:
        return
    for sub in children:
        yield sub
        yield from _walk(sub)


def _com_lists() -> tuple[list[str], str]:
    def run() -> tuple[list[str], str]:
        root = _outlook_root()
        default = str(root.Name or "Tasks")
        return [default] + [str(f.Name) for f in _walk(root) if f.Name], default

    return _in_com_apartment(run)


def _com_add(task: NewTask) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        root = _outlook_root()
        folder = root
        if task.list_name and task.list_name.lower() != (root.Name or "").lower():
            folder = next((f for f in _walk(root) if (f.Name or "").lower() == task.list_name.lower()), None)
            if folder is None:
                raise ValueError(f"No Outlook task list named '{task.list_name}'.")
        item = folder.Items.Add(OL_TASK_ITEM)
        item.Subject = task.title
        if task.notes:
            item.Body = task.notes
        if task.due_date:
            item.DueDate = datetime(task.due_date.year, task.due_date.month, task.due_date.day)
        if task.importance == "high":
            item.Importance = OL_IMPORTANCE_HIGH
        item.Save()
        return {"id": str(item.EntryID), "list_name": str(folder.Name)}

    return _in_com_apartment(run)


# ----- Microsoft Graph (personal To Do) -----------------------------------------


def _local_tz_id() -> str:
    """Windows time zone id (e.g. 'Pacific Standard Time'); Graph accepts these."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation"
        ) as key:
            value, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
            if value:
                return str(value).strip("\x00")
    except Exception:
        pass
    return "UTC"


def _graph_client(settings: Settings) -> httpx.Client:
    return httpx.Client(
        base_url=GRAPH_BASE,
        headers={"Authorization": f"Bearer {graph_token(settings)}"},
        timeout=30.0,
    )


def _graph_lists(client: httpx.Client) -> list[dict[str, Any]]:
    resp = client.get("/me/todo/lists")
    resp.raise_for_status()
    return list(resp.json().get("value") or [])


def _graph_default(lists: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return next((x for x in lists if x.get("wellknownListName") == "defaultList"), lists[0] if lists else None)


def _graph_add(settings: Settings, task: NewTask) -> dict[str, Any]:
    with _graph_client(settings) as client:
        lists = _graph_lists(client)
        target = _graph_default(lists)
        if task.list_name:
            target = next(
                (x for x in lists if (x.get("displayName") or "").lower() == task.list_name.lower()), None
            )
            if target is None:
                raise ValueError(f"No To Do list named '{task.list_name}'.")
        if target is None:
            raise ValueError("This Microsoft account has no To Do lists.")
        body: dict[str, Any] = {"title": task.title, "importance": "high" if task.importance == "high" else "normal"}
        if task.notes:
            body["body"] = {"content": task.notes, "contentType": "text"}
        if task.due_date:
            body["dueDateTime"] = {"dateTime": f"{task.due_date.isoformat()}T00:00:00", "timeZone": _local_tz_id()}
        resp = client.post(f"/me/todo/lists/{target['id']}/tasks", json=body)
        if resp.status_code == 403:
            raise PermissionError(
                "Microsoft did not allow adding tasks. Reconnect Microsoft in More > Accounts "
                "so Pensieve can ask for permission to add tasks."
            )
        resp.raise_for_status()
        return {"id": str(resp.json().get("id", "")), "list_name": target.get("displayName")}


# ----- public API -----------------------------------------------------------------


def available_lists(settings: Settings) -> dict[str, Any]:
    """Lists a new task can go to, for the capture card's picker."""
    src = effective_source(settings)
    out: dict[str, Any] = {"source": src, "enabled": bool(settings.allow_task_create), "lists": [], "default": None}
    if src == "outlook_com":
        out["lists"], out["default"] = _com_lists()
    elif src == "personal_graph":
        with _graph_client(settings) as client:
            lists = _graph_lists(client)
        out["lists"] = [x.get("displayName") for x in lists if x.get("displayName")]
        d = _graph_default(lists)
        out["default"] = d.get("displayName") if d else None
    else:
        out["enabled"] = False
    return out


def add_task(settings: Settings, task: NewTask) -> dict[str, Any]:
    """Create ``task`` in the user's own list. Returns ``{"source", "id", "list_name"}``."""
    src = _check_enabled(settings)
    title = (task.title or "").strip()
    if not title:
        raise ValueError("A task needs a title.")
    task.title = title[:255]
    task.importance = "high" if task.importance == "high" else "normal"
    created = _com_add(task) if src == "outlook_com" else _graph_add(settings, task)
    return {"source": src, **created}
