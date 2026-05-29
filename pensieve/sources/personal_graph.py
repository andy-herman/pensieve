"""Personal Microsoft Graph TaskSource. READ-ONLY against personal MS account.

Personal MS accounts (outlook.com / hotmail / live) can access Microsoft
To-Do via Graph WITHOUT admin consent — unlike corp accounts, which sit
behind Secure Future Initiative blockers. This source is the recommended
path for personal-device installs.

Auth: MSAL device-code flow. On first run a browser opens (or a code is
printed) for the user to grant `Tasks.Read`. A refresh token is cached
locally under ``data/personal-graph-token-cache.bin`` and reused on
subsequent runs — no re-prompt unless cache is deleted or the refresh
token expires.

The class never calls POST/PATCH/DELETE. Read-only contract is enforced
by the source surface (mirrors OutlookCOMSource).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
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
      - An app registration in the user's personal MS account (or
        multi-tenant + personal) with redirect URI `http://localhost`
        and delegated `Tasks.Read` permission.
      - `msal` installed (`pip install msal` or `pip install -e .[personal]`).
      - `PERSONAL_GRAPH_CLIENT_ID` set in .env.

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
        try:
            import msal  # type: ignore[import-not-found]
        except ImportError as e:
            raise PersonalGraphUnavailable(
                "msal is not installed. Run: pip install msal "
                "(or pip install -e .[personal] for the full personal-device extras)."
            ) from e

        client_id = self.settings.personal_graph_client_id
        if not client_id:
            raise PersonalGraphUnavailable(
                "PERSONAL_GRAPH_CLIENT_ID is not set. Register an app at "
                "https://entra.microsoft.com (Account type: personal MS accounts) "
                "and put the application (client) id in .env. See "
                "docs/SETUP-personal-device.md."
            )

        cache_path = self.settings.personal_graph_token_cache_path
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = msal.SerializableTokenCache()
        if cache_path.exists():
            try:
                cache.deserialize(cache_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        app = msal.PublicClientApplication(
            client_id,
            authority=self.settings.personal_graph_authority,
            token_cache=cache,
        )

        scopes = self.settings.personal_graph_scope_list()
        result = None
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])
        if not result:
            flow = app.initiate_device_flow(scopes=scopes)
            if "user_code" not in flow:
                raise PersonalGraphUnavailable(
                    f"Failed to start device flow: {flow.get('error_description', flow)}"
                )
            print(flow["message"])  # noqa: T201 (intentional CLI prompt)
            result = app.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            raise PersonalGraphUnavailable(
                f"Token acquisition failed: {result.get('error_description', result)}"
            )

        if cache.has_state_changed:
            cache_path.write_text(cache.serialize(), encoding="utf-8")

        self._token = result["access_token"]
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
            full = next_url if next_url.startswith("http") else next_url
            resp = client.get(full)
            if resp.status_code >= 400:
                raise PersonalGraphUnavailable(
                    f"Graph call failed [{resp.status_code}] for {full}: {resp.text}"
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

    @staticmethod
    def cache_path(settings: Optional[Settings] = None) -> Path:
        s = settings or get_settings()
        return s.personal_graph_token_cache_path
