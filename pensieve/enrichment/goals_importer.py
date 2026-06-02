"""Parse a Microsoft Connect PDF into the canonical connect-goals.json shape.

Flow:
    pdf_bytes -> extract_pdf_text() -> raw text
              -> extract_goals_from_text(client) -> goals dict
              -> assign_houses_and_ids() -> connect-goals.json-shaped dict

Goal count is variable. Houses are assigned deterministically from a fixed
palette of 8 HP-themed entries (the canonical four + four extensions). Goals
beyond 8 cycle back through the canonical four.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from pensieve.enrichment.llm_client import AzureOpenAIChatClient
from pensieve.enrichment.prompt import load_system_prompt

# 8-entry palette. First four are the canonical HP houses used by the
# dashboard CSS; the next four are extensions for users with more than
# 4 goals. Each entry must have a unique `house` slug so the dashboard
# CSS can target it.
HOUSE_PALETTE: list[dict[str, str]] = [
    {
        "house": "gryffindor",
        "house_glyph": "\u26a1",
        "color_primary": "#7a2018",
        "color_accent": "#c9a655",
    },
    {
        "house": "hufflepuff",
        "house_glyph": "\u2698",
        "color_primary": "#b08a26",
        "color_accent": "#2a1d10",
    },
    {
        "house": "slytherin",
        "house_glyph": "\u269c",
        "color_primary": "#2e5a3a",
        "color_accent": "#a8a8a8",
    },
    {
        "house": "ravenclaw",
        "house_glyph": "\u269b",
        "color_primary": "#2c4670",
        "color_accent": "#c9a655",
    },
    {
        "house": "internal",
        "house_glyph": "\u2697",  # alembic - internal alchemy
        "color_primary": "#5a5a5a",
        "color_accent": "#c9a655",
    },
    {
        "house": "muggleborn",
        "house_glyph": "\u270e",  # pencil - everyday work
        "color_primary": "#8a4b1f",
        "color_accent": "#e0c690",
    },
    {
        "house": "centaur",
        "house_glyph": "\u2618",  # shamrock - forest-aligned
        "color_primary": "#3c5e2c",
        "color_accent": "#c9a655",
    },
    {
        "house": "phoenix",
        "house_glyph": "\u2741",  # rotating asterisk - rebirth
        "color_primary": "#a83a1f",
        "color_accent": "#f5d77b",
    },
]


# ---------- PDF text extraction ----------


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF byte blob using pypdf.

    Returns a single string with page-text joined by double newlines. Empty
    pages are skipped.
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover - dependency-install path
        raise RuntimeError("pypdf is not installed. Run `pip install -e .` to refresh dependencies.") from e

    from io import BytesIO

    reader = PdfReader(BytesIO(pdf_bytes))
    chunks: list[str] = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        txt = txt.strip()
        if txt:
            chunks.append(txt)
    return "\n\n".join(chunks)


# ---------- LLM goal extraction ----------


def _slugify(s: str, max_len: int = 32) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s[:max_len] or "goal"


def extract_goals_from_text(
    text: str,
    *,
    client: Optional[AzureOpenAIChatClient] = None,
    max_output_tokens: int = 3000,
) -> dict[str, Any]:
    """Send PDF text to the LLM and parse the response into a goals dict.

    Returns the LLM's raw structured response (a dict with keys "goals",
    "behaviors", "extraction_notes"). Does NOT yet add houses/ids. Call
    `assign_houses_and_ids()` to finalize.
    """
    if not text or not text.strip():
        raise ValueError("PDF text is empty. Nothing to extract.")

    if client is None:
        from pensieve.config import get_settings

        client = AzureOpenAIChatClient(get_settings())

    system_prompt = load_system_prompt("extract-connect-goals.md")
    user_payload = json.dumps({"pdf_text": text}, ensure_ascii=False)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": ("Extract the user's Connect goals from this PDF text.\n\nINPUT:\n" + user_payload),
        },
    ]

    resp = client.chat(
        messages=messages,
        max_output_tokens=max_output_tokens,
        response_format="json_object",
    )
    content = resp["choices"][0]["message"]["content"]
    tokens = int(resp.get("usage", {}).get("total_tokens", 0))
    parsed = json.loads(content)

    # Normalize: always provide these keys.
    out: dict[str, Any] = {
        "goals": list(parsed.get("goals") or []),
        "behaviors": dict(parsed.get("behaviors") or {}),
        "extraction_notes": str(parsed.get("extraction_notes") or ""),
        "_tokens_used": tokens,
    }
    return out


def assign_houses_and_ids(
    extracted: dict[str, Any],
    *,
    source_label: Optional[str] = None,
) -> dict[str, Any]:
    """Take the LLM's extracted goals and produce a connect-goals.json-shaped dict.

    - Assigns deterministic `id`, `number`, and house palette entry to each goal.
    - Builds `_meta` block with `source`, `last_synced`, `house_mapping_rationale`.
    - Preserves the LLM's `summary`, `success_criteria`, `impact_statement`,
      `keywords_for_alignment`, `short_name`, `name`.
    """
    goals_in = extracted.get("goals") or []
    if not isinstance(goals_in, list):
        raise ValueError("extracted.goals must be a list")

    used_ids: set[str] = set()
    goals_out: list[dict[str, Any]] = []
    for idx, g in enumerate(goals_in):
        if not isinstance(g, dict):
            continue
        short_name = (g.get("short_name") or g.get("name") or f"Goal {idx + 1}").strip()
        name = (g.get("name") or short_name).strip()
        number = idx + 1
        palette = HOUSE_PALETTE[idx % len(HOUSE_PALETTE)]

        # Deterministic, unique id (suffix on collision is rare but possible)
        base_id = f"goal-{number}-{_slugify(short_name)}"
        goal_id = base_id
        bump = 2
        while goal_id in used_ids:
            goal_id = f"{base_id}-{bump}"
            bump += 1
        used_ids.add(goal_id)

        goals_out.append(
            {
                "id": goal_id,
                "number": number,
                "short_name": short_name,
                "name": name,
                "house": palette["house"],
                "house_glyph": palette["house_glyph"],
                "color_primary": palette["color_primary"],
                "color_accent": palette["color_accent"],
                "summary": (g.get("summary") or "").strip(),
                "success_criteria": list(g.get("success_criteria") or []),
                "impact_statement": (g.get("impact_statement") or "").strip(),
                "keywords_for_alignment": list(g.get("keywords_for_alignment") or []),
            }
        )

    today = datetime.now(timezone.utc).date().isoformat()
    meta = {
        "source": source_label or f"Imported from Connect PDF on {today}",
        "last_synced": today,
        "house_mapping_rationale": (
            "Auto-assigned by import order from the Pensieve house palette "
            "(gryffindor, hufflepuff, slytherin, ravenclaw, internal, muggleborn, "
            "centaur, phoenix). Edit data/connect-goals.json to remap."
        ),
    }

    out: dict[str, Any] = {
        "_meta": meta,
        "goals": goals_out,
    }
    behaviors = extracted.get("behaviors") or {}
    if behaviors:
        out["behaviors"] = behaviors
    notes = extracted.get("extraction_notes")
    if notes:
        out["_meta"]["extraction_notes"] = notes
    return out


def import_pdf_to_goals(
    pdf_bytes: bytes,
    *,
    client: Optional[AzureOpenAIChatClient] = None,
    source_label: Optional[str] = None,
) -> dict[str, Any]:
    """High-level convenience: pdf bytes -> ready-to-save goals dict."""
    text = extract_pdf_text(pdf_bytes)
    extracted = extract_goals_from_text(text, client=client)
    return assign_houses_and_ids(extracted, source_label=source_label)
