"""Handoff a Pensieve Memory into a live GitHub Copilot desktop app session.

Gathers the full context for a task (enriched Why/Impact, original notes,
private notes, strand description, aligned Connect goals, captured Vials,
related board memories, and matching Pensieve Docs excerpts), creates a new
session in the running GitHub Copilot desktop app over its local WebSocket
control plane, sends the kickoff prompt so Copilot starts working immediately,
and navigates the GitHub Copilot app UI to the new session.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from pensieve import docs_store
from pensieve.config import Settings, get_settings
from pensieve.store.schema import Memory, Vial


class CopilotAppUnavailable(RuntimeError):
    """The GitHub Copilot desktop app could not be reached or started."""


def concise_session_title(memory: Memory, max_len: int = 40) -> str:
    """Build a clean sidebar title (<=40 chars) for the GitHub Copilot session."""
    raw = (memory.display_title or memory.title or "Pensieve task").strip()
    raw = re.sub(r"^\s*\[\d+\]\s*", "", raw)
    raw = " ".join(raw.split())
    if len(raw) <= max_len:
        return raw or "Pensieve task"
    cut = raw[: max_len - 1].rsplit(" ", 1)[0].rstrip(":,-;")
    return (cut or raw[: max_len - 1]).strip()


def _matching_doc_excerpts(
    memory: Memory,
    docs: list[dict[str, Any]],
    max_chars: int = 2500,
) -> list[tuple[str, str]]:
    """Extract relevant markdown sections or excerpts from saved Pensieve Docs."""
    if not docs:
        return []
    title_text = f"{memory.title} {memory.display_title or ''}"
    num_match = re.search(r"\[(\d{2})\]", title_text)
    tag_num = num_match.group(1) if num_match else None

    keywords = {
        w.lower()
        for w in re.findall(r"[A-Za-z0-9]{4,}", title_text)
        if w.lower() not in {"with", "from", "that", "this", "into", "review", "prep", "team", "work"}
    }

    matches: list[tuple[str, str]] = []
    for d in docs:
        doc_title = str(d.get("title") or d.get("id") or "Document")
        content = str(d.get("content") or "").strip()
        if not content:
            continue
        if tag_num and f"#{tag_num}" in content:
            lines = [ln for ln in content.splitlines() if f"#{tag_num}" in ln or tag_num in ln]
            if lines:
                excerpt = "\n".join(lines)[:max_chars]
                matches.append((doc_title, excerpt))
                continue
        matched_lines = [
            ln
            for ln in content.splitlines()
            if any(k in ln.lower() for k in keywords)
        ]
        if matched_lines:
            matches.append((doc_title, "\n".join(matched_lines[:12])[:max_chars]))
    return matches[:3]


def _related_memories(
    target: Memory,
    all_memories: list[Memory],
    limit: int = 5,
) -> list[Memory]:
    """Find related memories on the board by shared strand or Connect goals."""
    target_goals = set(target.connect_goal_ids or [])
    scored: list[tuple[int, Memory]] = []
    for m in all_memories:
        if m.id == target.id:
            continue
        score = 0
        if target.suggested_strand and m.suggested_strand == target.suggested_strand:
            score += 3
        overlap = len(target_goals & set(m.connect_goal_ids or []))
        score += overlap * 2
        if target.list_name and m.list_name == target.list_name:
            score += 1
        if m.column != "closed":
            score += 1
        if score > 1:
            scored.append((score, m))
    scored.sort(key=lambda pair: (-pair[0], pair[1].title))
    return [m for _, m in scored[:limit]]


def build_copilot_kickoff_prompt(
    memory: Memory,
    *,
    all_memories: Optional[list[Memory]] = None,
    goals: Optional[list[dict[str, Any]]] = None,
    strand_catalog: Optional[list[dict[str, Any]]] = None,
    vials: Optional[list[Vial]] = None,
    docs: Optional[list[dict[str, Any]]] = None,
    settings: Optional[Settings] = None,
) -> str:
    """Assemble a comprehensive kickoff prompt with all relevant task context."""
    settings = settings or get_settings()
    all_memories = all_memories or []
    goals = goals or []
    strand_catalog = strand_catalog or []
    vials = vials or []
    docs = docs or []

    heading = memory.display_title or memory.title
    lines: list[str] = [
        f"I am starting work on this task from my Pensieve board: **{heading}**",
        "",
        "Please pull all relevant live context (emails, Teams chats/channels, meeting notes, and documents) using your available tools and help me execute on this task right away.",
        "",
        "## Task Dossier (from Pensieve)",
        f"- **Display Title:** {heading}",
    ]
    if memory.title and memory.title != heading:
        lines.append(f"- **Source Task Subject:** {memory.title}")
    if memory.list_name:
        lines.append(f"- **Source List:** {memory.list_name}")
    lines.append(f"- **Board Column:** {memory.column}")
    if memory.due_date:
        lines.append(f"- **Due Date:** {memory.due_date.date().isoformat()}")
    if memory.categories:
        lines.append(f"- **Categories / Tags:** {', '.join(memory.categories)}")

    if memory.suggested_strand:
        strand_info = next(
            (s for s in strand_catalog if s.get("id") == memory.suggested_strand),
            None,
        )
        if strand_info:
            s_name = strand_info.get("display_name") or memory.suggested_strand
            s_desc = strand_info.get("description") or ""
            lines.append(f"- **Workstream Strand:** {s_name} (`{memory.suggested_strand}`) - {s_desc}")
        else:
            lines.append(f"- **Workstream Strand:** `{memory.suggested_strand}`")

    if memory.why:
        lines.extend(["", "### Why This Task Matters", memory.why.strip()])
    if memory.impact:
        lines.extend(["", "### Expected Impact", memory.impact.strip()])
    if memory.original_notes:
        lines.extend(["", "### Source Notes, Actions & Collaborators", memory.original_notes.strip()])
    if memory.notes_for_user:
        lines.extend(["", "### My Private Pensieve Notes", memory.notes_for_user.strip()])

    aligned_goals = [g for g in goals if g.get("id") in (memory.connect_goal_ids or [])]
    if aligned_goals:
        lines.extend(["", "## Aligned Connect Goals"])
        for g in aligned_goals:
            num = g.get("number", "?")
            name = g.get("name") or g.get("short_name") or g.get("id")
            summary = (g.get("summary") or "").strip()
            lines.append(f"- **Goal #{num}: {name}**")
            if summary:
                lines.append(f"  - Summary: {summary}")
            criteria = g.get("success_criteria") or []
            if criteria:
                lines.append("  - Success criteria: " + "; ".join(str(c) for c in criteria))
            if g.get("impact_statement"):
                lines.append(f"  - Committed impact: {g['impact_statement']}")
        if memory.connect_alignment_note:
            lines.append(f"- **Task Alignment Note:** {memory.connect_alignment_note.strip()}")

    if vials:
        lines.extend(["", "## Prior Captured Vials / Progress Notes"])
        for v in vials:
            txt = (v.polished_text or v.captured_text or "").strip()
            if txt:
                lines.append(f"- ({v.captured_at.date().isoformat()}) {txt}")

    related = _related_memories(memory, all_memories)
    if related:
        lines.extend(["", "## Related Tasks Currently on My Pensieve Board"])
        for r in related:
            r_title = r.display_title or r.title
            r_due = f", due {r.due_date.date().isoformat()}" if r.due_date else ""
            lines.append(f"- **{r_title}** (`{r.column}`{r_due}): {r.why or r.original_notes[:160]}")

    doc_excerpts = _matching_doc_excerpts(memory, docs)
    if doc_excerpts:
        lines.extend(["", "## Relevant Excerpts from Pensieve Docs"])
        for doc_title, excerpt in doc_excerpts:
            lines.append(f"### From `{doc_title}`")
            lines.append(excerpt)

    if settings.vault_dir and Path(settings.vault_dir).exists():
        lines.extend(
            [
                "",
                "## Local Knowledge Base",
                f"- Obsidian vault path on this PC: `{settings.vault_dir}`",
            ]
        )

    lines.extend(
        [
            "",
            "## How to Start Working on This Now",
            "1. **Gather live context:** Use your connected M365 / WorkIQ tools (and Loop or local files if relevant) to search for recent emails, Teams messages, meetings, and documents related to the people, deliverables, and topics above.",
            "2. **Synthesize current state:** Briefly summarize any new updates or materials you find alongside the Pensieve context above.",
            "3. **Produce the next deliverable:** Draft the concrete output, talk track, review notes, reply message, or action plan needed to move this task to completion.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _copilot_app_exe() -> Optional[Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "Programs" / "GitHub Copilot" / "github.exe"
        if candidate.is_file():
            return candidate
    return None


def _read_ws_endpoint(run_dir: Optional[Path] = None) -> Optional[tuple[int, str]]:
    run_dir = run_dir or (Path.home() / ".copilot" / "run")
    port_file = run_dir / "ws.port"
    token_file = run_dir / "ws.token"
    if not port_file.is_file() or not token_file.is_file():
        return None
    try:
        port_lines = port_file.read_text(encoding="utf-8").splitlines()
        token_lines = token_file.read_text(encoding="utf-8").splitlines()
        if not port_lines or not token_lines:
            return None
        port = int(port_lines[0].strip())
        token = token_lines[0].strip()
        if not (0 < port < 65536) or not token:
            return None
        return port, token
    except Exception:
        return None


def _ensure_copilot_app_ws(run_dir: Optional[Path] = None, timeout: float = 12.0) -> tuple[int, str]:
    endpoint = _read_ws_endpoint(run_dir)
    if endpoint is not None:
        return endpoint

    exe = _copilot_app_exe()
    if exe is None:
        raise CopilotAppUnavailable(
            "GitHub Copilot desktop app (github.exe) was not found in %LOCALAPPDATA%\\Programs\\GitHub Copilot."
        )
    try:
        subprocess.Popen([str(exe)], close_fds=True)
    except Exception as e:
        raise CopilotAppUnavailable(f"Could not start GitHub Copilot desktop app: {e}") from e

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.4)
        endpoint = _read_ws_endpoint(run_dir)
        if endpoint is not None:
            return endpoint

    raise CopilotAppUnavailable(
        "GitHub Copilot desktop app did not expose its local session port in ~/.copilot/run/ws.port."
    )


async def _create_and_start_ws_session(
    *,
    port: int,
    token: str,
    title: str,
    prompt: str,
    cwd: str,
    timeout: float = 20.0,
) -> dict[str, Any]:
    import websockets

    uri = f"ws://127.0.0.1:{port}?token={token}"
    async with websockets.connect(uri, open_timeout=10.0, close_timeout=5.0) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "create_session",
                    "cwd": cwd,
                    "session_type": "general_chat",
                }
            )
        )

        session_id: Optional[str] = None
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.5, deadline - time.monotonic())
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            data = json.loads(raw)
            msg_type = data.get("type")
            if msg_type == "session_created" and data.get("session_id"):
                session_id = str(data["session_id"])
                break
            if msg_type == "error":
                raise CopilotAppUnavailable(
                    f"GitHub Copilot app rejected session creation: {data.get('message')}"
                )

        if not session_id:
            raise CopilotAppUnavailable("Timed out waiting for GitHub Copilot app to create the session.")

        await ws.send(
            json.dumps(
                {
                    "type": "rename_session",
                    "session_id": session_id,
                    "title": title,
                }
            )
        )
        await ws.send(
            json.dumps(
                {
                    "type": "send_message",
                    "session_id": session_id,
                    "prompt": prompt,
                    "initial_prompt": True,
                }
            )
        )
        deep_link = (
            f"github-app://notification/open?task_session_id={session_id}&session_type=general_chat"
        )
        await ws.send(
            json.dumps(
                {
                    "type": "handle_deep_link",
                    "url": deep_link,
                }
            )
        )
        await asyncio.sleep(0.15)
        return {
            "session_id": session_id,
            "title": title,
            "app_url": f"ghapp://sessions/{session_id}",
            "deep_link": deep_link,
        }


def launch_memory_in_copilot_app(
    memory: Memory,
    *,
    all_memories: Optional[list[Memory]] = None,
    goals: Optional[list[dict[str, Any]]] = None,
    strand_catalog: Optional[list[dict[str, Any]]] = None,
    vials: Optional[list[Vial]] = None,
    docs: Optional[list[dict[str, Any]]] = None,
    settings: Optional[Settings] = None,
    run_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Gather all context for ``memory`` and start a live session in GitHub Copilot app."""
    settings = settings or get_settings()
    if docs is None:
        docs = []
        for meta in docs_store.list_docs(settings):
            doc_id = meta.get("id")
            if doc_id:
                full_doc = docs_store.read_doc(str(doc_id), settings)
                if full_doc:
                    docs.append(full_doc)

    prompt = build_copilot_kickoff_prompt(
        memory,
        all_memories=all_memories,
        goals=goals,
        strand_catalog=strand_catalog,
        vials=vials,
        docs=docs,
        settings=settings,
    )
    title = concise_session_title(memory)
    port, token = _ensure_copilot_app_ws(run_dir=run_dir)
    cwd = str(Path.home())

    result = asyncio.run(
        _create_and_start_ws_session(
            port=port,
            token=token,
            title=title,
            prompt=prompt,
            cwd=cwd,
        )
    )
    result["prompt_chars"] = len(prompt)
    return result
