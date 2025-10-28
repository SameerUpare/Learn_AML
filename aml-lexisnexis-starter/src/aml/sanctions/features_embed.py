# src/aml/sanctions/features_embed.py
from __future__ import annotations
import os
from functools import lru_cache
from typing import Iterable, List, Union

import numpy as np

# Default multilingual model; override via AML_EMB_MODEL env
_DEFAULT_MODEL = os.getenv("AML_EMB_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

@lru_cache(maxsize=1)
def _load_model():
    # Lazy import so the rest of the app works if deps aren’t installed yet
    from sentence_transformers import SentenceTransformer  # type: ignore
    return SentenceTransformer(_DEFAULT_MODEL)

def _as_list(x: Union[str, Iterable[str]]) -> List[str]:
    if isinstance(x, str):
        return [x]
    return list(x)

def _l2_normalize(vecs: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, eps)
    return (vecs / norms).astype("float32")

def encode_name(name: str) -> np.ndarray:
    """
    Encode a single name to a (1, D) float32 L2-normalized vector.
    """
    model = _load_model()
    emb = model.encode([name], convert_to_numpy=True, normalize_embeddings=False)
    return _l2_normalize(emb)

def encode_names(names: Iterable[str]) -> np.ndarray:
    """
    Encode many names to (N, D) float32 L2-normalized vectors.
    """
    model = _load_model()
    emb = model.encode(_as_list(names), convert_to_numpy=True, normalize_embeddings=False)
    return _l2_normalize(emb)

def cosine_sim(q_vec: np.ndarray, p_vecs: np.ndarray) -> np.ndarray:
    """
    q_vec: (D,) or (1, D)  L2-normalized
    p_vecs: (N, D)         L2-normalized
    returns: (N,) cosine similarities in [-1, 1]
    """
    q = q_vec.reshape(1, -1).astype("float32")
    return (p_vecs @ q.T).ravel()
