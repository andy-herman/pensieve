"""Run a single RawTask through the enrichment prompt and produce a Memory."""

from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from pensieve.config import get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.enrichment.llm_client import AzureOpenAIChatClient
from pensieve.enrichment.prompt import load_system_prompt
from pensieve.sources.base import RawTask


class EnrichmentResult(BaseModel):
    """LLM output for a single task. Fields mirror the v2 prompt schema."""

    display_title: str = ""
    suggested_strand: Optional[str] = None
    needs_human_strand_review: bool = False
    why: str = ""
    impact: str = ""
    strand_kind: Optional[str] = None
    confidence_strand: float = 0.0
    confidence_impact: float = 0.0
    connect_goal_ids: list[str] = Field(default_factory=list)
    connect_alignment_confidence: float = 0.0
    connect_alignment_note: str = ""
    notes_for_user: str = ""
    tokens_used: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)


def _build_user_payload(
    task: RawTask,
    strand_catalog: list[dict],
    connect_goals: list[dict],
    recent_context: dict,
) -> str:
    payload = {
        "task": {
            "id": task.id,
            "title": task.title,
            "notes": task.notes,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "list_name": task.list_name,
        },
        "strand_catalog": strand_catalog,
        "connect_goals": connect_goals,
        "recent_context": recent_context,
    }
    return json.dumps(payload, default=str, ensure_ascii=False)


def enrich_task(
    task: RawTask,
    strand_catalog: list[dict],
    recent_context: dict,
    *,
    client: Optional[AzureOpenAIChatClient] = None,
    connect_goals: Optional[list[dict]] = None,
) -> EnrichmentResult:
    settings = get_settings()
    if client is None:
        client = AzureOpenAIChatClient(settings)
    if connect_goals is None:
        connect_goals = load_connect_goals()

    system_prompt = load_system_prompt()
    user_payload = _build_user_payload(task, strand_catalog, connect_goals, recent_context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Enrich this task into a Memory.\n\nINPUT:\n{user_payload}"},
    ]

    resp = client.chat(
        messages=messages,
        max_output_tokens=settings.enrichment_max_tokens,
        response_format="json_object",
    )

    content = resp["choices"][0]["message"]["content"]
    tokens = int(resp.get("usage", {}).get("total_tokens", 0))
    parsed = json.loads(content)

    return EnrichmentResult(
        display_title=(parsed.get("display_title") or parsed.get("title") or "") or "",
        suggested_strand=parsed.get("suggested_strand"),
        needs_human_strand_review=bool(parsed.get("needs_human_strand_review", False)),
        why=parsed.get("why", "") or "",
        impact=parsed.get("impact", "") or "",
        strand_kind=parsed.get("strand_kind"),
        confidence_strand=float(parsed.get("confidence_strand", 0.0) or 0.0),
        confidence_impact=float(parsed.get("confidence_impact", 0.0) or 0.0),
        connect_goal_ids=list(parsed.get("connect_goal_ids", []) or []),
        connect_alignment_confidence=float(parsed.get("connect_alignment_confidence", 0.0) or 0.0),
        connect_alignment_note=parsed.get("connect_alignment_note", "") or "",
        notes_for_user=parsed.get("notes_for_user", "") or "",
        tokens_used=tokens,
        raw=parsed,
    )
