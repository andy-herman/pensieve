"""The unpadded embedder must produce the same vectors as Chroma's default.

Stored vectors were written by Chroma's default MiniLM embedder (inputs padded
to 256 tokens). Search compares new query vectors against them, so the faster
unpadded embedder is only safe if it matches to float rounding.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from pensieve.store.embedding import UnpaddedMiniLM, get_embedding_function

try:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
except ImportError:  # pragma: no cover
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2  # type: ignore[no-redef]

_MODEL_DIR = os.path.join(ONNXMiniLM_L6_V2.DOWNLOAD_PATH, ONNXMiniLM_L6_V2.EXTRACTED_FOLDER_NAME)

# Never download the model from a test; the store tests already need it locally.
pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(_MODEL_DIR, "model.onnx")),
    reason="Chroma ONNX model not cached locally",
)

TEXTS = [
    "risk review",
    "x",
    "Quarterly control attestation for the vendor policy\n\nWhy: keeps audit evidence fresh",
    "Résumé naïve café, unicode and punctuation: 50% done (v2)!",
    # Longer than the 256-token limit, so truncation must match exactly.
    " ".join(["governance metrics and compliance reporting cadence"] * 80),
]


@pytest.fixture(scope="module")
def default_vectors():
    return np.asarray(ONNXMiniLM_L6_V2()(TEXTS))


def test_unpadded_matches_chroma_default(default_vectors):
    ours = np.asarray(UnpaddedMiniLM()(TEXTS))
    assert ours.shape == default_vectors.shape == (len(TEXTS), 384)
    assert float(np.max(np.abs(ours - default_vectors))) < 1e-5


def test_batch_equals_single_calls():
    ef = UnpaddedMiniLM()
    batch = np.asarray(ef(TEXTS))
    singles = np.vstack([np.asarray(ef([t])) for t in TEXTS])
    assert float(np.max(np.abs(batch - singles))) < 1e-6


def test_stores_share_one_embedder(tmp_path, monkeypatch):
    from pensieve.config import get_settings
    from pensieve.store import ChromaMemoryStore, ChromaVialStore

    monkeypatch.setenv("PENSIEVE_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    ef = get_embedding_function()
    assert isinstance(ef, UnpaddedMiniLM)
    assert ChromaMemoryStore()._memories._embedding_function is ef
    assert ChromaVialStore()._vials._embedding_function is ef
