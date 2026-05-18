"""Local embedding provider using sentence-transformers.

Falls back to a simple hash-based approach if the model cannot be loaded.
"""

from __future__ import annotations

import hashlib
import logging
import struct
from functools import lru_cache

logger = logging.getLogger(__name__)

_model = None
_model_load_attempted = False

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 dimension


def _load_model():
    global _model, _model_load_attempted
    if _model_load_attempted:
        return _model
    _model_load_attempted = True
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Local embedding model loaded: all-MiniLM-L6-v2")
    except Exception as exc:
        logger.warning("Failed to load sentence-transformers model: %s. Using hash fallback.", exc)
        _model = None
    return _model


def embed_local(text: str) -> list[float]:
    """Generate embedding vector for text using local model."""
    model = _load_model()
    if model is not None:
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    return _hash_embedding(text)


def _hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic pseudo-embedding from text hash. Not semantic but consistent."""
    digest = hashlib.sha512(text.encode()).digest()
    while len(digest) < dim * 4:
        digest += hashlib.sha512(digest).digest()
    floats = struct.unpack(f"{dim}f", digest[: dim * 4])
    norm = sum(f * f for f in floats) ** 0.5 or 1.0
    return [f / norm for f in floats]
