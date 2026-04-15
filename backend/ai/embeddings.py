"""Local text embeddings via BAAI/bge-small-en-v1.5 on Apple Silicon MPS.

Shared by ai.cache (semantic query cache) and ai.dedup (pre-/contents URL dedup).
First call downloads ~130MB to ~/.cache/huggingface; subsequent runs load from disk.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

_model: SentenceTransformer | None = None


def _pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, device=_pick_device())
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    """Batch-encode texts to L2-normalized vectors (cosine-ready)."""
    if not texts:
        return []
    model = _get_model()
    arr = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return arr.tolist()
