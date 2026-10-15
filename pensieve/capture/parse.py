"""Turn a spoken note into a structured task draft with the "capture" model.

The draft is only a suggestion: the dashboard shows it on a confirm card and
nothing is created until the user clicks Add. If the model is unavailable the
transcript itself becomes the title, so speaking a task never dead-ends.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Optional

from pensieve.config import Settings

_PROMPT = """You turn one short spoken note into a single task for a to-do list.

Today is {today} ({weekday}). Resolve relative dates against today: "tomorrow",
"Friday" or "by Friday" (the coming Friday), "next week" (next Monday),
"end of the month" (its last day). If no date is said, due_date is null.

Choose list_name only from exactly these lists, and only when the speaker names
or clearly implies one; otherwise null:
{lists}

Return a JSON object with exactly these keys:
- "title": an imperative, specific task title, at most 80 characters, no trailing period
- "notes": any extra detail the speaker gave that is not in the title, else ""
- "due_date": "YYYY-MM-DD" or null
- "list_name": one of the lists above, or null
- "importance": "high" if they say urgent, important, ASAP, or high priority; else "normal"

Do not invent details the speaker did not say. Drop filler words."""

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _fallback(transcript: str, error: Optional[str] = None) -> dict[str, Any]:
    text = transcript.strip()
    title = text if len(text) <= 80 else text[:77].rstrip() + "..."
    out: dict[str, Any] = {
        "title": title,
        "notes": text if len(text) > 80 else "",
        "due_date": None,
        "list_name": None,
        "importance": "normal",
        "ai": False,
    }
    if error:
        out["error"] = error
    return out


def parse_spoken_task(
    settings: Settings,
    transcript: str,
    lists: list[str],
    today: Optional[date] = None,
    client: Any = None,
) -> dict[str, Any]:
    """Draft ``{"title", "notes", "due_date", "list_name", "importance", "ai"}``."""
    text = (transcript or "").strip()
    if not text:
        raise ValueError("Nothing was heard.")
    today = today or date.today()
    if client is None:
        from pensieve.enrichment.chat_provider import get_chat_client

        client = get_chat_client(settings, purpose="capture")
    system = _PROMPT.format(
        today=today.isoformat(),
        weekday=today.strftime("%A"),
        lists="\n".join(f"- {name}" for name in lists) or "- (no lists available)",
    )
    try:
        resp = client.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": text}],
            max_output_tokens=300,
            response_format="json_object",
            timeout=45.0,
        )
        data = json.loads(resp["choices"][0]["message"]["content"])
    except Exception as e:  # model unavailable, bad JSON, timeout
        return _fallback(text, error=str(e))
    if not isinstance(data, dict):
        return _fallback(text, error="The model did not return an object.")

    title = str(data.get("title") or "").strip().rstrip(".") or _fallback(text)["title"]
    due = data.get("due_date")
    due = due if isinstance(due, str) and _DATE.match(due) else None
    if due:
        try:
            date.fromisoformat(due)
        except ValueError:
            due = None
    wanted = str(data.get("list_name") or "").strip().lower()
    list_name = next((n for n in lists if n.lower() == wanted), None) if wanted else None
    return {
        "title": title[:255],
        "notes": str(data.get("notes") or "").strip(),
        "due_date": due,
        "list_name": list_name,
        "importance": "high" if str(data.get("importance")).lower() == "high" else "normal",
        "ai": True,
        "model": resp.get("model") if isinstance(resp, dict) else None,
    }
