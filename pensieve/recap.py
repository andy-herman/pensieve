"""Connect recap generation.

Turns enriched Memories into a Microsoft Connect-style "Reflect on the past"
recap, grouped by the user's committed Connect goals. One LLM call per goal so
each response stays small and the calls are easy to reason about (and stay well
clear of the burst-throttle ceiling we hit at higher concurrency).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from pensieve.config import Settings, get_settings
from pensieve.enrichment.connect_goals import load_connect_goals
from pensieve.enrichment.llm_client import AzureOpenAIChatClient
from pensieve.enrichment.prompt import load_system_prompt
from pensieve.store.schema import Memory

# Scope -> human label, kept in sync with the frontend selector.
SCOPES = ("all", "completed", "review")

_COLUMN_STATUS = {
    "memory": "captured / not started",
    "dive": "in progress",
    "review": "needs review",
    "closed": "completed / closed",
}


def _is_review(m: Memory) -> bool:
    return bool(
        m.needs_human_strand_review
        or (m.confidence_strand and m.confidence_strand < 0.5)
        or (m.confidence_impact and m.confidence_impact < 0.5)
    )


def _is_completed(m: Memory) -> bool:
    return bool(m.completed or m.column == "closed")


def filter_by_scope(memories: list[Memory], scope: str) -> list[Memory]:
    if scope == "completed":
        return [m for m in memories if _is_completed(m)]
    if scope == "review":
        return [m for m in memories if _is_review(m)]
    return list(memories)  # "all"


def filter_by_list_names(memories: list[Memory], list_names: list[str]) -> list[Memory]:
    """Restrict to memories whose source list_name is in the allowlist.

    Empty list_names = no filter (return all memories unchanged). Match is
    case-insensitive and trims whitespace so a list_name of "ciso grc" or
    " CISO GRC " in either side still matches "CISO GRC".
    """
    if not list_names:
        return list(memories)
    wanted = {n.strip().lower() for n in list_names if n and n.strip()}
    if not wanted:
        return list(memories)
    return [m for m in memories if (m.list_name or "").strip().lower() in wanted]


def _resolve_list_names(
    list_names: Optional[list[str]], settings: Settings
) -> list[str]:
    """Treat ``None`` as 'use settings default'; pass-through any explicit list.

    A caller passing ``list_names=[]`` is explicitly disabling the filter
    (include every list); ``list_names=None`` means 'use whatever the env
    config says', which defaults to ``["CISO GRC"]``.
    """
    if list_names is None:
        return settings.recap_list_names_list()
    return [n for n in list_names if isinstance(n, str) and n.strip()]


def _status_label(m: Memory) -> str:
    if m.completed:
        return "completed"
    return _COLUMN_STATUS.get(m.column, m.column or "captured")


def _item_payload(m: Memory) -> dict[str, Any]:
    return {
        "title": m.title,
        "why": m.why,
        "impact": m.impact,
        "status": _status_label(m),
        "notes": m.notes_for_user or m.original_notes or "",
    }


def _goal_block(goal: dict[str, Any]) -> str:
    lines = [
        f"name: {goal.get('name') or goal.get('short_name', '')}",
        f"summary: {goal.get('summary', '')}",
    ]
    crit = goal.get("success_criteria") or []
    if crit:
        lines.append("success_criteria:")
        lines.extend(f"  - {c}" for c in crit)
    if goal.get("impact_statement"):
        lines.append(f"committed_impact: {goal['impact_statement']}")
    return "\n".join(lines)


# Synthetic goal used to recap work the user never mapped to a committed goal.
_UNALIGNED_GOAL = {
    "id": "_unaligned",
    "short_name": "Other Work",
    "name": "Other Work (not mapped to a committed goal)",
    "summary": (
        "Work the user completed this period that was not aligned to any of the "
        "committed Connect goals. Summarize it honestly as additional contributions."
    ),
    "success_criteria": [],
    "impact_statement": "",
}


def _group_by_goal(
    memories: list[Memory],
    goals: list[dict[str, Any]],
    goal_ids: Optional[list[str]],
) -> list[tuple[dict[str, Any], list[Memory]]]:
    """Return (goal, items) pairs in goal order, then an unaligned bucket.

    A memory can be aligned to multiple goals; it appears under each. Memories
    aligned to no known goal land in the synthetic _unaligned bucket.
    """
    known_ids = {g["id"] for g in goals if "id" in g}
    wanted = set(goal_ids) if goal_ids else None

    grouped: list[tuple[dict[str, Any], list[Memory]]] = []
    for goal in goals:
        gid = goal.get("id")
        if not gid:
            continue
        if wanted is not None and gid not in wanted:
            continue
        items = [m for m in memories if gid in (m.connect_goal_ids or [])]
        if items:
            grouped.append((goal, items))

    # Unaligned: only when the caller did not restrict to specific goals.
    if wanted is None:
        unaligned = [
            m
            for m in memories
            if not any(g in known_ids for g in (m.connect_goal_ids or []))
        ]
        if unaligned:
            grouped.append((_UNALIGNED_GOAL, unaligned))

    return grouped


def _accomplishments_for_goal(
    goal: dict[str, Any],
    items: list[Memory],
    *,
    client: AzureOpenAIChatClient,
    settings: Settings,
    prompt_template: str,
    feedback: str = "",
) -> tuple[list[dict[str, str]], int]:
    items_json = json.dumps([_item_payload(m) for m in items], ensure_ascii=False, default=str)
    content_prompt = prompt_template.replace("{goal_block}", _goal_block(goal)).replace(
        "{items_block}", items_json
    )
    if feedback.strip():
        content_prompt += (
            "\n\n## Reviewer correction\n"
            "The user reviewed a previous draft of this section and gave the "
            "following correction. Rewrite the accomplishments to address it "
            "(for example, a task may have been misinterpreted). Stay grounded "
            "in the work items above; do not invent facts.\n\n"
            f"CORRECTION: {feedback.strip()}"
        )
    messages = [
        {
            "role": "system",
            "content": "You write Microsoft Connect performance recaps. Return only JSON.",
        },
        {"role": "user", "content": content_prompt},
    ]
    resp = client.chat(
        messages=messages,
        max_output_tokens=settings.enrichment_max_tokens,
        response_format="json_object",
    )
    content = resp["choices"][0]["message"]["content"]
    tokens = int(resp.get("usage", {}).get("total_tokens", 0))
    parsed = json.loads(content)
    accomplishments: list[dict[str, str]] = []
    for a in parsed.get("accomplishments", []) or []:
        if not isinstance(a, dict):
            continue
        accomplishments.append(
            {
                "heading": str(a.get("heading", "")).strip(),
                "narrative": str(a.get("narrative", "")).strip(),
                "impact": str(a.get("impact", "")).strip(),
            }
        )
    return accomplishments, tokens


def generate_recap(
    memories: list[Memory],
    *,
    scope: str = "all",
    goal_ids: Optional[list[str]] = None,
    list_names: Optional[list[str]] = None,
    period_label: str = "",
    goals: Optional[list[dict[str, Any]]] = None,
    client: Optional[AzureOpenAIChatClient] = None,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """Generate a Connect-format recap from enriched memories.

    :param memories: all Memory records to consider (already loaded from store).
    :param scope: "all" | "completed" | "review" — which memories to include.
    :param goal_ids: optional restriction to specific Connect goal ids.
    :param list_names: optional restriction to specific source list_name values
        (e.g. ``["CISO GRC"]``). ``None`` = use the configured default from
        ``PENSIEVE_RECAP_LIST_NAMES`` (which defaults to ``CISO GRC``). Empty
        list ``[]`` = no list filter (include every memory).
    :param period_label: free-text reflection period (e.g. "Oct 2025 - May 2026").
    :param goals: Connect goal catalog; loaded from data/ if omitted.
    :param client: chat client; constructed from settings if omitted.
    :param settings: runtime settings; loaded if omitted.
    :returns: a JSON-serializable recap dict (see README / API docs).
    """
    settings = settings or get_settings()
    goals = goals if goals is not None else load_connect_goals()
    if client is None:
        client = AzureOpenAIChatClient(settings)
    if scope not in SCOPES:
        scope = "all"

    prompt_template = load_system_prompt("connect-recap-prompt.md")

    resolved_lists = _resolve_list_names(list_names, settings)
    list_scoped = filter_by_list_names(memories, resolved_lists)
    scoped = filter_by_scope(list_scoped, scope)
    grouped = _group_by_goal(scoped, goals, goal_ids)

    sections: list[dict[str, Any]] = []
    total_tokens = 0
    for goal, items in grouped:
        accomplishments, tokens = _accomplishments_for_goal(
            goal,
            items,
            client=client,
            settings=settings,
            prompt_template=prompt_template,
        )
        total_tokens += tokens
        sections.append(
            {
                "goal_id": goal["id"],
                "short_name": goal.get("short_name", ""),
                "name": goal.get("name", ""),
                "lane": goal.get("lane", ""),
                "task_count": len(items),
                "task_titles": [m.title for m in items],
                "accomplishments": accomplishments,
            }
        )

    return {
        "period_label": period_label,
        "scope": scope,
        "list_names_applied": resolved_lists,
        "memories_considered": len(scoped),
        "section_count": len(sections),
        "sections": sections,
        "tokens_used": total_tokens,
    }


def _resolve_goal_and_items(
    memories: list[Memory], goal_id: str, goals: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[Memory]]:
    """Return the (goal_dict, items) for a single goal_id, incl. the unaligned bucket."""
    if goal_id == "_unaligned":
        known = {g["id"] for g in goals if "id" in g}
        items = [m for m in memories if not any(g in known for g in (m.connect_goal_ids or []))]
        return _UNALIGNED_GOAL, items
    goal = next((g for g in goals if g.get("id") == goal_id), None)
    if goal is None:
        raise ValueError(f"Unknown goal_id: {goal_id}")
    items = [m for m in memories if goal_id in (m.connect_goal_ids or [])]
    return goal, items


def revise_recap_section(
    memories: list[Memory],
    goal_id: str,
    feedback: str,
    *,
    scope: str = "all",
    list_names: Optional[list[str]] = None,
    goals: Optional[list[dict[str, Any]]] = None,
    client: Optional[AzureOpenAIChatClient] = None,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """Re-draft a single recap section, incorporating the user's correction.

    Used by the recap chat: the user tells the agent it misread a task, and the
    section's accomplishments are regenerated for that one goal. ``list_names``
    follows the same semantics as :func:`generate_recap` so a revision sees the
    same memory cohort the original draft saw.
    """
    settings = settings or get_settings()
    goals = goals if goals is not None else load_connect_goals()
    if client is None:
        client = AzureOpenAIChatClient(settings)
    if scope not in SCOPES:
        scope = "all"

    prompt_template = load_system_prompt("connect-recap-prompt.md")
    resolved_lists = _resolve_list_names(list_names, settings)
    list_scoped = filter_by_list_names(memories, resolved_lists)
    scoped = filter_by_scope(list_scoped, scope)
    goal, items = _resolve_goal_and_items(scoped, goal_id, goals)

    accomplishments, tokens = _accomplishments_for_goal(
        goal,
        items,
        client=client,
        settings=settings,
        prompt_template=prompt_template,
        feedback=feedback,
    )
    return {
        "goal_id": goal.get("id", goal_id),
        "short_name": goal.get("short_name", ""),
        "name": goal.get("name", ""),
        "lane": goal.get("lane", ""),
        "list_names_applied": resolved_lists,
        "task_count": len(items),
        "task_titles": [m.title for m in items],
        "accomplishments": accomplishments,
        "tokens_used": tokens,
    }
