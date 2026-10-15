"""Personal Microsoft Graph TaskSource. READ-ONLY against personal MS account.

Personal MS accounts (outlook.com / hotmail / live) can access Microsoft
To-Do via Graph WITHOUT admin consent - unlike corp accounts, which sit
behind Secure Future Initiative blockers. Sync uses this source when the
Accounts screen's task source is Microsoft To Do.

Auth: the user connects their Microsoft account once in the dashboard's
Accounts screen (MSAL device-code flow, see pensieve.connections). The
refresh token is cached encrypted with Windows DPAPI and reused silently on
every sync; if it expires, sync reports that the account needs reconnecting.

The class never calls POST/PATCH/DELETE. Read-only contract is enforced
by the source surface (mirrors OutlookCOMSource).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

import httpx

from pensieve.config import Settings, get_settings
from pensieve.sources.base import RawTask, TaskSource

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class PersonalGraphUnavailable(RuntimeError):
    pass


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        s = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _parse_graph_datetime(blob: Optional[dict]) -> Optional[datetime]:
    """Graph returns datetimes as {'dateTime': '...', 'timeZone': '...'}."""
    if not blob:
        return None
    iso = blob.get("dateTime") if isinstance(blob, dict) else None
    return _parse_iso(iso)


class PersonalGraphSource(TaskSource):
    """Reads task lists from a personal Microsoft account via Graph /me/todo.

    Requirements:
      - ``PERSONAL_GRAPH_CLIENT_ID`` set to a Pensieve app registration in a
        personal Entra directory (see desktop/SHARING.md).
      - A Microsoft account connected in the Accounts screen.

    By default reads every To-Do list the user has. Use ``list_names`` to
    filter by displayName.
    """

    name = "personal_graph"

    def __init__(
        self,
        list_names: Optional[list[str]] = None,
        include_completed: bool = True,
        skip_completed_older_than_days: Optional[int] = None,
        settings: Optional[Settings] = None,
        token: Optional[str] = None,
    ):
        self.settings = settings or get_settings()
        self.list_names = [n for n in (list_names or []) if n and n.strip()]
        self.include_completed = include_completed
        self.skip_completed_older_than_days = (
            skip_completed_older_than_days
            if skip_completed_older_than_days is not None
            else self.settings.personal_graph_skip_completed_older_days
        )
        # Token can be injected by tests; otherwise acquired lazily via MSAL.
        self._token: Optional[str] = token
        self._covered_lists: set[str] = set()

    # ----- auth -----

    def _acquire_token(self) -> str:
        if self._token:
            return self._token
        # Sign-in happens in the app's Accounts screen (pensieve.connections),
        # which keeps an encrypted MSAL cache. Sync only ever refreshes silently:
        # a background sync must never block on an interactive prompt.
        from pensieve.connections import NotConnected, graph_token

        try:
            self._token = graph_token(self.settings)
        except NotConnected as e:
            raise PersonalGraphUnavailable(str(e)) from e
        except ImportError as e:
            raise PersonalGraphUnavailable(
                "msal and msal-extensions are required. Run: pip install msal msal-extensions"
            ) from e
        return self._token

    # ----- helpers -----

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=GRAPH_BASE,
            headers={"Authorization": f"Bearer {self._acquire_token()}"},
            timeout=30.0,
        )

    @staticmethod
    def _paged(client: httpx.Client, url: str) -> Iterator[dict]:
        next_url: Optional[str] = url
        while next_url:
            resp = client.get(next_url)
            if resp.status_code >= 400:
                raise PersonalGraphUnavailable(
                    f"Graph call failed [{resp.status_code}] for {next_url}: {resp.text}"
                )
            body = resp.json()
            for item in body.get("value", []):
                yield item
            next_url = body.get("@odata.nextLink")

    def _to_raw(self, item: dict, list_name: str) -> RawTask:
        body = item.get("body") or {}
        notes = body.get("content", "") if isinstance(body, dict) else ""
        status = (item.get("status") or "").lower()
        completed = status == "completed"
        return RawTask(
            id=str(item.get("id", "")),
            title=item.get("title") or "",
            notes=notes or "",
            list_name=list_name,
            created_at=_parse_iso(item.get("createdDateTime")),
            last_modification_time=_parse_iso(item.get("lastModifiedDateTime")),
            completed=completed,
            completed_at=_parse_graph_datetime(item.get("completedDateTime")),
            categories=list(item.get("categories") or []),
            due_date=_parse_graph_datetime(item.get("dueDateTime")),
            source=self.name,
        )

    # ----- TaskSource surface -----

    def list_tasks(self) -> Iterator[RawTask]:
        self._covered_lists.clear()
        with self._client() as client:
            lists = list(self._paged(client, "/me/todo/lists"))
            wanted = {n.strip().lower() for n in self.list_names}
            cutoff: Optional[datetime] = None
            if self.skip_completed_older_than_days and self.skip_completed_older_than_days > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    days=self.skip_completed_older_than_days
                )

            for lst in lists:
                list_name = lst.get("displayName") or "(unnamed list)"
                if wanted and list_name.strip().lower() not in wanted:
                    continue
                self._covered_lists.add(list_name)
                list_id = lst.get("id")
                if not list_id:
                    continue
                for item in self._paged(client, f"/me/todo/lists/{list_id}/tasks"):
                    task = self._to_raw(item, list_name)
                    if (
                        task.completed
                        and not self.include_completed
                    ):
                        continue
                    if (
                        task.completed
                        and cutoff
                        and task.completed_at
                        and task.completed_at < cutoff
                    ):
                        continue
                    yield task

    def get_task(self, task_id: str) -> Optional[RawTask]:
        # Walk lists to find the task. Graph doesn't expose a global by-id endpoint.
        with self._client() as client:
            for lst in self._paged(client, "/me/todo/lists"):
                list_id = lst.get("id")
                if not list_id:
                    continue
                resp = client.get(f"/me/todo/lists/{list_id}/tasks/{task_id}")
                if resp.status_code == 200:
                    return self._to_raw(resp.json(), lst.get("displayName") or "")
        return None

    def covered_lists(self) -> Optional[set[str]]:
        return set(self._covered_lists) if self._covered_lists else None
