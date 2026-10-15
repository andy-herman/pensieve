"""Shared embedding function for the Chroma collections.

Chroma's built-in MiniLM ONNX embedder pads every input to 256 tokens. Pensieve
embeds short texts (a search query, or a card's title + why + impact), so almost
all of that work is padding, and it dominated search and card-save latency.

``UnpaddedMiniLM`` runs the same model with the same tokenizer and the same
256-token truncation, but encodes each text at its own length. Padding tokens
are masked out of attention and of the mean pooling, so the vectors match
Chroma's default to float rounding (see tests/test_embedding.py) and stay
comparable with every vector already stored.

One instance is shared process-wide so every store reuses a single ONNX session.
If the subclass cannot be built (for example a future Chroma reshuffles these
internals), we fall back to Chroma's default embedder, which is today's behavior.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

import numpy as np

try:  # chromadb >= 0.5.x layout
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
except ImportError:  # pragma: no cover - older single-module layout
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2  # type: ignore[no-redef]

# Must match Chroma's truncation so long texts keep exactly the same tokens.
MAX_TOKENS = 256


class UnpaddedMiniLM(ONNXMiniLM_L6_V2):
    """Chroma's MiniLM embedder without fixed-length padding."""

    def __init__(self, preferred_providers: Optional[list[str]] = None) -> None:
        super().__init__(preferred_providers=preferred_providers)
        self._unpadded_tokenizer: Any = None
        self._tokenizer_lock = threading.Lock()

    @property
    def tokenizer(self) -> Any:  # type: ignore[override]
        # Built lazily: the tokenizer file only exists after Chroma's
        # model download check, which runs inside __call__ before _forward.
        tok = self._unpadded_tokenizer
        if tok is None:
            with self._tokenizer_lock:
                if self._unpadded_tokenizer is None:
                    t = self.Tokenizer.from_file(
                        os.path.join(self.DOWNLOAD_PATH, self.EXTRACTED_FOLDER_NAME, "tokenizer.json")
                    )
                    t.enable_truncation(max_length=MAX_TOKENS)
                    t.no_padding()  # tokenizer.json ships a fixed-length padding config
                    self._unpadded_tokenizer = t
                tok = self._unpadded_tokenizer
        return tok

    def _forward(self, documents: list[str], batch_size: int = 32) -> np.ndarray:  # type: ignore[override]
        # One text per ONNX run: without padding, a multi-text batch would be ragged.
        if not documents:
            return np.zeros((0, 384), dtype=np.float32)
        return np.concatenate([super()._forward([d], batch_size=1) for d in documents])


_LOCK = threading.Lock()
_SHARED: Any = None


def get_embedding_function() -> Any:
    """Return the process-wide embedder used by every Pensieve collection."""
    global _SHARED
    if _SHARED is None:
        with _LOCK:
            if _SHARED is None:
                try:
                    _SHARED = UnpaddedMiniLM()
                except Exception:  # pragma: no cover - defensive fallback
                    from chromadb.utils import embedding_functions as ef

                    _SHARED = ef.DefaultEmbeddingFunction()
    return _SHARED
