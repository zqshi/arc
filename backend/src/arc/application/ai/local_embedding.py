"""Local embedding provider using sentence-transformers.

Falls back to a simple hash-based approach if the model cannot be loaded.
"""

from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)

_model = None
_model_load_attempted = False

_LOCAL_MODEL_DIM = 384  # all-MiniLM-L6-v2 native dimension
EMBEDDING_DIM = 1536  # must match Vector(1536) in DB model


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
        vector = model.encode(text, normalize_embeddings=True).tolist()
        if len(vector) < EMBEDDING_DIM:
            vector += [0.0] * (EMBEDDING_DIM - len(vector))
        return vector
    return _hash_embedding(text)


def _hash_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic pseudo-embedding from text hash. Not semantic but consistent."""
    import random as _rng

    gen = _rng.Random(hashlib.sha256(text.encode()).hexdigest())
    vec = [gen.gauss(0, 1) for _ in range(dim)]
    norm = sum(f * f for f in vec) ** 0.5 or 1.0
    return [f / norm for f in vec]
