"""Constellation graph: nodes/edges/stats for the dashboard graph view.

Builds an Obsidian-style relationship graph from enriched memories:
  - one hub node per Connect goal,
  - one node per task (memory),
  - "alignment" edges task -> goal (from connect_goal_ids),
  - "semantic" edges task <-> task derived from ChromaDB embeddings
    (cosine similarity over the same vectors that power search).

Pure functions; the API layer supplies memories, goals, and the embedding
vectors (read from the Chroma collection). No I/O here so it stays testable.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from pensieve.store.schema import Memory

# Lane slug -> display color is owned by the frontend; here we just pass the
# goal's color_primary through so the canvas can paint without a lookup.
_DEFAULT_TASK_COLOR = "#42c8f5"  # --cyan
_UNASSIGNED_LANE = "unassigned"


def _cosine_edges(
    ids: Sequence[str],
    vectors: Sequence[Sequence[float]],
    *,
    threshold: float,
    max_per_node: int,
) -> list[dict[str, Any]]:
    """Top semantic edges between task nodes.

    Returns undirected edges (deduped) {source, target, kind:"semantic", weight}
    where weight is cosine similarity. Degrades to [] if numpy is unavailable
    or there are fewer than two vectors.
    """
    if len(ids) < 2:
        return []
    try:
        import numpy as np
    except Exception:
        return []

    mat = np.asarray(vectors, dtype="float32")
    if mat.ndim != 2 or mat.shape[0] != len(ids):
        return []
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = mat / norms
    sims = unit @ unit.T  # cosine similarity matrix

    seen: set[tuple[str, str]] = set()
    edges: list[dict[str, Any]] = []
    n = len(ids)
    for i in range(n):
        # rank neighbors of i by similarity, skip self
        order = np.argsort(-sims[i])
        taken = 0
        for j in order:
            if int(j) == i:
                continue
            w = float(sims[i][j])
            if w < threshold:
                break  # sorted desc; nothing better remains
            a, b = ids[i], ids[int(j)]
            key = (a, b) if a < b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": a, "target": b, "kind": "semantic", "weight": round(w, 4)})
            taken += 1
            if taken >= max_per_node:
                break
    return edges


def _task_lane_and_color(
    mem: Memory, goals_by_id: dict[str, dict[str, Any]]
) -> tuple[str, str]:
    for gid in mem.connect_goal_ids or []:
        g = goals_by_id.get(gid)
        if g:
            return g.get("lane", _UNASSIGNED_LANE), g.get("color_primary") or _DEFAULT_TASK_COLOR
    return _UNASSIGNED_LANE, _DEFAULT_TASK_COLOR


def build_graph(
    memories: list[Memory],
    goals: list[dict[str, Any]],
    embeddings: Optional[dict[str, Sequence[float]]] = None,
    *,
    semantic_threshold: float = 0.6,
    max_semantic_per_node: int = 3,
) -> dict[str, Any]:
    """Assemble the constellation graph payload.

    :param memories: enriched memories from the store.
    :param goals: Connect goal catalog (each needs id, short_name, lane, color_primary).
    :param embeddings: optional {memory_id: vector}; enables semantic edges.
    :returns: {nodes, edges, stats} ready to JSON-serialize.
    """
    goals_by_id = {g["id"]: g for g in goals if "id" in g}

    nodes: list[dict[str, Any]] = []
    for g in goals:
        if "id" not in g:
            continue
        nodes.append(
            {
                "id": g["id"],
                "type": "goal",
                "label": g.get("short_name") or g.get("name") or g["id"],
                "lane": g.get("lane", _UNASSIGNED_LANE),
                "color": g.get("color_primary") or _DEFAULT_TASK_COLOR,
                "size": 26,
            }
        )

    edges: list[dict[str, Any]] = []
    by_goal: dict[str, int] = {g["id"]: 0 for g in goals if "id" in g}
    by_column: dict[str, int] = {"memory": 0, "dive": 0, "review": 0, "closed": 0}
    unaligned = 0
    completed = 0

    for m in memories:
        lane, color = _task_lane_and_color(m, goals_by_id)
        nodes.append(
            {
                "id": m.id,
                "type": "task",
                "label": m.title,
                "lane": lane,
                "color": color,
                "column": m.column,
                "strand": m.suggested_strand or "",
                "completed": bool(m.completed),
                "goal_ids": list(m.connect_goal_ids or []),
                "size": 12,
            }
        )
        by_column[m.column] = by_column.get(m.column, 0) + 1
        if m.completed:
            completed += 1
        aligned_any = False
        for gid in m.connect_goal_ids or []:
            if gid in goals_by_id:
                edges.append({"source": m.id, "target": gid, "kind": "alignment", "weight": 1.0})
                by_goal[gid] = by_goal.get(gid, 0) + 1
                aligned_any = True
        if not aligned_any:
            unaligned += 1

    if embeddings:
        ids = [m.id for m in memories if m.id in embeddings]
        vecs = [embeddings[i] for i in ids]
        edges.extend(
            _cosine_edges(
                ids,
                vecs,
                threshold=semantic_threshold,
                max_per_node=max_semantic_per_node,
            )
        )

    by_strand: dict[str, int] = {}
    for m in memories:
        key = m.suggested_strand or "unstranded"
        by_strand[key] = by_strand.get(key, 0) + 1

    stats = {
        "total_tasks": len(memories),
        "completed": completed,
        "unaligned": unaligned,
        "by_goal": by_goal,
        "by_column": by_column,
        "by_strand": by_strand,
        "goal_count": len(by_goal),
        "semantic_edges": sum(1 for e in edges if e["kind"] == "semantic"),
        "alignment_edges": sum(1 for e in edges if e["kind"] == "alignment"),
    }

    return {"nodes": nodes, "edges": edges, "stats": stats}
