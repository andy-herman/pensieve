"""Tests for the Constellation graph builder (pensieve/graph.py)."""

from __future__ import annotations

from pensieve.graph import _cosine_edges, build_graph
from pensieve.store.schema import Memory

GOALS = [
    {"id": "goal-a", "short_name": "A", "name": "Goal A", "lane": "crimson", "color_primary": "#7a2018"},
    {"id": "goal-b", "short_name": "B", "name": "Goal B", "lane": "azure", "color_primary": "#2c4670"},
]


def _mem(mid, *, goals=None, column="memory", completed=False, strand="s1") -> Memory:
    return Memory(
        id=mid,
        source="test",
        source_task_id=mid,
        title=f"task {mid}",
        connect_goal_ids=goals or [],
        column=column,
        completed=completed,
        suggested_strand=strand,
    )


def test_build_graph_nodes_and_alignment_edges():
    mems = [
        _mem("1", goals=["goal-a"]),
        _mem("2", goals=["goal-a", "goal-b"]),
        _mem("3", goals=[]),
    ]
    g = build_graph(mems, GOALS)
    goal_nodes = [n for n in g["nodes"] if n["type"] == "goal"]
    task_nodes = [n for n in g["nodes"] if n["type"] == "task"]
    assert len(goal_nodes) == 2
    assert len(task_nodes) == 3
    align = [e for e in g["edges"] if e["kind"] == "alignment"]
    # task 1 -> a, task 2 -> a and b  = 3 alignment edges
    assert len(align) == 3
    assert g["stats"]["unaligned"] == 1
    assert g["stats"]["by_goal"]["goal-a"] == 2
    assert g["stats"]["by_goal"]["goal-b"] == 1


def test_task_node_inherits_goal_lane_and_color():
    g = build_graph([_mem("1", goals=["goal-b"])], GOALS)
    task = next(n for n in g["nodes"] if n["type"] == "task")
    assert task["lane"] == "azure"
    assert task["color"] == "#2c4670"


def test_unaligned_task_uses_unassigned_lane():
    g = build_graph([_mem("1", goals=[])], GOALS)
    task = next(n for n in g["nodes"] if n["type"] == "task")
    assert task["lane"] == "unassigned"


def test_stats_by_column_and_completed():
    mems = [
        _mem("1", column="closed", completed=True),
        _mem("2", column="dive"),
        _mem("3", column="dive"),
    ]
    g = build_graph(mems, GOALS)
    assert g["stats"]["completed"] == 1
    assert g["stats"]["by_column"]["dive"] == 2
    assert g["stats"]["by_column"]["closed"] == 1


def test_cosine_edges_links_similar_vectors():
    ids = ["a", "b", "c"]
    # a and b nearly identical; c orthogonal
    vecs = [[1.0, 0.0], [0.99, 0.01], [0.0, 1.0]]
    edges = _cosine_edges(ids, vecs, threshold=0.6, max_per_node=2)
    pairs = {tuple(sorted((e["source"], e["target"]))) for e in edges}
    assert ("a", "b") in pairs
    assert ("a", "c") not in pairs
    assert ("b", "c") not in pairs


def test_semantic_edges_threshold_excludes_all_when_high():
    ids = ["a", "b"]
    vecs = [[1.0, 0.0], [0.0, 1.0]]
    assert _cosine_edges(ids, vecs, threshold=0.6, max_per_node=2) == []


def test_build_graph_with_embeddings_adds_semantic_edges():
    mems = [_mem("1", goals=["goal-a"]), _mem("2", goals=["goal-a"])]
    emb = {"1": [1.0, 0.0, 0.0], "2": [0.98, 0.02, 0.0]}
    g = build_graph(mems, GOALS, emb, semantic_threshold=0.6)
    assert g["stats"]["semantic_edges"] >= 1
