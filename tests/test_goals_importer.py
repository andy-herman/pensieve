"""Unit tests for pensieve.enrichment.goals_importer."""

from __future__ import annotations

from typing import Any

import pytest

from pensieve.enrichment.goals_importer import (
    HOUSE_PALETTE,
    assign_houses_and_ids,
    extract_goals_from_text,
    import_pdf_to_goals,
)

# ---------- helpers ----------


class _StubClient:
    """Mock AzureOpenAIChatClient that returns a canned JSON response."""

    def __init__(self, payload: dict[str, Any], tokens: int = 1234):
        self.payload = payload
        self.tokens = tokens
        self.last_messages: list[dict[str, str]] | None = None

    def chat(self, messages, max_output_tokens=3000, response_format="json_object", timeout=60.0):
        import json

        self.last_messages = messages
        return {
            "choices": [{"message": {"content": json.dumps(self.payload)}}],
            "usage": {"total_tokens": self.tokens},
        }


def _five_goal_llm_payload() -> dict[str, Any]:
    return {
        "goals": [
            {
                "short_name": "DORA",
                "name": "DORA Compliance Leadership",
                "summary": "Lead DORA program.",
                "success_criteria": ["JET on time", "Playbook authored"],
                "impact_statement": "Foundation for EU regulator response.",
                "keywords_for_alignment": ["DORA", "JET", "RFI"],
            },
            {
                "short_name": "UK CTP",
                "name": "UK CTP Year 1 Submission",
                "summary": "Year 1 obligations.",
                "success_criteria": ["Self-assessment submitted"],
                "impact_statement": "Credibility with BoE, PRA, FCA.",
                "keywords_for_alignment": ["UK CTP", "CTP", "BoE", "PRA", "FCA"],
            },
            {
                "short_name": "NIS2",
                "name": "NIS2 Readiness Foundation",
                "summary": "Build NIS2 foundation.",
                "success_criteria": [],
                "impact_statement": "Reduces ramp time.",
                "keywords_for_alignment": ["NIS2", "Ireland", "directive"],
            },
            {
                "short_name": "AI Program",
                "name": "AI Strategy and Argus",
                "summary": "AI transformation program.",
                "success_criteria": ["Governance launched"],
                "impact_statement": "Center of excellence for AI compliance.",
                "keywords_for_alignment": ["Argus", "Pensieve", "AI program"],
            },
            {
                "short_name": "Internal Goals",
                "name": "Internal CISO GRC Goals",
                "summary": "Internal team commitments.",
                "success_criteria": [],
                "impact_statement": "Healthy ops substrate.",
                "keywords_for_alignment": ["onboarding", "1:1", "ops"],
            },
        ],
        "behaviors": {
            "trust_intentionally": "Direct and approachable.",
            "solve_at_scale": "Durable solutions over band-aids.",
        },
        "extraction_notes": "5 goals extracted cleanly.",
    }


# ---------- tests ----------


def test_extract_goals_from_text_uses_stub_client_and_returns_normalized_dict():
    stub = _StubClient(_five_goal_llm_payload(), tokens=4321)

    out = extract_goals_from_text("some pdf text here", client=stub)

    assert isinstance(out, dict)
    assert len(out["goals"]) == 5
    assert out["behaviors"]["trust_intentionally"].startswith("Direct")
    assert out["extraction_notes"].startswith("5 goals")
    assert out["_tokens_used"] == 4321
    # Make sure we actually called the LLM with both system + user role.
    roles = [m["role"] for m in (stub.last_messages or [])]
    assert roles == ["system", "user"]


def test_extract_goals_from_text_raises_on_empty_input():
    with pytest.raises(ValueError, match="empty"):
        extract_goals_from_text("", client=_StubClient({"goals": []}))
    with pytest.raises(ValueError, match="empty"):
        extract_goals_from_text("   \n\n  ", client=_StubClient({"goals": []}))


def test_assign_houses_and_ids_handles_five_goals_with_extended_palette():
    extracted = _five_goal_llm_payload()

    finalized = assign_houses_and_ids(extracted, source_label="test fixture")

    assert finalized["_meta"]["source"] == "test fixture"
    assert "last_synced" in finalized["_meta"]
    assert finalized["behaviors"]["solve_at_scale"]

    goals = finalized["goals"]
    assert len(goals) == 5
    # Numbers are 1..5 in order.
    assert [g["number"] for g in goals] == [1, 2, 3, 4, 5]
    # IDs are deterministic, unique, slugified.
    ids = [g["id"] for g in goals]
    assert ids == [
        "goal-1-dora",
        "goal-2-uk-ctp",
        "goal-3-nis2",
        "goal-4-ai-program",
        "goal-5-internal-goals",
    ]
    assert len(set(ids)) == 5
    # Houses come from the palette in order: 4 canonical + 1 extended.
    expected_houses = [p["house"] for p in HOUSE_PALETTE[:5]]
    assert [g["house"] for g in goals] == expected_houses
    # Palette colors are wired correctly for goal 5 (the new extended one).
    assert goals[4]["house"] == "internal"
    assert goals[4]["color_primary"] == HOUSE_PALETTE[4]["color_primary"]
    # Source fields preserved verbatim from the LLM.
    assert goals[0]["summary"] == "Lead DORA program."
    assert goals[0]["keywords_for_alignment"] == ["DORA", "JET", "RFI"]


def test_assign_houses_and_ids_cycles_palette_for_more_than_eight_goals():
    extracted = {
        "goals": [{"short_name": f"Goal {i}", "name": f"Goal {i}"} for i in range(10)],
    }
    finalized = assign_houses_and_ids(extracted)
    goals = finalized["goals"]
    assert len(goals) == 10
    # First 8 hit each palette entry exactly once.
    assert [g["house"] for g in goals[:8]] == [p["house"] for p in HOUSE_PALETTE]
    # Goals 9, 10 wrap to the first two entries.
    assert goals[8]["house"] == HOUSE_PALETTE[0]["house"]
    assert goals[9]["house"] == HOUSE_PALETTE[1]["house"]
    # IDs are still unique even though short_name slug collisions would otherwise happen.
    assert len({g["id"] for g in goals}) == 10


def test_assign_houses_and_ids_handles_empty_goals_list():
    finalized = assign_houses_and_ids({"goals": [], "behaviors": {}, "extraction_notes": "none"})
    assert finalized["goals"] == []
    assert finalized["_meta"]["source"].startswith("Imported from Connect PDF on ")
    assert finalized["_meta"]["extraction_notes"] == "none"


def test_import_pdf_to_goals_end_to_end_with_stub(monkeypatch):
    """Patch extract_pdf_text to bypass real pypdf so this works without a real PDF."""
    from pensieve.enrichment import goals_importer as gi

    monkeypatch.setattr(gi, "extract_pdf_text", lambda _b: "fake pdf text")
    stub = _StubClient(_five_goal_llm_payload(), tokens=999)

    out = import_pdf_to_goals(b"%PDF-fake", client=stub, source_label="unit-test")

    assert out["_meta"]["source"] == "unit-test"
    assert len(out["goals"]) == 5
    assert out["goals"][4]["house"] == "internal"
